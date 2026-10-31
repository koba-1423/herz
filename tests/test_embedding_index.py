import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from herz.models import TrackRecord
from herz.services.embedding_index import EmbeddingIndex


def _record(track_id: str, vector: list[float], model: str = "m") -> TrackRecord:
    record = TrackRecord(id=track_id, source="itunes", source_track_id=track_id, title=track_id, artist="A")
    record.set_embedding(np.array(vector, dtype=np.float32), model)
    return record


async def test_index_reads_new_rows_incrementally_and_ranks(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    index = EmbeddingIndex("m")
    async with session_factory() as session:
        session.add_all([_record("a", [1.0, 0.0]), _record("other-model", [1.0, 0.0], model="x")])
        await session.commit()
        await index.refresh(session)
        assert len(index) == 1

        session.add(_record("b", [0.6, 0.8]))
        await session.commit()
        await index.refresh(session)

    query = np.array([0.0, 1.0], dtype=np.float32)
    assert [track_id for track_id, _ in index.top(query, limit=5)] == ["b", "a"]
    assert [track_id for track_id, _ in index.top(query, limit=1)] == ["b"]
    assert [track_id for track_id, _ in index.top(query, limit=5, track_ids={"a"})] == ["a"]
