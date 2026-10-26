from fastapi import APIRouter

from herz.core.dependencies import SessionDep
from herz.schemas.track import Track, TrackSearchQuery
from herz.services import track_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=list[Track])
async def search_tracks(query: TrackSearchQuery, session: SessionDep) -> list[Track]:
    """雰囲気条件（ジャンル・キー・BPM・energy等の範囲）で取り込み済みの楽曲を検索する。

    検索対象は POST /ingest で解析・保存した楽曲のみ。danceability / valence /
    instrumentalness はv1の分析では算出していないため、これらの条件を指定すると
    現状は結果が空になる（フェーズ2で算出予定）。
    """
    return await track_search.search_tracks(session, query)
