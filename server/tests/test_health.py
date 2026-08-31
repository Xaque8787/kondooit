"""Tests for the health endpoint."""

import pytest
from litestar.testing import TestClient

from kondooit.config import Settings


@pytest.fixture
def client() -> TestClient:
    from kondooit.app import create_app
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    with TestClient(app=create_app(settings)) as c:
        yield c


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
