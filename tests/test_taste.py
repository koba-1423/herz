import httpx
from fastapi import FastAPI

from tests.conftest import enable_fake_embedder


async def test_catalog_search_and_add_track(client: httpx.AsyncClient) -> None:
    before = (await client.get("/catalog/search", params={"term": "anything"})).json()
    assert [(song["source_track_id"], song["track_id"]) for song in before] == [
        ("1", None),
        ("2", None),
        ("4", None),
    ]

    added = await client.post("/library/tracks", json={"source_track_id": "1"})
    assert added.status_code == 200
    assert added.json()["id"] == "itunes:1"

    after = (await client.get("/catalog/search", params={"term": "anything"})).json()
    assert after[0]["track_id"] == "itunes:1"


async def test_add_track_without_analyzable_preview_is_404(client: httpx.AsyncClient) -> None:
    response = await client.post("/library/tracks", json={"source_track_id": "2"})  # プレビューが404
    assert response.status_code == 404


async def test_taste_profile_describes_favorites_relative_to_library(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    enable_fake_embedder(app)
    await client.post("/ingest", json={"term": "anything"})

    response = await client.post("/taste", json={"track_ids": ["itunes:1"]})

    assert response.status_code == 200
    profile = response.json()
    assert profile["track_count"] == 1
    assert profile["descriptors"][0]["label"] == "ピアノ"
    assert "piano" not in {d["prompt"] for d in profile["avoided"]}
    tempo = next(feature for feature in profile["features"] if feature["name"] == "tempo_bpm")
    assert tempo["value"] == 70.0
    assert tempo["percentile"] == 0.0  # ライブラリで一番遅い
    assert profile["major_ratio"] == 0.0
    assert profile["recommendations"] == []  # 他の曲は同じアーティスト


async def test_taste_requires_embedder(client: httpx.AsyncClient) -> None:
    response = await client.post("/taste", json={"track_ids": ["itunes:1"]})
    assert response.status_code == 503
