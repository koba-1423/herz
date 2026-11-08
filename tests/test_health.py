from fastapi.testclient import TestClient

from herz.core.config import Settings
from herz.main import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_admin_routes_are_left_out_when_disabled() -> None:
    paths = create_app(Settings(admin_enabled=False)).openapi()["paths"]

    assert "/ingest" not in paths and "/ingest/embeddings" not in paths and "/analyze" not in paths
    assert "/search" in paths and "/library/tracks" in paths
