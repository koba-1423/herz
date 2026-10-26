import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from herz.models import TrackRecord
from herz.schemas.track import TrackFeatures, TrackSearchQuery
from herz.services.track_search import search_tracks


def _record(track_id: str, genre: str | None, features: TrackFeatures) -> TrackRecord:
    record = TrackRecord(
        id=track_id,
        source="itunes",
        source_track_id=track_id,
        title=track_id,
        artist="Artist",
        genre=genre,
    )
    record.apply_features(features)
    return record


@pytest.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncSession:
    async with session_factory() as session:
        session.add_all(
            [
                _record("slow-ballad", "J-Pop", TrackFeatures(tempo_bpm=70, key=9, mode=0, energy=0.2)),
                _record("dance", "Dance", TrackFeatures(tempo_bpm=128, key=0, mode=1, energy=0.9)),
                _record("mid-pop", "J-Pop", TrackFeatures(tempo_bpm=110, key=0, mode=1, energy=0.6)),
                _record("unanalyzed", "J-Pop", TrackFeatures()),
            ]
        )
        await session.commit()
        return session


async def _ids(session: AsyncSession, **conditions: object) -> list[str]:
    return [track.id for track in await search_tracks(session, TrackSearchQuery.model_validate(conditions))]


async def test_no_conditions_returns_everything(session: AsyncSession) -> None:
    assert sorted(await _ids(session)) == ["dance", "mid-pop", "slow-ballad", "unanalyzed"]


async def test_genre_match_is_case_insensitive(session: AsyncSession) -> None:
    assert sorted(await _ids(session, genres=["j-pop"])) == ["mid-pop", "slow-ballad", "unanalyzed"]


async def test_range_conditions_are_inclusive_and_exclude_unanalyzed(session: AsyncSession) -> None:
    assert sorted(await _ids(session, tempo_bpm_min=70, tempo_bpm_max=110)) == ["mid-pop", "slow-ballad"]
    assert await _ids(session, energy_min=0.8) == ["dance"]


async def test_key_and_mode(session: AsyncSession) -> None:
    assert await _ids(session, mode=0) == ["slow-ballad"]
    assert sorted(await _ids(session, key=0, energy_max=0.7)) == ["mid-pop"]


async def test_limit(session: AsyncSession) -> None:
    assert len(await _ids(session, limit=2)) == 2
