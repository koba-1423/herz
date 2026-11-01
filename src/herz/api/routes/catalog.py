import httpx
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from herz.core.dependencies import ITunesClientDep, SessionDep
from herz.models.track import TrackRecord
from herz.schemas.catalog import CatalogSong
from herz.services.ingest import SOURCE

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/search", response_model=list[CatalogSong])
async def search_catalog(
    session: SessionDep,
    itunes: ITunesClientDep,
    term: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[CatalogSong]:
    """曲名・アーティスト名でiTunesのカタログを探す（好きな曲やseed曲を選ぶ用）。

    ライブラリに取り込み済みの曲には track_id が付く。
    """
    try:
        previews = await itunes.search_previews(term, limit)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"iTunes search failed: {exc}") from exc

    ids = [f"{SOURCE}:{preview.source_track_id}" for preview in previews]
    in_library = set(await session.scalars(select(TrackRecord.id).where(TrackRecord.id.in_(ids))))
    return [
        CatalogSong(
            source_track_id=preview.source_track_id,
            title=preview.title,
            artist=preview.artist,
            genre=preview.genre,
            artwork_url=preview.artwork_url,
            preview_url=preview.preview_url,
            track_id=track_id if track_id in in_library else None,
        )
        for preview, track_id in zip(previews, ids, strict=True)
    ]
