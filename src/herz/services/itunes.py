import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from herz.core.config import Settings

SEARCH_URL = "https://itunes.apple.com/search"
LOOKUP_URL = "https://itunes.apple.com/lookup"
TOP_SONGS_URL = "https://itunes.apple.com/{country}/rss/topsongs/limit={limit}/genre={genre_id}/json"

# lookup APIに一度に渡すIDの数
_LOOKUP_BATCH = 50

# レート制限に掛かると 403 / 429 が返る。少し待てば解除されるので間隔を空けて再試行する
_RETRY_STATUSES = frozenset({403, 429, 500, 502, 503, 504})
_RETRY_DELAYS_SEC = (30.0, 60.0, 120.0, 300.0)

# ライブラリの土台にするジャンル別チャート (iTunesのジャンルID: 表示名)。
# カラオケ・フィットネス等、曲の雰囲気で探す対象として意味の薄いものは除いている
CHART_GENRES: dict[int, str] = {
    27: "J-Pop",
    30: "歌謡曲",
    29: "アニメ",
    51: "K-Pop",
    14: "ポップ",
    21: "ロック",
    20: "オルタナティブ",
    10: "シンガーソングライター",
    18: "ヒップホップ／ラップ",
    15: "R&B／ソウル",
    7: "エレクトロニック",
    17: "ダンス",
    11: "ジャズ",
    2: "ブルース",
    5: "クラシック",
    16: "サウンドトラック",
    13: "ニューエイジ",
    25: "イージーリスニング",
    6: "カントリー",
    12: "ラテン",
    24: "レゲエ",
    19: "ワールド",
}


@dataclass(frozen=True)
class PreviewTrack:
    source_track_id: str
    title: str
    artist: str
    artist_id: str | None
    genre: str | None
    preview_url: str
    external_url: str | None
    artwork_url: str | None = None


def _parse_tracks(results: list[dict[str, Any]]) -> list[PreviewTrack]:
    return [
        PreviewTrack(
            source_track_id=str(item["trackId"]),
            title=item["trackName"],
            artist=item["artistName"],
            artist_id=str(item["artistId"]) if item.get("artistId") else None,
            genre=item.get("primaryGenreName"),
            preview_url=item["previewUrl"],
            external_url=item.get("trackViewUrl"),
            artwork_url=item.get("artworkUrl100"),
        )
        for item in results
        if item.get("kind") == "song" and item.get("previewUrl")
    ]


class ITunesClient:
    """iTunes Search API クライアント。

    認証不要で30秒のプレビュー音源 (AAC/m4a) のURLが取れるため、分析用の音源取得に使う。
    Spotifyは新規アプリだと preview_url が null で返るため音源取得には使えない。
    """

    def __init__(
        self, settings: Settings, http_client: httpx.AsyncClient, min_api_interval_sec: float = 0.0
    ) -> None:
        """min_api_interval_sec: 検索・lookup・チャートAPIを呼ぶ最小間隔（大量に取り込むとき用）。
        指定したときはレート制限等の一時的なエラーも待って再試行する（指定しないAPI経由の呼び出しは即失敗させる）。
        プレビュー音源のダウンロードはCDN配信でレート制限の対象外なので間隔を空けない。"""
        self._country = settings.itunes_country
        self._http = http_client
        self._min_api_interval = min_api_interval_sec
        self._api_lock = asyncio.Lock()
        self._last_api_call = 0.0

    async def search_previews(self, term: str, limit: int = 25) -> list[PreviewTrack]:
        """キーワード検索。曲名・アーティスト名への一致で返るため、ジャンル名で探すと
        そのジャンル名を曲名に含むBGM等が多く混ざる点に注意（ジャンルで集めるなら chart_previews）。"""
        response = await self._api_get(
            SEARCH_URL,
            params={
                "term": term,
                "media": "music",
                "entity": "song",
                "limit": limit,
                "country": self._country,
            },
        )
        return _parse_tracks(response.json()["results"])

    async def chart_previews(
        self, genre_id: int, limit: int = 100, country: str | None = None
    ) -> list[PreviewTrack]:
        """ジャンル別の人気曲チャート（最大200曲程度）をプレビュー付きで取得する。"""
        country = country or self._country
        response = await self._api_get(
            TOP_SONGS_URL.format(country=country.lower(), limit=limit, genre_id=genre_id)
        )
        entries = response.json()["feed"].get("entry", [])
        # 1件だけのときは配列ではなくオブジェクトで返ってくる
        if isinstance(entries, dict):
            entries = [entries]
        track_ids = [entry["id"]["attributes"]["im:id"] for entry in entries]
        return await self.lookup_previews(track_ids, country=country)

    async def lookup_previews(self, track_ids: list[str], country: str | None = None) -> list[PreviewTrack]:
        tracks: list[PreviewTrack] = []
        for start in range(0, len(track_ids), _LOOKUP_BATCH):
            response = await self._api_get(
                LOOKUP_URL,
                params={
                    "id": ",".join(track_ids[start : start + _LOOKUP_BATCH]),
                    "country": country or self._country,
                },
            )
            tracks.extend(_parse_tracks(response.json()["results"]))
        return tracks

    async def artist_previews(
        self, artist_id: str, limit: int = 50, country: str | None = None
    ) -> list[PreviewTrack]:
        """アーティストの曲（おおむね人気順）。先頭にはアーティスト自体の情報が入るが曲以外は除外される。"""
        response = await self._api_get(
            LOOKUP_URL,
            params={
                "id": artist_id,
                "entity": "song",
                "limit": limit,
                "country": country or self._country,
            },
        )
        return _parse_tracks(response.json()["results"])

    async def download_preview(self, preview_url: str) -> bytes:
        response = await self._http.get(preview_url)
        response.raise_for_status()
        return response.content

    async def _api_get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        for delay in (*_RETRY_DELAYS_SEC, None):
            async with self._api_lock:
                wait = self._last_api_call + self._min_api_interval - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last_api_call = time.monotonic()
                response = await self._http.get(url, params=params)
            if response.status_code not in _RETRY_STATUSES or delay is None or self._min_api_interval == 0:
                break
            await asyncio.sleep(delay)
        response.raise_for_status()
        return response
