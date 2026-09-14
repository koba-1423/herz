import time

import httpx

from herz.core.config import Settings
from herz.schemas.track import Track, TrackFeatures

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"


class SpotifyClient:
    """Spotify Web API のカタログ検索クライアント（Client Credentials Flow）。

    Client Credentials Flowではユーザーデータやaudio-features等の拡張アクセスが
    必要なエンドポイントは利用できない点に注意。ここでは曲メタデータの検索のみを扱う。
    """

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._client_id = settings.spotify_client_id
        self._client_secret = settings.spotify_client_secret
        self._http = http_client
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token

        if not self._client_id or not self._client_secret:
            raise RuntimeError("Spotify client credentials are not configured")

        response = await self._http.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
        )
        response.raise_for_status()
        payload = response.json()

        self._token = payload["access_token"]
        self._token_expires_at = time.monotonic() + payload["expires_in"] - 30
        return self._token

    async def search_tracks(self, query: str, limit: int = 20) -> list[Track]:
        token = await self._get_token()
        response = await self._http.get(
            f"{API_BASE}/search",
            params={"q": query, "type": "track", "limit": limit},
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        items = response.json()["tracks"]["items"]

        return [
            Track(
                id=item["id"],
                title=item["name"],
                artist=", ".join(artist["name"] for artist in item["artists"]),
                preview_url=item.get("preview_url"),
                external_url=item.get("external_urls", {}).get("spotify"),
                features=TrackFeatures(),
            )
            for item in items
        ]
