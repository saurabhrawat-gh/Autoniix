"""Smoke tests for services/api/sheets_sync/main.py."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from services_api.sheets_sync.main import app

    return TestClient(app)


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "sheets_sync"


def test_sync_endpoints_registered(client):
    routes = {r.path for r in client.app.routes}
    for path in (
        "/health",
        "/sync/system-config",
        "/sync/output-log",
        "/sync/api-usage",
        "/sync/feedback-loop",
        "/sync/trend-intelligence",
        "/sync/all",
    ):
        assert path in routes, f"missing route: {path}"


def test_sync_without_credentials_returns_503(client, monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "google_sheets_credentials_json", "")

    async def fake_fetch(*_args, **_kwargs):
        return [{"config_key": "k", "config_value": "v", "updated_at": "2026-01-01", "updated_by": "u"}]

    class FakePool:
        async def fetch(self, *args, **kwargs):
            return await fake_fetch(*args, **kwargs)

    from services_api.sheets_sync import main as mod

    async def fake_get_pool():
        return FakePool()

    monkeypatch.setattr(mod, "get_pool", fake_get_pool)

    response = client.post("/sync/system-config")
    assert response.status_code == 503
    assert "credentials" in response.json()["detail"].lower()
