import asyncio
from dataclasses import dataclass

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from herz.models.track import TrackRecord
from herz.schemas.ingest import EmbedBackfillResponse, IngestFailure, IngestResponse
from herz.schemas.track import TrackFeatures
from herz.services.audio_features import AudioFeatureExtractor
from herz.services.embeddings import AudioTextEmbedder
from herz.services.itunes import ITunesClient, PreviewTrack

SOURCE = "itunes"

# プレビューのダウンロードと解析(CPU負荷が高い)を同時に走らせる上限
_CONCURRENCY = 4


@dataclass(frozen=True)
class _Analysis:
    features: TrackFeatures
    embedding: np.ndarray | None


class TrackIngestor:
    """iTunesで見つけたプレビュー音源を解析し、特徴量付きの楽曲としてDBに保存する。

    embedder があれば自然文検索用の音声埋め込みも同時に算出する。
    """

    def __init__(
        self,
        session: AsyncSession,
        itunes: ITunesClient,
        extractor: AudioFeatureExtractor,
        embedder: AudioTextEmbedder | None = None,
        concurrency: int = _CONCURRENCY,
    ) -> None:
        self._session = session
        self._itunes = itunes
        self._extractor = extractor
        self._embedder = embedder
        self._semaphore = asyncio.Semaphore(concurrency)

    async def ingest(self, term: str, limit: int) -> IngestResponse:
        return await self.ingest_previews(await self._itunes.search_previews(term, limit))

    async def ingest_chart(self, genre_id: int, limit: int) -> IngestResponse:
        return await self.ingest_previews(await self._itunes.chart_previews(genre_id, limit))

    async def ensure_track(self, source_track_id: str) -> TrackRecord | None:
        """iTunesの曲IDの楽曲をライブラリに取り込んで返す（取り込み済みならそのまま返す）。

        iTunesに無い・プレビューが無い・解析に失敗した場合は None。
        """
        track_id = f"{SOURCE}:{source_track_id}"
        if (record := await self._session.get(TrackRecord, track_id)) is not None:
            return record
        previews = await self._itunes.lookup_previews([source_track_id])
        if not previews:
            return None
        await self.ingest_previews(previews)
        return await self._session.get(TrackRecord, track_id)

    async def ingest_previews(self, previews: list[PreviewTrack]) -> IngestResponse:
        candidates = {f"{SOURCE}:{preview.source_track_id}": preview for preview in previews}

        existing = set(
            await self._session.scalars(select(TrackRecord.id).where(TrackRecord.id.in_(candidates)))
        )
        targets = [
            (track_id, preview) for track_id, preview in candidates.items() if track_id not in existing
        ]

        results = await asyncio.gather(
            *(self._analyze(preview) for _, preview in targets), return_exceptions=True
        )

        records: list[TrackRecord] = []
        failed: list[IngestFailure] = []
        for (track_id, preview), result in zip(targets, results, strict=True):
            if isinstance(result, BaseException):
                failed.append(_failure(track_id, result))
                continue

            record = TrackRecord(
                id=track_id,
                source=SOURCE,
                source_track_id=preview.source_track_id,
                title=preview.title,
                artist=preview.artist,
                source_artist_id=preview.artist_id,
                genre=preview.genre,
                preview_url=preview.preview_url,
                external_url=preview.external_url,
            )
            record.apply_features(result.features)
            if self._embedder is not None and result.embedding is not None:
                record.set_embedding(result.embedding, self._embedder.model_name)
            records.append(record)

        self._session.add_all(records)
        await self._session.commit()

        return IngestResponse(
            ingested=[record.to_schema() for record in records],
            skipped_track_ids=sorted(existing),
            failed=failed,
        )

    async def backfill_embeddings(self, embedder: AudioTextEmbedder, limit: int) -> EmbedBackfillResponse:
        """埋め込みが未算出、または別モデルで算出済みの楽曲について埋め込みを計算し直す。"""
        records = list(
            await self._session.scalars(
                select(TrackRecord)
                .where(TrackRecord.preview_url.is_not(None))
                .where(
                    or_(
                        TrackRecord.embedding_model.is_(None),
                        TrackRecord.embedding_model != embedder.model_name,
                    )
                )
                .order_by(TrackRecord.id)
                .limit(limit)
            )
        )

        results = await asyncio.gather(
            *(self._embed(embedder, record.preview_url) for record in records if record.preview_url),
            return_exceptions=True,
        )

        embedded: list[str] = []
        failed: list[IngestFailure] = []
        for record, result in zip(records, results, strict=True):
            if isinstance(result, BaseException):
                failed.append(_failure(record.id, result))
                continue
            record.set_embedding(result, embedder.model_name)
            embedded.append(record.id)

        await self._session.commit()
        return EmbedBackfillResponse(embedded_track_ids=embedded, failed=failed)

    async def _analyze(self, preview: PreviewTrack) -> _Analysis:
        async with self._semaphore:
            audio_bytes = await self._itunes.download_preview(preview.preview_url)
            features = await asyncio.to_thread(self._extractor.extract, audio_bytes)
            embedding = (
                await asyncio.to_thread(self._embedder.embed_audio, audio_bytes)
                if self._embedder is not None
                else None
            )
            return _Analysis(features=features, embedding=embedding)

    async def _embed(self, embedder: AudioTextEmbedder, preview_url: str) -> np.ndarray:
        async with self._semaphore:
            audio_bytes = await self._itunes.download_preview(preview_url)
            return await asyncio.to_thread(embedder.embed_audio, audio_bytes)


def _failure(track_id: str, error: BaseException) -> IngestFailure:
    return IngestFailure(track_id=track_id, reason=f"{type(error).__name__}: {error}")
