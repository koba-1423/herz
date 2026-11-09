"""Apple Music / Spotify / YouTube の曲のURLから、iTunesで曲を探す手がかりを取り出す。

貼られたURLそのものにはアクセスせず、URLから取り出したIDで決まった先（公式の埋め込み用API等）
だけを読みに行く（任意のURLを取得させると、サーバー経由で内部ネットワーク等を覗かれうるため）。
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

_APPLE_HOSTS = {"music.apple.com", "itunes.apple.com", "geo.music.apple.com"}
_SPOTIFY_HOSTS = {"open.spotify.com"}
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}

_ID = re.compile(r"^\d+$")
_SPOTIFY_TRACK = re.compile(r"/track/([A-Za-z0-9]{22})")
_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


class UnsupportedLinkError(ValueError):
    """曲を特定できない種類のURL（プレイリスト・アーティストページ等）。"""


@dataclass(frozen=True)
class LinkLookup:
    service: str  # apple_music / spotify / youtube
    detected: str | None = None  # URLから読み取った「曲名 / アーティスト」（表示用）
    track_id: str | None = None  # iTunesの曲ID（Apple Musicの曲URL）
    album_id: str | None = None  # iTunesのアルバムID（Apple MusicのアルバムURL）
    country: str | None = None
    search_terms: tuple[str, ...] = ()  # iTunesで順に試す検索語（曲IDが分からないとき）


def is_link(text: str) -> bool:
    return bool(re.match(r"^\s*https?://", text))


async def resolve_link(url: str, http: httpx.AsyncClient) -> LinkLookup:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if host in _APPLE_HOSTS:
        return _apple_music(parsed.path, parse_qs(parsed.query))
    if host in _SPOTIFY_HOSTS:
        return await _spotify(parsed.path, http)
    if host in _YOUTUBE_HOSTS:
        return await _youtube(host, parsed.path, parse_qs(parsed.query), http)
    raise UnsupportedLinkError("Apple Music・Spotify・YouTube の曲のURLに対応しています")


def _apple_music(path: str, query: dict[str, list[str]]) -> LinkLookup:
    # /jp/album/{slug}/{albumId}?i={trackId} または /jp/song/{slug}/{trackId}
    segments = [segment for segment in path.split("/") if segment]
    country = segments[0].upper() if segments and len(segments[0]) == 2 else None
    last = segments[-1] if segments else ""
    if (track_id := query.get("i", [""])[0]) and _ID.match(track_id):
        return LinkLookup(service="apple_music", track_id=track_id, country=country)
    if "song" in segments and _ID.match(last):
        return LinkLookup(service="apple_music", track_id=last, country=country)
    if "album" in segments and _ID.match(last):
        return LinkLookup(service="apple_music", album_id=last, country=country)
    raise UnsupportedLinkError("Apple Music は曲かアルバムのURLに対応しています")


async def _spotify(path: str, http: httpx.AsyncClient) -> LinkLookup:
    match = _SPOTIFY_TRACK.search(path)
    if match is None:
        raise UnsupportedLinkError("Spotify は曲（/track/...）のURLに対応しています")
    # 公式の埋め込み用API（oEmbed）。アプリ登録なしで使えるが、分かるのは曲名だけでアーティスト名は返らない
    response = await http.get(
        "https://open.spotify.com/oembed", params={"url": f"https://open.spotify.com/track/{match.group(1)}"}
    )
    response.raise_for_status()
    title = response.json().get("title", "").strip()
    if not title:
        raise UnsupportedLinkError("Spotify の曲情報を読み取れませんでした")
    return LinkLookup(service="spotify", detected=title, search_terms=(title,))


async def _youtube(host: str, path: str, query: dict[str, list[str]], http: httpx.AsyncClient) -> LinkLookup:
    if host == "youtu.be":
        video_id = path.strip("/")
    elif path.startswith("/shorts/"):
        video_id = path.removeprefix("/shorts/").strip("/")
    else:
        video_id = query.get("v", [""])[0]
    if not _YOUTUBE_ID.match(video_id):
        raise UnsupportedLinkError("YouTube は動画（watch?v=...）のURLに対応しています")

    response = await http.get(
        "https://www.youtube.com/oembed",
        params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
    )
    response.raise_for_status()
    info = response.json()
    title, channel = info.get("title", ""), info.get("author_name", "")
    return LinkLookup(service="youtube", detected=title, search_terms=youtube_search_terms(title, channel))


# 動画タイトルに付きがちな、曲名ではない飾り
_VIDEO_NOISE = re.compile(
    r"[\(\[【（](?:[^\)\]】）]*?(?:official|mv|m/v|music video|lyric|video|audio|live|4k|hd|remaster|"
    r"公式|歌詞|ライブ|フル|full)[^\)\]】）]*)[\)\]】）]"
    r"|official\s*(?:music\s*)?video|music\s*video|lyric\s*video|official\s*audio|\bmv\b|\bm/v\b",
    re.IGNORECASE,
)
_CHANNEL_NOISE = re.compile(r"\s*(?:-\s*topic|vevo|official|channel|公式|チャンネル)\s*$", re.IGNORECASE)
_QUOTED = re.compile(r"[「『“\"](.+?)[」』”\"]")


def youtube_search_terms(title: str, channel: str) -> tuple[str, ...]:
    """動画タイトルとチャンネル名から、iTunesで試す検索語を確からしい順に作る。

    例: 'YOASOBI「夜に駆ける」 Official Music Video' → ('夜に駆ける YOASOBI', ...)
        'Rick Astley - Never Gonna Give You Up (Official Video)' → ('Never Gonna Give You Up Rick Astley', ...)
    """
    artist = _CHANNEL_NOISE.sub("", channel).strip()
    cleaned = re.sub(r"\s+", " ", _VIDEO_NOISE.sub(" ", title)).strip(" -/|｜")

    terms: list[str] = []
    if quoted := _QUOTED.search(cleaned):
        song = quoted.group(1).strip()
        before = cleaned[: quoted.start()].strip(" -/|｜") or artist
        terms += [f"{song} {before}".strip(), song]
    parts = [part.strip() for part in re.split(r"\s+[-/|｜]\s+|\s*／\s*", cleaned) if part.strip()]
    if len(parts) >= 2:
        # 「アーティスト - 曲名」と「曲名 / アーティスト」のどちらの並びもあるので両方試す
        terms += [f"{parts[1]} {parts[0]}", f"{parts[0]} {parts[1]}"]
    terms += [f"{cleaned} {artist}".strip() if artist and artist not in cleaned else cleaned, cleaned]
    return tuple(dict.fromkeys(term for term in terms if term))


_VERSION_SUFFIX = re.compile(r"\s*(?:[\(\[（【].*?[\)\]）】]|\s-\s.*)$")


def rank_by_title(titles: list[str], term: str) -> list[int]:
    """検索語に曲名がそのまま含まれる曲を先に、ライブ版・リマスター等の別バージョンを後にした並び順を返す。

    iTunesの検索結果は人気順で、元の曲より別バージョンが先に来ることがあるため。
    """
    normalized_term = term.casefold()

    def score(position: int) -> tuple[int, int, int]:
        title = titles[position].casefold()
        base = _VERSION_SUFFIX.sub("", title).strip()
        mentioned = bool(base) and base in normalized_term
        # 「(Live)」等の付け足しが検索語に無いなら、元の曲ではない別バージョンとみなす
        other_version = title != base and title not in normalized_term
        return (-int(mentioned), int(other_version), position)

    return sorted(range(len(titles)), key=score)
