from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Herz"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://herz:herz@localhost:5432/herz"

    itunes_country: str = "JP"

    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None

    apple_music_team_id: str | None = None
    apple_music_key_id: str | None = None
    apple_music_private_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
