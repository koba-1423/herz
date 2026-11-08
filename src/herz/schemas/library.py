from pydantic import BaseModel, Field


class LibraryStats(BaseModel):
    total_tracks: int = Field(description="取り込み済みの楽曲数")
    embedded_tracks: int = Field(description="現在のモデルで埋め込みを算出済みの楽曲数")
    text_search_available: bool = Field(description="自然文検索 (CLAP) が使えるか")
    embedding_model: str | None = None
    admin_enabled: bool = Field(description="管理用の取り込み・埋め込み計算の API が使えるか")
