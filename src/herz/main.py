from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from herz.api.routes import analyze, health, ingest, search
from herz.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_async_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            app.state.http_client = client
            yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Herz", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(search.router)
    app.include_router(analyze.router)
    app.include_router(ingest.router)
    return app


app = create_app()
