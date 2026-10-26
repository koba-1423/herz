from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from herz.models.track import TrackRecord
from herz.schemas.track import Track, TrackSearchQuery

# TrackSearchQuery の `{name}_min` / `{name}_max` と TrackRecord のカラムの対応
_RANGE_FIELDS = (
    "tempo_bpm",
    "energy",
    "danceability",
    "valence",
    "acousticness",
    "instrumentalness",
    "speechiness",
)


def build_search_statement(query: TrackSearchQuery) -> Select[tuple[TrackRecord]]:
    """検索条件をSELECT文に変換する。

    範囲条件を指定した特徴量が未算出 (NULL) の楽曲は、条件を満たすか判断できないため除外する。
    """
    statement = select(TrackRecord)

    if query.genres:
        statement = statement.where(func.lower(TrackRecord.genre).in_([g.lower() for g in query.genres]))
    if query.key is not None:
        statement = statement.where(TrackRecord.key == query.key)
    if query.mode is not None:
        statement = statement.where(TrackRecord.mode == query.mode)

    for field in _RANGE_FIELDS:
        column = getattr(TrackRecord, field)
        lower = getattr(query, f"{field}_min")
        upper = getattr(query, f"{field}_max")
        if lower is not None:
            statement = statement.where(column >= lower)
        if upper is not None:
            statement = statement.where(column <= upper)

    return statement.order_by(TrackRecord.artist, TrackRecord.title).limit(query.limit)


async def search_tracks(session: AsyncSession, query: TrackSearchQuery) -> list[Track]:
    records = await session.scalars(build_search_statement(query))
    return [record.to_schema() for record in records]
