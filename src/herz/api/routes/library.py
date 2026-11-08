import httpx
from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from herz.core.dependencies import AudioTextEmbedderDep, SessionDep, SettingsDep, TrackIngestorDep
from herz.models.track import TrackRecord
from herz.schemas.catalog import AddTrackRequest
from herz.schemas.library import LibraryStats
from herz.schemas.track import Track

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/stats", response_model=LibraryStats)
async def library_stats(
    session: SessionDep, embedder: AudioTextEmbedderDep, settings: SettingsDep
) -> LibraryStats:
    """取り込み済みの楽曲数と、自然文検索の対象になっている楽曲数を返す。"""
    total = await session.scalar(select(func.count()).select_from(TrackRecord))
    embedded = (
        await session.scalar(select(func.count()).where(TrackRecord.embedding_model == embedder.model_name))
        if embedder is not None
        else 0
    )
    return LibraryStats(
        total_tracks=total or 0,
        embedded_tracks=embedded or 0,
        text_search_available=embedder is not None,
        embedding_model=embedder.model_name if embedder is not None else None,
        admin_enabled=settings.admin_enabled,
    )


@router.post("/tracks", response_model=Track)
async def add_track(request: AddTrackRequest, ingestor: TrackIngestorDep) -> Track:
    """iTunesの曲IDの曲をライブラリに取り込む（取り込み済みならそのまま返す）。数秒かかる。"""
    try:
        record = await ingestor.ensure_track(request.source_track_id)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"iTunes lookup failed: {exc}") from exc
    if record is None:
        raise HTTPException(status_code=404, detail="track not found or its preview could not be analyzed")
    return record.to_schema()
