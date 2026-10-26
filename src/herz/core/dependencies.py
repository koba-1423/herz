from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from herz.core.config import Settings, get_settings
from herz.services.audio_features import AudioFeatureExtractor
from herz.services.dsp_analysis import DspAudioFeatureExtractor
from herz.services.ingest import TrackIngestor
from herz.services.itunes import ITunesClient
from herz.services.spotify import SpotifyClient

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_spotify_client(settings: SettingsDep, http_client: HttpClientDep) -> SpotifyClient:
    return SpotifyClient(settings=settings, http_client=http_client)


SpotifyClientDep = Annotated[SpotifyClient, Depends(get_spotify_client)]


def get_itunes_client(settings: SettingsDep, http_client: HttpClientDep) -> ITunesClient:
    return ITunesClient(settings=settings, http_client=http_client)


ITunesClientDep = Annotated[ITunesClient, Depends(get_itunes_client)]

_extractor = DspAudioFeatureExtractor()


def get_audio_feature_extractor() -> AudioFeatureExtractor:
    return _extractor


AudioFeatureExtractorDep = Annotated[AudioFeatureExtractor, Depends(get_audio_feature_extractor)]


def get_track_ingestor(
    session: SessionDep, itunes: ITunesClientDep, extractor: AudioFeatureExtractorDep
) -> TrackIngestor:
    return TrackIngestor(session=session, itunes=itunes, extractor=extractor)


TrackIngestorDep = Annotated[TrackIngestor, Depends(get_track_ingestor)]
