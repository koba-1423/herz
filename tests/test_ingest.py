from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from herz.core.dependencies import get_audio_feature_extractor, get_http_client, get_session
from herz.main import create_app
from herz.models import TrackRecord
from herz.schemas.track import TrackFeatures

PREVIEW_OK = "https://audio.example/ok.m4a"
PREVIEW_MISSING = "https://audio.example/missing.m4a"


def _itunes_item(track_id: int, preview_url: str | None, genre: str = "J-Pop") -> dict[str, object]:
    return {
        "kind": "song",
        "trackId": track_id,
        "trackName": f"Song {track_id}",
        "artistName": "Artist",
        "primaryGenreName": genre,
        "previewUrl": preview_url,
        "trackViewUrl": f"https://music.apple.com/jp/song/{track_id}",
    }


def _itunes_handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "itunes.apple.com":
        return httpx.Response(
            200,
            json={
                "results": [
                    _itunes_item(1, PREVIEW_OK),
                    _itunes_item(2, PREVIEW_MISSING),
                    _itunes_item(3, None),  # プレビュー無しは候補から除外される
                ]
            },
        )
    if str(request.url) == PREVIEW_OK:
        return httpx.Response(200, content=b"fake-audio")
    return httpx.Response(404)


class _FakeExtractor:
    def extract(self, audio_bytes: bytes) -> TrackFeatures:
        assert audio_bytes == b"fake-audio"
        return TrackFeatures(tempo_bpm=120.0, key=0, mode=1, energy=0.5)


@pytest.fixture
async def client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async with httpx.AsyncClient(transport=httpx.MockTransport(_itunes_handler)) as http_client:
        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_http_client] = lambda: http_client
        app.dependency_overrides[get_audio_feature_extractor] = _FakeExtractor
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


async def test_ingest_stores_analyzed_tracks(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.post("/ingest", json={"term": "city pop"})

    assert response.status_code == 200
    body = response.json()
    assert [track["id"] for track in body["ingested"]] == ["itunes:1"]
    assert body["ingested"][0]["features"]["tempo_bpm"] == 120.0
    assert body["ingested"][0]["genres"] == ["J-Pop"]
    assert [failure["track_id"] for failure in body["failed"]] == ["itunes:2"]

    async with session_factory() as session:
        stored = (await session.scalars(select(TrackRecord))).all()
    assert [(record.id, record.energy) for record in stored] == [("itunes:1", 0.5)]


async def test_ingest_skips_already_analyzed_tracks(client: httpx.AsyncClient) -> None:
    await client.post("/ingest", json={"term": "city pop"})
    response = await client.post("/ingest", json={"term": "city pop"})

    body = response.json()
    assert body["ingested"] == []
    assert body["skipped_track_ids"] == ["itunes:1"]


async def test_ingested_tracks_are_searchable(client: httpx.AsyncClient) -> None:
    await client.post("/ingest", json={"term": "city pop"})

    hit = await client.post("/search", json={"genres": ["j-pop"], "tempo_bpm_min": 100, "tempo_bpm_max": 130})
    miss = await client.post("/search", json={"tempo_bpm_min": 140})

    assert [track["id"] for track in hit.json()] == ["itunes:1"]
    assert miss.json() == []
