from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Herz"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://herz:herz@localhost:5432/herz"

    itunes_country: str = "JP"

    # 自然文検索用のCLAPモデル。空文字にすると埋め込みの算出・自然文検索を無効化する
    clap_model: str = "laion/larger_clap_general"

    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None

    apple_music_team_id: str | None = None
    apple_music_key_id: str | None = None
    apple_music_private_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
