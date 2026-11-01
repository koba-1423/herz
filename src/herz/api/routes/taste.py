from fastapi import APIRouter, HTTPException

from herz.core.dependencies import AudioTextEmbedderDep, EmbeddingIndexDep, SessionDep
from herz.schemas.taste import TasteProfile, TasteRequest
from herz.services.taste import analyze_taste

router = APIRouter(prefix="/taste", tags=["taste"])


@router.post("", response_model=TasteProfile)
async def analyze(
    request: TasteRequest, session: SessionDep, embedder: AudioTextEmbedderDep, index: EmbeddingIndexDep
) -> TasteProfile:
    """好きな曲から、その人の好みの傾向（特徴量・言葉）と、好みに近い別アーティストの曲を返す。

    曲はライブラリに取り込み済みである必要がある（POST /library/tracks で取り込める）。
    """
    if embedder is None or index is None:
        raise HTTPException(
            status_code=503,
            detail="taste analysis is unavailable: install the `clap` extra and set CLAP_MODEL",
        )
    return await analyze_taste(session, request, embedder, index)
