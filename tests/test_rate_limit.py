from fastapi import FastAPI
from fastapi.testclient import TestClient

from herz.core.config import Settings
from herz.core.rate_limit import RateLimiter
from herz.main import create_app


def test_allows_again_after_a_minute() -> None:
    limiter = RateLimiter(per_minute=2, heavy_per_minute=1)

    assert [limiter.allow("1.1.1.1", heavy=False, now=t) for t in (0, 1, 2)] == [True, True, False]
    assert limiter.allow("2.2.2.2", heavy=False, now=2)  # 別の人は別に数える
    assert limiter.allow("1.1.1.1", heavy=True, now=2)  # 曲の取り込みは別に数える
    assert limiter.allow("1.1.1.1", heavy=False, now=60)


def test_search_api_returns_429_but_pages_are_not_counted() -> None:
    app = FastAPI()
    app.middleware("http")(RateLimiter(per_minute=1, heavy_per_minute=1))
    app.post("/search")(lambda: {"ok": True})
    app.get("/")(lambda: "page")
    client = TestClient(app)

    for _ in range(3):
        assert client.get("/").status_code == 200
    first = client.post("/search")
    second = client.post("/search")

    assert first.status_code == 200
    assert second.status_code == 429 and "少し待って" in second.json()["detail"]


def test_limiter_is_off_by_default() -> None:
    assert not create_app().user_middleware
    assert create_app(Settings(rate_limit_per_minute=30)).user_middleware
