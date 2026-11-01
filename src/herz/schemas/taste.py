from pydantic import BaseModel, Field

from herz.schemas.track import TrackSearchResult


class TasteRequest(BaseModel):
    track_ids: list[str] = Field(min_length=1, max_length=100, description="好きな曲（ライブラリのID）")
    recommendation_limit: int = Field(default=20, ge=0, le=100)


class FeatureInsight(BaseModel):
    name: str
    label: str
    value: float = Field(description="好きな曲の平均")
    percentile: float = Field(description="ライブラリ全体の中で何%の曲より大きいか (0〜100)")


class Descriptor(BaseModel):
    label: str = Field(description="表示用の言葉")
    prompt: str = Field(description="CLAPに渡した英語の文")
    score: float = Field(description="ライブラリ全体と比べてどれだけその方向に寄っているか")


class TasteProfile(BaseModel):
    track_count: int = Field(description="分析できた曲数（埋め込みの無い曲は除く）")
    features: list[FeatureInsight]
    major_ratio: float | None = Field(default=None, description="長調の曲の割合 (0〜1)")
    descriptors: list[Descriptor] = Field(description="好みをよく表す言葉（強い順）")
    avoided: list[Descriptor] = Field(description="好きな曲にあまり無い傾向")
    recommendations: list[TrackSearchResult] = Field(description="好みに近い、別のアーティストの曲")
