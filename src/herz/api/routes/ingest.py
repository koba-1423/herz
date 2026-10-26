import httpx
from fastapi import APIRouter, HTTPException

from herz.core.dependencies import TrackIngestorDep
from herz.schemas.ingest import IngestRequest, IngestResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_tracks(request: IngestRequest, ingestor: TrackIngestorDep) -> IngestResponse:
    """iTunesでキーワード検索した楽曲のプレビュー音源を解析し、検索対象としてDBに取り込む。

    既に取り込み済みの楽曲は再解析せずスキップする。1曲あたり数秒の解析がかかるため、
    limitを大きくするとレスポンスまで時間がかかる。
    """
    try:
        return await ingestor.ingest(term=request.term, limit=request.limit)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"iTunes search failed: {exc}") from exc
