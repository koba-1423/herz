from datetime import datetime

import numpy as np
from sqlalchemy import DateTime, Float, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from herz.models.base import Base
from herz.schemas.track import Track, TrackFeatures

FEATURE_FIELDS = tuple(TrackFeatures.model_fields)


class TrackRecord(Base):
    """分析済みの楽曲。主キーは音源ごとのIDを `{source}:{source_track_id}` 形式にしたもの。

    特徴量カラムは TrackFeatures のフィールドと1対1で対応させている（FEATURE_FIELDS）。
    embedding は自然文検索用の音声埋め込み（float32配列のバイト列）で、どのモデルで
    算出したかを embedding_model に残す（モデルが変わったら再計算が必要なため）。
    """

    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    source_track_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    artist: Mapped[str] = mapped_column(String(512))
    source_artist_id: Mapped[str | None] = mapped_column(String(64), index=True)
    genre: Mapped[str | None] = mapped_column(String(128), index=True)
    preview_url: Mapped[str | None] = mapped_column(String(1024))
    external_url: Mapped[str | None] = mapped_column(String(1024))

    tempo_bpm: Mapped[float | None] = mapped_column(Float, index=True)
    key: Mapped[int | None] = mapped_column(Integer)
    mode: Mapped[int | None] = mapped_column(Integer)
    energy: Mapped[float | None] = mapped_column(Float, index=True)
    danceability: Mapped[float | None] = mapped_column(Float)
    valence: Mapped[float | None] = mapped_column(Float)
    acousticness: Mapped[float | None] = mapped_column(Float)
    instrumentalness: Mapped[float | None] = mapped_column(Float)
    speechiness: Mapped[float | None] = mapped_column(Float)
    liveness: Mapped[float | None] = mapped_column(Float)
    loudness_db: Mapped[float | None] = mapped_column(Float)

    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
    embedding_model: Mapped[str | None] = mapped_column(String(128), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def apply_features(self, features: TrackFeatures) -> None:
        for field in FEATURE_FIELDS:
            setattr(self, field, getattr(features, field))

    def set_embedding(self, vector: np.ndarray, model_name: str) -> None:
        self.embedding = vector.astype(np.float32).tobytes()
        self.embedding_model = model_name

    def embedding_vector(self) -> np.ndarray | None:
        return None if self.embedding is None else np.frombuffer(self.embedding, dtype=np.float32)

    def to_schema(self) -> Track:
        return Track(
            id=self.id,
            title=self.title,
            artist=self.artist,
            genres=[self.genre] if self.genre else [],
            preview_url=self.preview_url,
            external_url=self.external_url,
            features=TrackFeatures(**{field: getattr(self, field) for field in FEATURE_FIELDS}),
        )
