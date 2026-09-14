from fastapi import APIRouter

from herz.core.dependencies import SpotifyClientDep
from herz.schemas.track import Track, TrackSearchQuery

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=list[Track])
async def search_tracks(query: TrackSearchQuery, spotify: SpotifyClientDep) -> list[Track]:
    """雰囲気条件で楽曲を検索する。

    現時点ではSpotifyカタログ検索（ジャンル・キーワード）のみに対応しており、
    BPM/energy等の音響特徴量による絞り込みは未実装（AudioFeatureProviderの
    実装待ち）。features フィールドは将来ここで埋める。
    """
    search_terms = " ".join(f"genre:{genre}" for genre in (query.genres or []))
    tracks = await spotify.search_tracks(query=search_terms or "*", limit=query.limit)
    return tracks
