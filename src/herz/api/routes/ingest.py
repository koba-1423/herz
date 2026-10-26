import httpx
from fastapi import APIRouter, HTTPException

from herz.core.dependencies import AudioTextEmbedderDep, TrackIngestorDep
from herz.schemas.ingest import EmbedBackfillRequest, EmbedBackfillResponse, IngestRequest, IngestResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_tracks(request: IngestRequest, ingestor: TrackIngestorDep) -> IngestResponse:
    """iTunesでキーワード検索した楽曲のプレビュー音源を解析し、検索対象としてDBに取り込む。

    既に取り込み済みの楽曲は再解析せずスキップする。CLAPが有効なら自然文検索用の埋め込みも
    同時に算出する。1曲あたり数秒の解析がかかるため、limitを大きくするとレスポンスまで時間がかかる。
    """
    try:
        return await ingestor.ingest(term=request.term, limit=request.limit)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"iTunes search failed: {exc}") from exc


@router.post("/embeddings", response_model=EmbedBackfillResponse)
async def backfill_embeddings(
    request: EmbedBackfillRequest, ingestor: TrackIngestorDep, embedder: AudioTextEmbedderDep
) -> EmbedBackfillResponse:
    """埋め込みが未算出（またはモデル変更前に算出した）楽曲の埋め込みをプレビュー音源から計算する。

    CLAP導入前に取り込んだ楽曲を自然文検索の対象にするために使う。残りがあれば繰り返し呼ぶ。
    """
    if embedder is None:
        raise HTTPException(
            status_code=503,
            detail="embeddings are unavailable: install the `clap` extra and set CLAP_MODEL",
        )
    return await ingestor.backfill_embeddings(embedder, limit=request.limit)
