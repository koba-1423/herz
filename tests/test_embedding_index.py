import os

import numpy as np
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from herz.models import Base, TrackRecord
from herz.models.types import EMBEDDING_DIM
from herz.services.embedding_index import EmbeddingIndex, PgVectorIndex, VectorIndex


def _record(track_id: str, vector: list[float], model: str = "m") -> TrackRecord:
    record = TrackRecord(id=track_id, source="itunes", source_track_id=track_id, title=track_id, artist="A")
    padded = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    padded[: len(vector)] = vector
    record.set_embedding(padded, model)
    return record


def _query(*values: float) -> np.ndarray:
    vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vector[: len(values)] = values
    return vector


async def _check_index(index: VectorIndex, factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory() as session:
        session.add_all([_record("a", [1.0, 0.0]), _record("other-model", [1.0, 0.0], model="x")])
        await session.commit()
        assert [i for i, _ in await index.top(session, _query(0.0, 1.0), limit=5)] == ["a"]

        session.add(_record("b", [0.6, 0.8]))
        await session.commit()

        query = _query(0.0, 1.0)
        top = await index.top(session, query, limit=5)
        assert [i for i, _ in top] == ["b", "a"]
        assert top[0][1] == pytest.approx(0.8, abs=1e-5)
        assert [i for i, _ in await index.top(session, query, limit=1)] == ["b"]
        only_a = select(TrackRecord).where(TrackRecord.id == "a")
        assert [i for i, _ in await index.top(session, query, limit=5, where=only_a)] == ["a"]

        mean = await index.mean_vector(session)
        assert mean is not None
        assert mean[:2] == pytest.approx([0.8, 0.4])


async def test_memory_index_reads_new_rows_and_ranks(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _check_index(EmbeddingIndex("m"), session_factory)


@pytest.mark.skipif("TEST_POSTGRES_URL" not in os.environ, reason="TEST_POSTGRES_URL が未設定")
async def test_pgvector_index_ranks_like_memory_index() -> None:
    engine = create_async_engine(os.environ["TEST_POSTGRES_URL"])
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    try:
        await _check_index(PgVectorIndex("m"), async_sessionmaker(engine, expire_on_commit=False))
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()
