from fastapi import APIRouter
from sqlalchemy import func, select

from herz.core.dependencies import AudioTextEmbedderDep, SessionDep
from herz.models.track import TrackRecord
from herz.schemas.library import LibraryStats

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/stats", response_model=LibraryStats)
async def library_stats(session: SessionDep, embedder: AudioTextEmbedderDep) -> LibraryStats:
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
    )
