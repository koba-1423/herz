from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from herz.core.dependencies import HttpClientDep, ITunesClientDep, SessionDep
from herz.models.track import TrackRecord
from herz.schemas.catalog import CatalogSong
from herz.services.ingest import SOURCE
from herz.services.itunes import ITunesClient, PreviewTrack
from herz.services.links import LinkLookup, UnsupportedLinkError, is_link, rank_by_title, resolve_link

router = APIRouter(prefix="/catalog", tags=["catalog"])

# URLの曲を曲名で探すときに取ってくる候補数
_LINK_CANDIDATES = 25


@router.get("/search", response_model=list[CatalogSong])
async def search_catalog(
    session: SessionDep,
    itunes: ITunesClientDep,
    http_client: HttpClientDep,
    response: Response,
    term: str = Query(min_length=1, max_length=1000),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[CatalogSong]:
    """曲名・アーティスト名、または Apple Music / Spotify / YouTube の曲のURLでiTunesのカタログを探す
    （好きな曲やseed曲を選ぶ用）。

    URLのときは、URLから読み取った曲名等を X-Herz-Detected ヘッダ（URLエンコード）で返す。
    ライブラリに取り込み済みの曲には track_id が付く。
    """
    try:
        if is_link(term):
            lookup = await resolve_link(term, http_client)
            if lookup.detected:
                response.headers["X-Herz-Detected"] = quote(lookup.detected)
            previews = await _link_previews(itunes, lookup, limit)
        else:
            previews = await itunes.search_previews(term, limit)
    except UnsupportedLinkError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"lookup failed: {exc}") from exc

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


async def _link_previews(itunes: ITunesClient, lookup: LinkLookup, limit: int) -> list[PreviewTrack]:
    if lookup.track_id:
        return await itunes.lookup_previews([lookup.track_id], country=lookup.country)
    if lookup.album_id:
        return (await itunes.album_previews(lookup.album_id, country=lookup.country))[:limit]
    # 曲名・アーティスト名から探す。確からしい検索語から順に、見つかるまで試す
    for term in lookup.search_terms:
        # 元の曲が別バージョンより下に埋もれていることがあるので、多めに取ってから並べ替える
        if previews := await itunes.search_previews(term, max(limit, _LINK_CANDIDATES)):
            order = rank_by_title([preview.title for preview in previews], term)
            return [previews[i] for i in order[:limit]]
    return []
