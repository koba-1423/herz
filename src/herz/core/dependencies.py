from typing import Annotated

import httpx
from fastapi import Depends, Request

from herz.core.config import Settings, get_settings
from herz.services.spotify import SpotifyClient

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


def get_spotify_client(settings: SettingsDep, http_client: HttpClientDep) -> SpotifyClient:
    return SpotifyClient(settings=settings, http_client=http_client)


SpotifyClientDep = Annotated[SpotifyClient, Depends(get_spotify_client)]
