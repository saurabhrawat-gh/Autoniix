"""Unit tests for the strict pre-publish quality gate (Phase 4).

These tests are pure-function — no DB, no LLM, no network. The gate's
:func:`record_decision` is exercised separately via integration tests.
"""

from __future__ import annotations

from quality import (
    PRODUCTION_THRESHOLDS,
    evaluate,
)


def _all_pass_scores() -> dict:
    """Scores that comfortably clear every production floor."""
    return {
        "research_depth_score": 8.5,
        "script_structure_score": 8.5,
        "hook_retention_score": 8.5,
        "voice_quality_score": 8.0,
        "thumbnail_score": 8.5,
        "direction_score": 8.0,
        "production_score": 8.0,
    }


def test_all_floors_pass():
    out = evaluate(_all_pass_scores())
    assert out.passed is True
    assert out.failures == []
    assert out.composite_score >= PRODUCTION_THRESHOLDS["composite_score"]
    assert out.profile == "production"


def test_single_dimension_below_floor_blocks():
    scores = _all_pass_scores()
    scores["voice_quality_score"] = 6.5
    out = evaluate(scores)
    assert out.passed is False
    assert any("voice_quality_score" in f for f in out.failures)


def test_high_scores_in_other_dims_cannot_compensate_for_floor():
    scores = _all_pass_scores()
    scores["hook_retention_score"] = 0.0
    out = evaluate(scores)
    assert out.passed is False
    assert any("hook_retention_score" in f for f in out.failures)


def test_composite_threshold_blocks_even_when_floors_pass():
    scores = {
        "research_depth_score": 7.0,
        "script_structure_score": 7.5,
        "hook_retention_score": 7.5,
        "voice_quality_score": 7.0,
        "thumbnail_score": 7.5,
        "direction_score": 7.0,
        "production_score": 7.0,
    }
    out = evaluate(scores)
    floor_failures = [f for f in out.failures if not f.startswith("composite_score")]
    assert floor_failures == []
    assert any(f.startswith("composite_score") for f in out.failures)
    assert out.passed is False


def test_test_profile_passes_everything():
    out = evaluate({k: 0.0 for k in PRODUCTION_THRESHOLDS if k != "composite_score"}, profile="test")
    assert out.passed is True
    assert out.profile == "test"


def test_missing_dimension_is_treated_as_failure_in_production():
    scores = _all_pass_scores()
    scores.pop("voice_quality_score")
    out = evaluate(scores)
    assert out.passed is False
    assert any("voice_quality_score" in f and "missing" in f for f in out.failures)


def test_unparseable_score_is_zero_not_silently_passed():
    scores = _all_pass_scores()
    scores["thumbnail_score"] = "not_a_number"
    out = evaluate(scores)
    assert out.passed is False
    assert any("thumbnail_score" in f for f in out.failures)


def test_unknown_extra_keys_are_ignored():
    scores = _all_pass_scores()
    scores["mystery_metric"] = 99.0
    out = evaluate(scores)
    assert out.passed is True


def test_decision_dict_is_serialisable():
    out = evaluate(_all_pass_scores())
    d = out.as_dict()
    import json

    json.loads(json.dumps(d))
    assert d["passed"] is True
    assert "composite_score" in d
    assert "sub_scores" in d
