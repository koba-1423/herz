import asyncio
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response

from herz.core.dependencies import AudioTextEmbedderDep, EmbeddingIndexDep, QueryTranslatorDep, SessionDep
from herz.schemas.track import TrackSearchQuery, TrackSearchResult
from herz.services import track_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=list[TrackSearchResult])
async def search_tracks(
    query: TrackSearchQuery,
    session: SessionDep,
    embedder: AudioTextEmbedderDep,
    index: EmbeddingIndexDep,
    translator: QueryTranslatorDep,
    response: Response,
) -> list[TrackSearchResult]:
    """雰囲気条件で取り込み済みの楽曲を検索する。

    - ジャンル・キー・BPM・energy等の範囲条件で絞り込む
    - text（自然文）や seed_track_ids（この曲みたいな曲）を指定すると、絞り込んだ楽曲を
      近い順に並べて similarity を付ける。同じ曲の重複は除き、同じアーティストは max_per_artist 曲まで。
      埋め込み未算出の楽曲は対象外（POST /ingest/embeddings で後から算出できる）

    text が日本語なら英語に変換してから検索し、変換後の文を X-Herz-Query ヘッダ（URLエンコード）で返す。

    検索対象は POST /ingest で解析・保存した楽曲のみ。danceability / valence /
    instrumentalness はv1の分析では算出していないため、これらの条件を指定すると
    現状は結果が空になる。
    """
    if query.ranks_by_similarity and embedder is None:
        raise HTTPException(
            status_code=503,
            detail="text search is unavailable: install the `clap` extra and set CLAP_MODEL",
        )
    if query.text is not None:
        english = await asyncio.to_thread(translator.to_english, query.text)
        response.headers["X-Herz-Query"] = quote(english)
        query = query.model_copy(update={"text": english})
    return await track_search.search_tracks(session, query, embedder, index)
