from dataclasses import dataclass

import httpx

from herz.core.config import Settings

SEARCH_URL = "https://itunes.apple.com/search"


@dataclass(frozen=True)
class PreviewTrack:
    source_track_id: str
    title: str
    artist: str
    genre: str | None
    preview_url: str
    external_url: str | None


class ITunesClient:
    """iTunes Search API クライアント。

    認証不要で30秒のプレビュー音源 (AAC/m4a) のURLが取れるため、分析用の音源取得に使う。
    Spotifyは新規アプリだと preview_url が null で返るため音源取得には使えない。
    """

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._country = settings.itunes_country
        self._http = http_client

    async def search_previews(self, term: str, limit: int = 25) -> list[PreviewTrack]:
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

        return [
            PreviewTrack(
                source_track_id=str(item["trackId"]),
                title=item["trackName"],
                artist=item["artistName"],
                genre=item.get("primaryGenreName"),
                preview_url=item["previewUrl"],
                external_url=item.get("trackViewUrl"),
            )
            for item in response.json()["results"]
            if item.get("kind") == "song" and item.get("previewUrl")
        ]

    async def download_preview(self, preview_url: str) -> bytes:
        response = await self._http.get(preview_url)
        response.raise_for_status()
        return response.content
