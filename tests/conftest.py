from collections.abc import AsyncIterator

import httpx
import numpy as np
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from herz.core.dependencies import (
    get_audio_feature_extractor,
    get_audio_text_embedder,
    get_http_client,
    get_query_translator,
    get_session,
)
from herz.main import create_app
from herz.models import Base
from herz.schemas.track import TrackFeatures
from herz.services.query_translation import QueryTranslator

# iTunesのモック: 曲ID -> プレビュー音源の中身（None はダウンロードが404になる曲）
PREVIEWS: dict[int, bytes | None] = {1: b"piano", 2: None, 4: b"metal"}
FEATURES = {
    b"piano": TrackFeatures(tempo_bpm=70.0, key=9, mode=0, energy=0.2),
    b"metal": TrackFeatures(tempo_bpm=160.0, key=4, mode=0, energy=0.9),
}


def _itunes_item(track_id: int, preview_url: str | None) -> dict[str, object]:
    return {
        "kind": "song",
        "trackId": track_id,
        "trackName": f"Song {track_id}",
        "artistName": "Artist",
        "primaryGenreName": "J-Pop",
        "previewUrl": preview_url,
        "trackViewUrl": f"https://music.apple.com/jp/song/{track_id}",
    }


def _itunes_handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "itunes.apple.com":
        items = [_itunes_item(track_id, f"https://audio.example/{track_id}.m4a") for track_id in PREVIEWS]
        items.append(_itunes_item(3, None))  # プレビュー無しは候補から除外される
        return httpx.Response(200, json={"results": items})

    track_id = int(request.url.path.strip("/").removesuffix(".m4a"))
    content = PREVIEWS.get(track_id)
    return httpx.Response(200, content=content) if content else httpx.Response(404)


class FakeExtractor:
    def extract(self, audio_bytes: bytes) -> TrackFeatures:
        return FEATURES[audio_bytes]


class FakeEmbedder:
    """'piano' / 'metal' の2軸だけを持つ埋め込み。文中の単語で軸が決まる。"""

    model_name = "fake-clap"
    _AXES = ("piano", "metal")

    def embed_audio(self, audio_bytes: bytes) -> np.ndarray:
        return self._vector(audio_bytes.decode())

    def embed_text(self, text: str) -> np.ndarray:
        return self._vector(text)

    def _vector(self, text: str) -> np.ndarray:
        vector = np.array([1.0 if axis in text else 0.1 for axis in self._AXES], dtype=np.float32)
        return vector / np.linalg.norm(vector)


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False)

    await engine.dispose()


@pytest.fixture
async def app(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[FastAPI]:
    """外部APIとモデルを差し替えたアプリ。埋め込みは既定で無効（テストごとに上書きする）。"""
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async with httpx.AsyncClient(transport=httpx.MockTransport(_itunes_handler)) as http_client:
        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_http_client] = lambda: http_client
        app.dependency_overrides[get_audio_feature_extractor] = FakeExtractor
        app.dependency_overrides[get_audio_text_embedder] = lambda: None
        app.dependency_overrides[get_query_translator] = lambda: (
            QueryTranslator()
        )  # 機械翻訳モデルは読み込まない
        yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


def enable_fake_embedder(app: FastAPI) -> None:
    embedder = FakeEmbedder()
    app.dependency_overrides[get_audio_text_embedder] = lambda: embedder
