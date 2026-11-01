from pydantic import BaseModel, Field


class CatalogSong(BaseModel):
    """iTunesのカタログ上の曲（ライブラリに取り込む前のものを含む）。"""

    source_track_id: str
    title: str
    artist: str
    genre: str | None = None
    artwork_url: str | None = None
    preview_url: str | None = None
    track_id: str | None = Field(default=None, description="ライブラリに取り込み済みなら、そのID")


class AddTrackRequest(BaseModel):
    source_track_id: str = Field(min_length=1, max_length=64, pattern=r"^\d+$")
