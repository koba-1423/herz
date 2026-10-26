from pydantic import BaseModel, Field

from herz.schemas.track import Track


class IngestRequest(BaseModel):
    term: str = Field(min_length=1, description="iTunesで検索するキーワード（ジャンル名・曲名など）")
    limit: int = Field(default=25, ge=1, le=200, description="取り込む候補の最大件数")


class IngestFailure(BaseModel):
    track_id: str
    reason: str


class IngestResponse(BaseModel):
    ingested: list[Track]
    skipped_track_ids: list[str] = Field(description="既に分析済みのため取り込みを省略した楽曲")
    failed: list[IngestFailure]
