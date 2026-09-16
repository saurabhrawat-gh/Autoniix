"""Smoke tests for services/api/brand."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from services_api.brand.main import app

    return TestClient(app)


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "brand"


def test_brand_endpoints_registered(client):
    routes = {r.path for r in client.app.routes}
    for path in ("/health", "/profile", "/consistency", "/evolution"):
        assert path in routes, f"missing route: {path}"


def test_compute_brand_fingerprint_shape():
    from services_api.brand.brand_dna import compute_brand_fingerprint

    channel = {
        "channel_id": "test-ch",
        "niche": "tech",
        "primary_color": "#1A237E",
        "secondary_color": "#FF6F00",
        "brand_voice": "direct_urgent",
        "content_mode": "short",
    }
    fp = compute_brand_fingerprint(channel)

    assert fp["channel_id"] == "test-ch"
    assert fp["niche"] == "tech"
    assert "color_analysis" in fp
    assert "speaking_style" in fp
    assert "vocabulary" in fp
    assert "pacing_profile" in fp
    assert "visual_identity" in fp
    assert 0.0 <= fp["energy_level"] <= 1.0
    assert 0.0 <= fp["formality_level"] <= 1.0


def test_score_brand_consistency_penalizes_blacklisted_words():
    from services_api.brand.brand_dna import score_brand_consistency

    fingerprint = {
        "vocabulary": {"blacklist": ["forbidden"]},
        "pacing_profile": {"target_wpm": 150},
        "energy_level": 0.7,
        "formality_level": 0.5,
    }
    content = {
        "segments": [
            {"narration": "This is a totally forbidden sentence.", "duration_s": 5, "emphasis_words": []},
        ],
    }
    result = score_brand_consistency(content, fingerprint)
    assert result["consistency_score"] < 10.0
    assert any("forbidden" in d.lower() for d in result["deviations"])


def test_analyze_color_palette_returns_mood():
    from services_api.brand.brand_dna import analyze_color_palette

    result = analyze_color_palette("#1A237E", "#FFFFFF", "#FF6F00")
    assert "primary_mood" in result
    assert "contrast_score" in result
    assert "palette_harmony" in result
    assert result["colors_analyzed"] == 3
