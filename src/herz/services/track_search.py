import asyncio
import re
from collections import Counter

import numpy as np
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from herz.models.track import TrackRecord
from herz.schemas.track import TrackSearchQuery, TrackSearchResult
from herz.services.embedding_index import EmbeddingIndex
from herz.services.embeddings import AudioTextEmbedder

# 重複・同じアーティストを間引く前に取っておく候補の倍数
_OVERFETCH = 10
# 埋め込みのコサイン類似度がこれを超える2曲は同じ音源とみなす
_SAME_AUDIO = 0.995

# 歌モノの伴奏だけを収録した版の曲名。元の曲と音がほぼ同じで、似た曲検索の上位を埋めてしまう
_KARAOKE_TITLE = re.compile(
    r"instrumental|off[\s-]?vocal|karaoke|backing track|\binst\.?(?:\)|\]|$)|カラオケ|オリジナル・?カラオケ",
    re.IGNORECASE,
)

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

    if not query.ranks_by_similarity:
        records = await session.scalars(
            statement.order_by(TrackRecord.artist, TrackRecord.title).limit(query.limit)
        )
        return [TrackSearchResult(**record.to_schema().model_dump()) for record in records]

    if embedder is None:
        raise ValueError("similarity search requires an audio-text embedder")
    if index is None:
        index = EmbeddingIndex(embedder.model_name)

    # 埋め込みはベクトルDBを使わずメモリ上で総当たりする（数十万曲規模までは十分速い）。
    # 規模が大きくなったら pgvector 等への移行を検討する
    await index.refresh(session)

    seed_ids = list(dict.fromkeys(query.seed_track_ids or []))
    seeds = list(await session.scalars(select(TrackRecord).where(TrackRecord.id.in_(seed_ids))))
    seed_vectors = [vector for seed in seeds if (vector := index.vector(seed.id)) is not None]
    text_vector = await asyncio.to_thread(embedder.embed_text, query.text) if query.text else None
    query_vector = combine_query_vectors(text_vector, seed_vectors)
    if query_vector is None:
        return []

    track_ids = (
        None
        if statement.whereclause is None
        else set(await session.scalars(statement.with_only_columns(TrackRecord.id)))
    )
    # 重複や同じアーティストの曲を後から間引くので、多めに候補を取っておく
    ranked = index.top(query_vector, query.limit * _OVERFETCH + len(seed_ids), track_ids)
    records_by_id = {
        record.id: record
        for record in await session.scalars(
            select(TrackRecord).where(TrackRecord.id.in_([track_id for track_id, _ in ranked]))
        )
    }

    picker = _DiversePicker(query, seeds, seed_vectors)
    results: list[TrackSearchResult] = []
    for track_id, similarity in ranked:
        record = records_by_id.get(track_id)
        if record is None or not picker.accept(record, index.vector(track_id)):
            continue
        results.append(TrackSearchResult(**record.to_schema().model_dump(), similarity=similarity))
        if len(results) == query.limit:
            break
    return results


def combine_query_vectors(
    text_vector: np.ndarray | None, seed_vectors: list[np.ndarray]
) -> np.ndarray | None:
    """自然文とseed曲の平均を、それぞれ正規化して足し合わせた検索ベクトルにする。"""
    parts = [text_vector] if text_vector is not None else []
    if seed_vectors:
        parts.append(_normalize(np.mean(seed_vectors, axis=0)))
    return _normalize(np.sum(parts, axis=0)) if parts else None


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector if norm == 0 else (vector / norm).astype(np.float32)


class _DiversePicker:
    """検索結果から重複と偏りを取り除く。

    - seed曲そのもの、同じ曲名・アーティスト名の曲、音がほぼ同一の曲（国ごとに別IDで入った同じ音源など）
    - max_per_artist を超えた同じアーティストの曲（BGM系のように似た曲を大量に出すアーティスト対策）
    - exclude_karaoke_versions のとき、カラオケ・インスト版
    """

    def __init__(
        self, query: TrackSearchQuery, seeds: list[TrackRecord], seed_vectors: list[np.ndarray]
    ) -> None:
        self._query = query
        self._seed_ids = set(query.seed_track_ids or [])
        self._seed_artists = {_normalize_name(seed.artist) for seed in seeds}
        self._songs = {_song_key(seed) for seed in seeds}
        self._vectors = list(seed_vectors)
        self._per_artist: Counter[str] = Counter()

    def accept(self, record: TrackRecord, vector: np.ndarray | None) -> bool:
        artist = _normalize_name(record.artist)
        song = _song_key(record)
        if record.id in self._seed_ids or song in self._songs:
            return False
        if self._query.exclude_karaoke_versions and _KARAOKE_TITLE.search(record.title):
            return False
        if self._query.exclude_seed_artists and artist in self._seed_artists:
            return False
        if self._query.max_per_artist and self._per_artist[artist] >= self._query.max_per_artist:
            return False
        if vector is not None and any(float(vector @ other) > _SAME_AUDIO for other in self._vectors):
            return False

        self._songs.add(song)
        self._per_artist[artist] += 1
        if vector is not None:
            self._vectors.append(vector)
        return True


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", "", name).casefold()


def _song_key(record: TrackRecord) -> tuple[str, str]:
    return _normalize_name(record.title), _normalize_name(record.artist)
