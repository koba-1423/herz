import asyncio

import numpy as np
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from herz.models.track import TrackRecord
from herz.schemas.track import TrackSearchQuery, TrackSearchResult
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
    session: AsyncSession, query: TrackSearchQuery, embedder: AudioTextEmbedder | None = None
) -> list[TrackSearchResult]:
    statement = build_filter_statement(query)

    if query.text is None:
        records = await session.scalars(
            statement.order_by(TrackRecord.artist, TrackRecord.title).limit(query.limit)
        )
        return [TrackSearchResult(**record.to_schema().model_dump()) for record in records]

    if embedder is None:
        raise ValueError("text search requires an audio-text embedder")

    # 埋め込みはベクトルDBを使わずアプリ側で総当たりする（数万曲規模までは十分速い）。
    # 規模が大きくなったら pgvector 等への移行を検討する
    records = await session.scalars(statement.where(TrackRecord.embedding_model == embedder.model_name))
    candidates = [(record, vector) for record in records if (vector := record.embedding_vector()) is not None]
    if not candidates:
        return []

    text_vector = await asyncio.to_thread(embedder.embed_text, query.text)
    similarities = np.stack([vector for _, vector in candidates]) @ text_vector
    ranked = np.argsort(-similarities)[: query.limit]

    return [
        TrackSearchResult(**candidates[i][0].to_schema().model_dump(), similarity=float(similarities[i]))
        for i in ranked
    ]
