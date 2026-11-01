import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Protocol

import numpy as np
from pgvector.sqlalchemy import Vector
from sqlalchemy import Select, bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from herz.models.track import TrackRecord
from herz.models.types import EMBEDDING_DIM

# SQLiteの CURRENT_TIMESTAMP は秒単位で、同じ秒に後から書かれた行を取りこぼさないよう少し遡って読み直す
_WATERMARK_OVERLAP = timedelta(seconds=2)


class VectorIndex(Protocol):
    """ある埋め込みモデルで算出した楽曲の中から、ベクトルに近い曲を探す索引。"""

    model_name: str

    async def top(
        self, session: AsyncSession, vector: np.ndarray, limit: int, where: Select[Any] | None = None
    ) -> list[tuple[str, float]]:
        """コサイン類似度が高い順に最大 limit 件の (楽曲ID, 類似度) を返す。
        where（TrackRecord のSELECT文）を渡すと、その条件に合う曲に絞る。"""
        ...

    async def mean_vector(self, session: AsyncSession) -> np.ndarray | None:
        """ライブラリ全体の平均。好みの分析で「ライブラリ全体と比べてどうか」を測る基準に使う。"""
        ...


class EmbeddingIndex:
    """埋め込みをメモリに載せて総当たりする索引（SQLite等、pgvectorが使えないDB用）。

    検索のたびに全行をDBから読むと曲数に比例して遅くなるため、前回以降に更新された行だけを
    読み足す。削除された楽曲は索引に残るが、検索結果を引くときにDBに無ければ除外される。
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._ids: list[str] = []
        self._positions: dict[str, int] = {}
        self._matrix = np.empty((0, 0), dtype=np.float32)
        self._watermark: datetime | None = None
        self._lock = asyncio.Lock()

    def __len__(self) -> int:
        return len(self._ids)

    async def refresh(self, session: AsyncSession) -> None:
        async with self._lock:
            statement = select(TrackRecord.id, TrackRecord.embedding, TrackRecord.updated_at).where(
                TrackRecord.embedding_model == self.model_name, TrackRecord.embedding.is_not(None)
            )
            if self._watermark is not None:
                statement = statement.where(TrackRecord.updated_at >= self._watermark - _WATERMARK_OVERLAP)
            rows = (await session.execute(statement)).all()
            for track_id, embedding, updated_at in rows:
                self._put(track_id, np.frombuffer(embedding, dtype=np.float32))
                if self._watermark is None or updated_at > self._watermark:
                    self._watermark = updated_at

    async def mean_vector(self, session: AsyncSession) -> np.ndarray | None:
        await self.refresh(session)
        return None if not self._ids else self._matrix[: len(self._ids)].mean(axis=0)

    async def top(
        self, session: AsyncSession, vector: np.ndarray, limit: int, where: Select[Any] | None = None
    ) -> list[tuple[str, float]]:
        await self.refresh(session)
        track_ids = (
            None if where is None else set(await session.scalars(where.with_only_columns(TrackRecord.id)))
        )
        return self._top(vector, limit, track_ids)

    def _top(self, vector: np.ndarray, limit: int, track_ids: set[str] | None) -> list[tuple[str, float]]:
        if not self._ids or limit <= 0:
            return []
        similarities = self._matrix[: len(self._ids)] @ vector
        if track_ids is not None:
            mask = np.zeros(len(self._ids), dtype=bool)
            mask[[self._positions[i] for i in track_ids if i in self._positions]] = True
            similarities = np.where(mask, similarities, -np.inf)
        if limit < len(similarities):
            candidates = np.argpartition(-similarities, limit)[:limit]
        else:
            candidates = np.arange(len(similarities))
        order = candidates[np.argsort(-similarities[candidates])]
        return [(self._ids[i], float(similarities[i])) for i in order if np.isfinite(similarities[i])]

    def _put(self, track_id: str, vector: np.ndarray) -> None:
        if (position := self._positions.get(track_id)) is not None:
            self._matrix[position] = vector
            return
        size = len(self._ids)
        if size == len(self._matrix):
            # 1曲ずつ行列を作り直さないよう、容量を倍々に確保する
            grown = np.empty((max(1024, size * 2), vector.shape[0]), dtype=np.float32)
            if size:
                grown[:size] = self._matrix[:size]
            self._matrix = grown
        self._matrix[size] = vector
        self._ids.append(track_id)
        self._positions[track_id] = size


# 平均ベクトルは全曲の集計で重いので、しばらく使い回す
_MEAN_CACHE_SEC = 600.0


class PgVectorIndex:
    """PostgreSQL の pgvector（HNSW索引）で近い曲を探す索引。"""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._mean: np.ndarray | None = None
        self._mean_at = 0.0

    async def top(
        self, session: AsyncSession, vector: np.ndarray, limit: int, where: Select[Any] | None = None
    ) -> list[tuple[str, float]]:
        if limit <= 0:
            return []
        query_vector = bindparam("query_vector", vector.astype(np.float32), type_=Vector(EMBEDDING_DIM))
        distance = TrackRecord.embedding.op("<=>", return_type=TrackRecord.tempo_bpm.type)(query_vector)
        statement = (
            (where if where is not None else select(TrackRecord))
            .with_only_columns(TrackRecord.id, distance)
            .where(TrackRecord.embedding_model == self.model_name)
            .order_by(distance)
            .limit(limit)
        )
        # 絞り込み条件があっても limit 件集まるまで索引を辿り続けるようにする（pgvector 0.8〜）。
        # 結果の順序は厳密でなくなるが、呼び出し側で類似度順に並べ直す
        await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        await session.execute(text(f"SET LOCAL hnsw.ef_search = {min(1000, max(40, limit))}"))
        rows = (await session.execute(statement)).all()
        return sorted(((track_id, 1.0 - float(d)) for track_id, d in rows), key=lambda row: -row[1])

    async def mean_vector(self, session: AsyncSession) -> np.ndarray | None:
        if self._mean is None or time.monotonic() - self._mean_at > _MEAN_CACHE_SEC:
            mean = await session.scalar(
                select(func.avg(TrackRecord.embedding, type_=Vector(EMBEDDING_DIM))).where(
                    TrackRecord.embedding_model == self.model_name
                )
            )
            self._mean = None if mean is None else np.asarray(mean, dtype=np.float32)
            self._mean_at = time.monotonic()
        return self._mean


def make_vector_index(dialect: str, model_name: str) -> VectorIndex:
    """PostgreSQLなら pgvector の索引、それ以外は埋め込みをメモリに載せる索引を使う。"""
    return PgVectorIndex(model_name) if dialect == "postgresql" else EmbeddingIndex(model_name)
