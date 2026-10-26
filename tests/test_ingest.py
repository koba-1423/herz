import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from herz.models import TrackRecord
from tests.conftest import enable_fake_embedder


async def test_ingest_stores_analyzed_tracks(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.post("/ingest", json={"term": "anything"})

    assert response.status_code == 200
    body = response.json()
    assert [track["id"] for track in body["ingested"]] == ["itunes:1", "itunes:4"]
    assert body["ingested"][0]["features"]["tempo_bpm"] == 70.0
    assert body["ingested"][0]["genres"] == ["J-Pop"]
    assert [failure["track_id"] for failure in body["failed"]] == ["itunes:2"]

    async with session_factory() as session:
        stored = (await session.scalars(select(TrackRecord).order_by(TrackRecord.id))).all()
    assert [(record.id, record.energy, record.embedding) for record in stored] == [
        ("itunes:1", 0.2, None),
        ("itunes:4", 0.9, None),
    ]


async def test_ingest_skips_already_analyzed_tracks(client: httpx.AsyncClient) -> None:
    await client.post("/ingest", json={"term": "anything"})
    response = await client.post("/ingest", json={"term": "anything"})

    body = response.json()
    assert body["ingested"] == []
    assert body["skipped_track_ids"] == ["itunes:1", "itunes:4"]


async def test_ingested_tracks_are_searchable(client: httpx.AsyncClient) -> None:
    await client.post("/ingest", json={"term": "anything"})

    hit = await client.post("/search", json={"genres": ["j-pop"], "tempo_bpm_min": 60, "tempo_bpm_max": 80})
    miss = await client.post("/search", json={"tempo_bpm_min": 180})

    assert [track["id"] for track in hit.json()] == ["itunes:1"]
    assert hit.json()[0]["similarity"] is None
    assert miss.json() == []


async def test_ingest_computes_embeddings_when_enabled(
    app: FastAPI, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    enable_fake_embedder(app)
    await client.post("/ingest", json={"term": "anything"})

    async with session_factory() as session:
        stored = (await session.scalars(select(TrackRecord))).all()
    assert {record.embedding_model for record in stored} == {"fake-clap"}
    assert all(
        vector is not None and vector.shape == (2,) for vector in (r.embedding_vector() for r in stored)
    )


async def test_text_search_ranks_by_similarity_within_filters(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    enable_fake_embedder(app)
    await client.post("/ingest", json={"term": "anything"})

    ranked = (await client.post("/search", json={"text": "heavy metal riffs"})).json()
    filtered = (await client.post("/search", json={"text": "heavy metal riffs", "energy_max": 0.5})).json()

    assert [track["id"] for track in ranked] == ["itunes:4", "itunes:1"]
    assert ranked[0]["similarity"] > ranked[1]["similarity"]
    assert [track["id"] for track in filtered] == ["itunes:1"]


async def test_text_search_is_unavailable_without_embedder(client: httpx.AsyncClient) -> None:
    response = await client.post("/search", json={"text": "calm piano"})

    assert response.status_code == 503


async def test_backfill_embeds_tracks_ingested_before_clap(app: FastAPI, client: httpx.AsyncClient) -> None:
    await client.post("/ingest", json={"term": "anything"})
    enable_fake_embedder(app)

    first = (await client.post("/ingest/embeddings", json={"limit": 1})).json()
    second = (await client.post("/ingest/embeddings", json={})).json()
    third = (await client.post("/ingest/embeddings", json={})).json()
    ranked = (await client.post("/search", json={"text": "soft piano"})).json()

    assert first["embedded_track_ids"] == ["itunes:1"]
    assert second["embedded_track_ids"] == ["itunes:4"]
    assert third["embedded_track_ids"] == []
    assert [track["id"] for track in ranked] == ["itunes:1", "itunes:4"]
