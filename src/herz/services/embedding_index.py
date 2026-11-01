import asyncio
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from herz.models.track import TrackRecord

# SQLiteの CURRENT_TIMESTAMP は秒単位で、同じ秒に後から書かれた行を取りこぼさないよう少し遡って読み直す
_WATERMARK_OVERLAP = timedelta(seconds=2)


class EmbeddingIndex:
    """ある埋め込みモデルで算出した楽曲の埋め込みをメモリに載せておく索引。

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

    def vector(self, track_id: str) -> np.ndarray | None:
        position = self._positions.get(track_id)
        return None if position is None else self._matrix[position]

    def mean_vector(self) -> np.ndarray | None:
        """ライブラリ全体の平均。好みの分析で「ライブラリ全体と比べてどうか」を測る基準に使う。"""
        return None if not self._ids else self._matrix[: len(self._ids)].mean(axis=0)

    def top(
        self, text_vector: np.ndarray, limit: int, track_ids: set[str] | None = None
    ) -> list[tuple[str, float]]:
        """文との類似度が高い順に最大 limit 件を返す。track_ids を渡すとその楽曲に絞る。"""
        if not self._ids or limit <= 0:
            return []
        similarities = self._matrix[: len(self._ids)] @ text_vector
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
