from pydantic import BaseModel, Field


class TrackFeatures(BaseModel):
    """Sonic characteristics of a track, independent of artist/label/era metadata."""

    tempo_bpm: float | None = Field(default=None, description="推定テンポ (BPM)")
    key: int | None = Field(
        default=None, ge=-1, le=11, description="推定キー (Pitch Class, 0=C ... 11=B, -1=不明)"
    )
    mode: int | None = Field(default=None, ge=0, le=1, description="0=マイナー, 1=メジャー")
    energy: float | None = Field(default=None, ge=0, le=1, description="音の激しさ・強度")
    danceability: float | None = Field(default=None, ge=0, le=1, description="リズムの踊りやすさ")
    valence: float | None = Field(default=None, ge=0, le=1, description="曲の明るさ・ポジティブさ")
    acousticness: float | None = Field(default=None, ge=0, le=1, description="アコースティック度")
    instrumentalness: float | None = Field(default=None, ge=0, le=1, description="ボーカルの有無・少なさ")
    speechiness: float | None = Field(default=None, ge=0, le=1, description="声・話し言葉らしさ")
    liveness: float | None = Field(default=None, ge=0, le=1, description="ライブ感")
    loudness_db: float | None = Field(default=None, description="平均音圧 (dB)")


class Track(BaseModel):
    id: str
    title: str
    artist: str
    genres: list[str] = Field(default_factory=list)
    preview_url: str | None = None
    external_url: str | None = None
    features: TrackFeatures = Field(default_factory=TrackFeatures)


class TrackSearchQuery(BaseModel):
    """雰囲気ベースの検索条件。アーティスト名/レーベル/年代は意図的に含まない。"""

    text: str | None = Field(
        default=None,
        min_length=1,
        max_length=300,
        description="曲の雰囲気を表す自然文（英語）。指定すると他の条件で絞り込んだ上で近い順に並べる",
    )
    seed_track_ids: list[str] | None = Field(
        default=None,
        max_length=100,
        description="この曲（たち）に雰囲気が近い順に並べる。text と併用すると両方に近い曲を探す",
    )
    genres: list[str] | None = None
    key: int | None = Field(default=None, ge=0, le=11, description="キー (Pitch Class, 0=C ... 11=B)")
    mode: int | None = Field(default=None, ge=0, le=1, description="0=マイナー, 1=メジャー")
    tempo_bpm_min: float | None = None
    tempo_bpm_max: float | None = None
    energy_min: float | None = Field(default=None, ge=0, le=1)
    energy_max: float | None = Field(default=None, ge=0, le=1)
    danceability_min: float | None = Field(default=None, ge=0, le=1)
    danceability_max: float | None = Field(default=None, ge=0, le=1)
    valence_min: float | None = Field(default=None, ge=0, le=1)
    valence_max: float | None = Field(default=None, ge=0, le=1)
    acousticness_min: float | None = Field(default=None, ge=0, le=1)
    acousticness_max: float | None = Field(default=None, ge=0, le=1)
    instrumentalness_min: float | None = Field(default=None, ge=0, le=1)
    instrumentalness_max: float | None = Field(default=None, ge=0, le=1)
    speechiness_min: float | None = Field(default=None, ge=0, le=1)
    speechiness_max: float | None = Field(default=None, ge=0, le=1)
    max_per_artist: int | None = Field(
        default=2,
        ge=1,
        description="雰囲気で並べるとき、同じアーティストの曲を何曲まで出すか（null で制限なし）",
    )
    exclude_seed_artists: bool = Field(
        default=False, description="seed曲と同じアーティストの曲を除く（知らない曲を見つけたいとき用）"
    )
    limit: int = Field(default=20, ge=1, le=100)

    @property
    def ranks_by_similarity(self) -> bool:
        return self.text is not None or bool(self.seed_track_ids)


class TrackSearchResult(Track):
    similarity: float | None = Field(
        default=None,
        description="text / seed_track_ids を指定した場合の、検索条件と曲のコサイン類似度 (-1〜1)",
    )
