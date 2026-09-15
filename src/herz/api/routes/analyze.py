from fastapi import APIRouter, HTTPException, UploadFile

from herz.schemas.track import TrackFeatures
from herz.services.dsp_analysis import DspAudioFeatureExtractor

router = APIRouter(tags=["analyze"])
_extractor = DspAudioFeatureExtractor()


@router.post("/analyze", response_model=TrackFeatures)
async def analyze_track(file: UploadFile) -> TrackFeatures:
    """アップロードされた音声ファイルを解析し、音響特徴量を返す。

    Spotify等の外部音源連携がまだ無くても、手元の音声ファイルで
    分析パイプラインを試せるようにするための動作確認用エンドポイント。
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="empty file")

    try:
        return _extractor.extract(audio_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"failed to analyze audio: {exc}") from exc
