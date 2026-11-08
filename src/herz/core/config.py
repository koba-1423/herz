from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Herz"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://herz:herz@localhost:5432/herz"

    itunes_country: str = "JP"

    # キーワードでの取り込み・埋め込みの計算・音声ファイルの解析の API と、画面の管理用の欄を出すか。
    # 誰でも重い処理を走らせられてしまうので、公開するサーバーでは false にする
    admin_enabled: bool = True

    # 自然文検索用のCLAPモデル。空文字にすると埋め込みの算出・自然文検索を無効化する
    clap_model: str = "laion/larger_clap_general"
    # 日本語の検索文のうち、音楽の言葉の辞書で拾えなかったものを英訳する機械翻訳モデル（空文字で無効）
    translation_model: str = "facebook/nllb-200-distilled-600M"

    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None

    apple_music_team_id: str | None = None
    apple_music_key_id: str | None = None
    apple_music_private_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
