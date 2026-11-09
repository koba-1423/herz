import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from herz.api.routes import analyze, catalog, health, ingest, library, search, taste
from herz.core.config import Settings, get_settings
from herz.core.dependencies import get_audio_text_embedder, get_query_translator
from herz.core.rate_limit import RateLimiter
from herz.services.embeddings import ClapEmbedder
from herz.services.query_translation import NllbTranslator

WEB_DIR = Path(__file__).parent / "web"

logger = logging.getLogger(__name__)


async def _warm_up(model: ClapEmbedder | NllbTranslator) -> None:
    try:
        await asyncio.to_thread(model.warm_up)
    except Exception:
        logger.exception("failed to load model %s", model.model_name)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # CLAP・翻訳モデルの読み込みには数秒〜数十秒かかるため、起動をブロックせず裏で読み込んでおく
    embedder = get_audio_text_embedder(settings)
    fallback = get_query_translator(settings).fallback
    models = [model for model in (embedder, fallback) if isinstance(model, ClapEmbedder | NllbTranslator)]
    warm_ups = [asyncio.create_task(_warm_up(model)) for model in models]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            app.state.http_client = client
            yield
    finally:
        for task in warm_ups:
            task.cancel()
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Herz", lifespan=lifespan)
    app.state.embedding_indexes = {}
    if settings.rate_limit_per_minute > 0:
        limiter = RateLimiter(
            settings.rate_limit_per_minute, settings.rate_limit_heavy_per_minute, settings.trust_proxy_headers
        )
        app.middleware("http")(limiter)
    app.include_router(health.router)
    app.include_router(search.router)
    if settings.admin_enabled:
        app.include_router(analyze.router)
        app.include_router(ingest.router)
    app.include_router(library.router)
    app.include_router(catalog.router)
    app.include_router(taste.router)
    # APIルートに一致しなかったリクエストだけが届くよう、静的ファイルは最後にマウントする
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()
