import httpx
from fastapi import FastAPI

from tests.conftest import enable_fake_embedder


async def test_stats_without_embedder(client: httpx.AsyncClient) -> None:
    await client.post("/ingest", json={"term": "anything"})

    stats = (await client.get("/library/stats")).json()

    assert stats == {
        "total_tracks": 2,
        "embedded_tracks": 0,
        "text_search_available": False,
        "embedding_model": None,
    }


async def test_stats_counts_tracks_embedded_with_current_model(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    await client.post("/ingest", json={"term": "anything"})
    enable_fake_embedder(app)
    await client.post("/ingest/embeddings", json={"limit": 1})

    stats = (await client.get("/library/stats")).json()

    assert (stats["total_tracks"], stats["embedded_tracks"], stats["text_search_available"]) == (2, 1, True)


async def test_frontend_is_served_alongside_api(client: httpx.AsyncClient) -> None:
    index = await client.get("/")
    script = await client.get("/app.js")
    health = await client.get("/health")

    assert index.status_code == 200 and "<title>Herz" in index.text
    assert script.status_code == 200 and "javascript" in script.headers["content-type"]
    assert health.json() == {"status": "ok"}
