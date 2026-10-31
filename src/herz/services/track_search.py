import asyncio

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from herz.models.track import TrackRecord
from herz.schemas.track import TrackSearchQuery, TrackSearchResult
from herz.services.embedding_index import EmbeddingIndex
from herz.services.embeddings import AudioTextEmbedder

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


def build_filter_statement(query: TrackSearchQuery) -> Select[tuple[TrackRecord]]:
    """自然文以外の検索条件をSELECT文に変換する（並び順・件数制限は含まない）。

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

    return statement


async def search_tracks(
    session: AsyncSession,
    query: TrackSearchQuery,
    embedder: AudioTextEmbedder | None = None,
    index: EmbeddingIndex | None = None,
) -> list[TrackSearchResult]:
    """index を渡すと、自然文検索の埋め込みをその索引から引く（渡さなければ毎回DBから読む）。"""
    statement = build_filter_statement(query)

    if query.text is None:
        records = await session.scalars(
            statement.order_by(TrackRecord.artist, TrackRecord.title).limit(query.limit)
        )
        return [TrackSearchResult(**record.to_schema().model_dump()) for record in records]

    if embedder is None:
        raise ValueError("text search requires an audio-text embedder")
    if index is None:
        index = EmbeddingIndex(embedder.model_name)

    # 埋め込みはベクトルDBを使わずメモリ上で総当たりする（数十万曲規模までは十分速い）。
    # 規模が大きくなったら pgvector 等への移行を検討する
    await index.refresh(session)
    track_ids = (
        None
        if statement.whereclause is None
        else set(await session.scalars(statement.with_only_columns(TrackRecord.id)))
    )
    text_vector = await asyncio.to_thread(embedder.embed_text, query.text)
    ranked = index.top(text_vector, query.limit, track_ids)

    records_by_id = {
        record.id: record
        for record in await session.scalars(
            select(TrackRecord).where(TrackRecord.id.in_([track_id for track_id, _ in ranked]))
        )
    }
    return [
        TrackSearchResult(**records_by_id[track_id].to_schema().model_dump(), similarity=similarity)
        for track_id, similarity in ranked
        if track_id in records_by_id
    ]
