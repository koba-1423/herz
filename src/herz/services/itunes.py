from dataclasses import dataclass
from typing import Any

import httpx

from herz.core.config import Settings

SEARCH_URL = "https://itunes.apple.com/search"
LOOKUP_URL = "https://itunes.apple.com/lookup"
TOP_SONGS_URL = "https://itunes.apple.com/{country}/rss/topsongs/limit={limit}/genre={genre_id}/json"

# lookup APIに一度に渡すIDの数
_LOOKUP_BATCH = 50

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
    genre: str | None
    preview_url: str
    external_url: str | None


def _parse_tracks(results: list[dict[str, Any]]) -> list[PreviewTrack]:
    return [
        PreviewTrack(
            source_track_id=str(item["trackId"]),
            title=item["trackName"],
            artist=item["artistName"],
            genre=item.get("primaryGenreName"),
            preview_url=item["previewUrl"],
            external_url=item.get("trackViewUrl"),
        )
        for item in results
        if item.get("kind") == "song" and item.get("previewUrl")
    ]


class ITunesClient:
    """iTunes Search API クライアント。

    認証不要で30秒のプレビュー音源 (AAC/m4a) のURLが取れるため、分析用の音源取得に使う。
    Spotifyは新規アプリだと preview_url が null で返るため音源取得には使えない。
    """

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._country = settings.itunes_country
        self._http = http_client

    async def search_previews(self, term: str, limit: int = 25) -> list[PreviewTrack]:
        """キーワード検索。曲名・アーティスト名への一致で返るため、ジャンル名で探すと
        そのジャンル名を曲名に含むBGM等が多く混ざる点に注意（ジャンルで集めるなら chart_previews）。"""
        response = await self._http.get(
            SEARCH_URL,
            params={
                "term": term,
                "media": "music",
                "entity": "song",
                "limit": limit,
                "country": self._country,
            },
        )
        response.raise_for_status()
        return _parse_tracks(response.json()["results"])

    async def chart_previews(self, genre_id: int, limit: int = 100) -> list[PreviewTrack]:
        """ジャンル別の人気曲チャート（最大100曲程度）をプレビュー付きで取得する。"""
        response = await self._http.get(
            TOP_SONGS_URL.format(country=self._country.lower(), limit=limit, genre_id=genre_id)
        )
        response.raise_for_status()
        entries = response.json()["feed"].get("entry", [])
        # 1件だけのときは配列ではなくオブジェクトで返ってくる
        if isinstance(entries, dict):
            entries = [entries]
        track_ids = [entry["id"]["attributes"]["im:id"] for entry in entries]
        return await self.lookup_previews(track_ids)

    async def lookup_previews(self, track_ids: list[str]) -> list[PreviewTrack]:
        tracks: list[PreviewTrack] = []
        for start in range(0, len(track_ids), _LOOKUP_BATCH):
            response = await self._http.get(
                LOOKUP_URL,
                params={
                    "id": ",".join(track_ids[start : start + _LOOKUP_BATCH]),
                    "country": self._country,
                },
            )
            response.raise_for_status()
            tracks.extend(_parse_tracks(response.json()["results"]))
        return tracks

    async def download_preview(self, preview_url: str) -> bytes:
        response = await self._http.get(preview_url)
        response.raise_for_status()
        return response.content
