import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from herz.models import TrackRecord
from herz.schemas.track import TrackSearchQuery
from herz.services.track_search import search_tracks
from tests.conftest import FakeEmbedder


def _record(track_id: str, artist: str, vector: list[float], title: str | None = None) -> TrackRecord:
    record = TrackRecord(
        id=track_id, source="itunes", source_track_id=track_id, title=title or track_id, artist=artist
    )
    vec = np.array(vector, dtype=np.float32)
    record.set_embedding(vec / np.linalg.norm(vec), FakeEmbedder.model_name)
    return record


async def _search(session_factory: async_sessionmaker[AsyncSession], **conditions: object) -> list[str]:
    async with session_factory() as session:
        results = await search_tracks(session, TrackSearchQuery.model_validate(conditions), FakeEmbedder())
    return [result.id for result in results]


async def test_seed_search_ranks_by_audio_and_removes_duplicates_and_floods(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add_all(
            [
                _record("seed", "Seed Band", [1.0, 0.0]),
                _record("seed-other-country", "SEED BAND", [0.9, 0.1], title="SEED"),  # 同じ曲の別ID
                _record("bgm-1", "BGM Factory", [1.0, 0.2]),
                _record("bgm-2", "BGM Factory", [1.0, 0.5]),
                _record("bgm-3", "BGM Factory", [1.0, 0.8]),
                _record("bgm-3-copy", "Other Label", [1.0, 0.81]),  # bgm-3 と音がほぼ同一
                _record("far", "Metal Band", [0.0, 1.0]),
            ]
        )
        await session.commit()

    ranked = await _search(session_factory, seed_track_ids=["seed"], limit=10)
    assert ranked == ["bgm-1", "bgm-2", "bgm-3-copy", "far"]  # 同じアーティストは2曲まで

    unlimited = await _search(session_factory, seed_track_ids=["seed"], max_per_artist=None, limit=10)
    assert unlimited == ["bgm-1", "bgm-2", "bgm-3", "far"]  # 同一音源の bgm-3-copy は除外

    discovery = await _search(
        session_factory, seed_track_ids=["seed"], exclude_seed_artists=True, max_per_artist=1, limit=10
    )
    assert discovery == ["bgm-1", "bgm-3-copy", "far"]


async def test_seed_and_text_are_combined(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        session.add_all(
            [
                _record("seed", "A", [1.0, 0.0]),
                _record("piano-ish", "B", [0.95, 0.3]),
                _record("between", "C", [0.7, 0.7]),
                _record("metal", "D", [0.0, 1.0]),
            ]
        )
        await session.commit()

    assert (await _search(session_factory, seed_track_ids=["seed"], limit=1)) == ["piano-ish"]
    assert (await _search(session_factory, seed_track_ids=["seed"], text="metal", limit=1)) == ["between"]


async def test_unknown_seed_returns_nothing(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        session.add(_record("a", "A", [1.0, 0.0]))
        await session.commit()

    assert await _search(session_factory, seed_track_ids=["missing"]) == []


async def test_karaoke_versions_are_excluded_by_default(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add_all(
            [
                _record("seed", "A", [1.0, 0.0]),
                _record("off-vocal", "B", [1.0, 0.2], title="Song (off vocal)"),
                _record("inst", "C", [1.0, 0.5], title="Song (Inst.)"),
                _record("karaoke", "D", [1.0, 0.8], title="歌 (オリジナル・カラオケ)"),
                _record("institute", "E", [1.0, 1.5], title="Institute of Sound"),
            ]
        )
        await session.commit()

    assert await _search(session_factory, seed_track_ids=["seed"]) == ["institute"]
    assert len(await _search(session_factory, seed_track_ids=["seed"], exclude_karaoke_versions=False)) == 4
