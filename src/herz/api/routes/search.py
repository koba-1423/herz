from fastapi import APIRouter, HTTPException

from herz.core.dependencies import AudioTextEmbedderDep, SessionDep
from herz.schemas.track import TrackSearchQuery, TrackSearchResult
from herz.services import track_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=list[TrackSearchResult])
async def search_tracks(
    query: TrackSearchQuery, session: SessionDep, embedder: AudioTextEmbedderDep
) -> list[TrackSearchResult]:
    """雰囲気条件で取り込み済みの楽曲を検索する。

    - ジャンル・キー・BPM・energy等の範囲条件で絞り込む
    - text（英語の自然文）を指定すると、絞り込んだ楽曲を文との近さ順に並べて similarity を付ける。
      埋め込み未算出の楽曲は対象外（POST /ingest/embeddings で後から算出できる）

    検索対象は POST /ingest で解析・保存した楽曲のみ。danceability / valence /
    instrumentalness はv1の分析では算出していないため、これらの条件を指定すると
    現状は結果が空になる。
    """
    if query.text is not None and embedder is None:
        raise HTTPException(
            status_code=503,
            detail="text search is unavailable: install the `clap` extra and set CLAP_MODEL",
        )
    return await track_search.search_tracks(session, query, embedder)
