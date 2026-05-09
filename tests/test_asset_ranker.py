"""Unit tests for the asset semantic ranker (Phase 3).

These tests deliberately do NOT require the SBERT model — the ranker
falls back to a Jaccard keyword overlap when ``sentence-transformers``
isn't installed in the CI image, which keeps the tests fast and
deterministic.
"""
from __future__ import annotations

import pytest

from src.services.assets import semantic_ranker as sr


@pytest.fixture(autouse=True)
def _no_sbert(monkeypatch):
    """Force the keyword-overlap fallback path by stubbing the model loader.

    This makes scoring fully deterministic regardless of whether the SBERT
    weights are present in the test environment.
    """
    monkeypatch.setattr(sr, "_get_model", lambda: None)
    yield


def _candidate(**kw):
    base = {
        "source": "pexels",
        "id": "1",
        "url": "https://example.com/clip.mp4",
        "duration": 8.0,
        "width": 1920,
        "height": 1080,
        "tags": "city skyline night",
        "title": "city skyline night",
        "license": "pexels_free",
        "dominant_colors": ["#101820", "#FEE715"],
    }
    base.update(kw)
    return base


def test_perfect_match_scores_above_threshold():
    out = sr.score_candidates(
        query="city skyline night",
        candidates=[_candidate()],
        motion_intent="dynamic",
        target_duration_s=8.0,
        brand_palette=["#101820"],
    )
    assert len(out) == 1
    assert out[0].rejected is False
    assert out[0].final >= 0.7, out[0].as_dict()


def test_irrelevant_query_is_rejected():
    out = sr.score_candidates(
        query="quantum mechanics lecture",
        candidates=[_candidate()],
        motion_intent="dynamic",
        target_duration_s=8.0,
    )
    # Semantic = 0 in fallback mode; license + duration + resolution carry
    # weight but the cap should still be below the 0.55 threshold.
    assert out[0].rejected is True
    assert out[0].final < 0.55, out[0].as_dict()


def test_higher_resolution_beats_lower_when_query_ties():
    sd = _candidate(id="sd", height=480, width=854, tags="city skyline night")
    hd = _candidate(id="hd", height=1080, width=1920, tags="city skyline night")
    out = sr.score_candidates(
        query="city skyline night",
        candidates=[sd, hd],
        target_duration_s=8.0,
    )
    assert out[0].clip["id"] == "hd"


def test_short_clip_penalised_when_target_is_long():
    short = _candidate(id="short", duration=2.0)
    longish = _candidate(id="long", duration=10.0)
    out = sr.score_candidates(
        query="city skyline night",
        candidates=[short, longish],
        target_duration_s=10.0,
    )
    assert out[0].clip["id"] == "long"


def test_brand_palette_match_increases_color_score():
    on_brand = _candidate(id="on", dominant_colors=["#101820", "#FEE715"])
    off_brand = _candidate(id="off", dominant_colors=["#FFFFFF", "#FF00FF"])
    out = sr.score_candidates(
        query="city skyline night",
        candidates=[on_brand, off_brand],
        target_duration_s=8.0,
        brand_palette=["#101820", "#FEE715"],
    )
    on = next(s for s in out if s.clip["id"] == "on")
    off = next(s for s in out if s.clip["id"] == "off")
    assert on.color > off.color


def test_motion_intent_still_prefers_long_clips():
    short = _candidate(id="short", duration=2.0)
    long_ = _candidate(id="long", duration=12.0)
    out = sr.score_candidates(
        query="city skyline night",
        candidates=[short, long_],
        motion_intent="still",
        target_duration_s=10.0,
    )
    short_score = next(s for s in out if s.clip["id"] == "short")
    long_score = next(s for s in out if s.clip["id"] == "long")
    assert long_score.motion > short_score.motion


def test_best_candidate_skips_rejected():
    # Force every candidate-side text to be irrelevant so semantic falls to 0.
    rejected_only = _candidate(
        tags="totally unrelated stuff",
        title="totally unrelated stuff",
    )
    out = sr.score_candidates(
        query="quantum mechanics lecture",
        candidates=[rejected_only],
        target_duration_s=8.0,
    )
    assert sr.best_candidate(out) is None


def test_license_freedom_ordering():
    free = _candidate(id="free", license="pexels_free")
    paid = _candidate(id="paid", license="storyblocks")
    out = sr.score_candidates(
        query="city skyline night",
        candidates=[free, paid],
        target_duration_s=8.0,
    )
    free_s = next(s for s in out if s.clip["id"] == "free")
    paid_s = next(s for s in out if s.clip["id"] == "paid")
    assert free_s.license_ > paid_s.license_
