from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from herz.api.routes import analyze, health, search


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        app.state.http_client = client
        yield


def create_app() -> FastAPI:
    app = FastAPI(title="Herz", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(search.router)
    app.include_router(analyze.router)
    return app


app = create_app()
