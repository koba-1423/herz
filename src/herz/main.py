import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from herz.api.routes import analyze, health, ingest, library, search
from herz.core.config import get_settings
from herz.core.dependencies import get_audio_text_embedder
from herz.services.embeddings import ClapEmbedder

WEB_DIR = Path(__file__).parent / "web"

logger = logging.getLogger(__name__)


async def _warm_up_embedder(embedder: ClapEmbedder) -> None:
    try:
        await asyncio.to_thread(embedder.warm_up)
    except Exception:
        logger.exception("failed to load CLAP model %s", embedder.model_name)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # CLAPモデルの読み込みには数秒〜十数秒かかるため、起動をブロックせず裏で読み込んでおく
    embedder = get_audio_text_embedder(settings)
    warm_up = asyncio.create_task(_warm_up_embedder(embedder)) if isinstance(embedder, ClapEmbedder) else None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            app.state.http_client = client
            yield
    finally:
        if warm_up is not None:
            warm_up.cancel()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Herz", lifespan=lifespan)
    app.state.embedding_indexes = {}
    app.include_router(health.router)
    app.include_router(search.router)
    app.include_router(analyze.router)
    app.include_router(ingest.router)
    app.include_router(library.router)
    # APIルートに一致しなかったリクエストだけが届くよう、静的ファイルは最後にマウントする
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()
