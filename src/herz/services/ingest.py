import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from herz.models.track import TrackRecord
from herz.schemas.ingest import IngestFailure, IngestResponse
from herz.schemas.track import TrackFeatures
from herz.services.audio_features import AudioFeatureExtractor
from herz.services.itunes import ITunesClient, PreviewTrack

SOURCE = "itunes"

# プレビューのダウンロードと解析(CPU負荷が高い)を同時に走らせる上限
_CONCURRENCY = 4


class TrackIngestor:
    """iTunesで見つけたプレビュー音源を解析し、特徴量付きの楽曲としてDBに保存する。"""

    def __init__(self, session: AsyncSession, itunes: ITunesClient, extractor: AudioFeatureExtractor) -> None:
        self._session = session
        self._itunes = itunes
        self._extractor = extractor
        self._semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def ingest(self, term: str, limit: int) -> IngestResponse:
        candidates = {
            f"{SOURCE}:{preview.source_track_id}": preview
            for preview in await self._itunes.search_previews(term, limit)
        }

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
                failed.append(IngestFailure(track_id=track_id, reason=f"{type(result).__name__}: {result}"))
                continue

            record = TrackRecord(
                id=track_id,
                source=SOURCE,
                source_track_id=preview.source_track_id,
                title=preview.title,
                artist=preview.artist,
                genre=preview.genre,
                preview_url=preview.preview_url,
                external_url=preview.external_url,
            )
            record.apply_features(result)
            records.append(record)

        self._session.add_all(records)
        await self._session.commit()

        return IngestResponse(
            ingested=[record.to_schema() for record in records],
            skipped_track_ids=sorted(existing),
            failed=failed,
        )

    async def _analyze(self, preview: PreviewTrack) -> TrackFeatures:
        async with self._semaphore:
            audio_bytes = await self._itunes.download_preview(preview.preview_url)
            return await asyncio.to_thread(self._extractor.extract, audio_bytes)
