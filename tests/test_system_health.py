"""Phase 12 — system health aggregation tests.

Locks per-subsystem scoring rules, weight invariants, the cold-start
exclusion behaviour, and the traffic-light bands.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.intelligence.system_health import (
    GREEN_THRESHOLD,
    SUBSYSTEM_WEIGHTS,
    YELLOW_THRESHOLD,
    aggregate_health,
    band,
    score_calibration,
    score_db_pool,
    score_diversity_floor,
    score_gate_calibration,
    score_niche_pulse,
    score_pressure_24h,
    score_retention_coverage,
    score_services,
)


def _hours_ago(h: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()


# Weight invariant


def test_subsystem_weights_sum_to_100():
    """Aggregator interprets the score as a percentage. If weights
    don't sum to 100 the headline number stops being meaningful."""
    assert sum(SUBSYSTEM_WEIGHTS.values()) == 100


def test_services_carries_the_most_weight():
    """Operator-impact ordering: 'is anything responding' must outweigh
    every other subsystem, since downed services typically mean
    nothing else can run anyway."""
    services_w = SUBSYSTEM_WEIGHTS["services"]
    for name, weight in SUBSYSTEM_WEIGHTS.items():
        if name != "services":
            assert services_w > weight, (
                f"services ({services_w}) must outweigh {name} ({weight})"
            )


# Bands


def test_band_thresholds():
    assert band(95) == "green"
    assert band(GREEN_THRESHOLD) == "green"
    assert band(GREEN_THRESHOLD - 0.1) == "yellow"
    assert band(YELLOW_THRESHOLD) == "yellow"
    assert band(YELLOW_THRESHOLD - 0.1) == "red"
    assert band(0) == "red"


def test_band_ordering():
    """Strict monotonicity around boundaries — refactors mustn't
    silently swap green/yellow boundaries."""
    assert GREEN_THRESHOLD > YELLOW_THRESHOLD
    assert YELLOW_THRESHOLD > 0


# score_services


def test_services_perfect_when_all_ok():
    score, reason = score_services({"ok_count": 5, "total": 5})
    assert score == 100.0
    assert "all 5" in reason


def test_services_zero_when_all_down():
    score, reason = score_services({"ok_count": 0, "total": 5})
    assert score == 0.0
    assert "5/5" in reason


def test_services_proportional():
    score, _ = score_services({"ok_count": 3, "total": 5})
    assert score == 60.0


def test_services_returns_none_on_no_data():
    """Cold-start: payload missing or empty → no contribution."""
    assert score_services(None)[0] is None
    assert score_services({})[0] is None
    assert score_services({"ok_count": 0, "total": 0})[0] is None


# score_db_pool


def test_db_pool_zero_when_saturated():
    """All connections checked out and at max → operator must be alerted."""
    score, reason = score_db_pool({"size": 20, "idle": 0, "max_size": 20})
    assert score == 0.0
    assert "saturated" in reason


def test_db_pool_full_credit_with_headroom():
    score, _ = score_db_pool({"size": 10, "idle": 7, "max_size": 20})
    assert score == 100.0


def test_db_pool_partial_credit_at_squeeze():
    """30% headroom → full marks; 0% → fail; 15% → middle."""
    score, _ = score_db_pool({"size": 10, "idle": 1, "max_size": 20})
    # 1/10 = 10% headroom → linear band between 0% (0) and 30% (100)
    # → ~33%.
    assert 25 < score < 45


def test_db_pool_empty_pool_scores_full():
    """size=0 → not yet warmed; treat as healthy, not fail."""
    score, _ = score_db_pool({"size": 0, "idle": 0, "max_size": 20})
    assert score == 100.0


# score_pressure_24h


def test_pressure_perfect_when_quiet():
    score, _ = score_pressure_24h({"quality_gate_blocks": 0, "video_failures": 0})
    assert score == 100.0


def test_pressure_zero_when_flooded():
    score, _ = score_pressure_24h({"quality_gate_blocks": 30, "video_failures": 30})
    assert score == 0.0


def test_pressure_failures_weigh_more_than_blocks():
    """A failure indicates a wedged pipeline; a block is the gate
    correctly rejecting work. Failures must dominate."""
    blocks_only, _ = score_pressure_24h({"quality_gate_blocks": 5, "video_failures": 0})
    fails_only, _  = score_pressure_24h({"quality_gate_blocks": 0, "video_failures": 5})
    assert blocks_only > fails_only


def test_pressure_none_on_missing_data():
    assert score_pressure_24h(None)[0] is None
    assert score_pressure_24h({})[0] is None


# score_gate_calibration


def test_gate_calibration_cold_start_returns_none():
    """No niches calibrated yet → exclude from aggregate, don't
    penalise the score."""
    score, _ = score_gate_calibration({"ok": True, "niches_calibrated": 0,
                                        "dims_auto": 0, "dims_default": 0,
                                        "last_run": None})
    assert score is None


def test_gate_calibration_full_credit_when_recent_and_auto():
    """Recent run with 100% auto-calibrated dims → ~100."""
    score, _ = score_gate_calibration({
        "ok": True, "niches_calibrated": 5,
        "dims_auto": 10, "dims_default": 0,
        "last_run": _hours_ago(24),
    })
    assert score is not None and score >= 95


def test_gate_calibration_penalises_stale_run():
    """Same dims, but last run was 2 weeks ago."""
    score, _ = score_gate_calibration({
        "ok": True, "niches_calibrated": 5,
        "dims_auto": 10, "dims_default": 0,
        "last_run": _hours_ago(14 * 24),
    })
    assert score is not None and score < 60


def test_gate_calibration_penalises_default_dims():
    """All dims still on defaults (none auto-calibrated) → low score."""
    score, _ = score_gate_calibration({
        "ok": True, "niches_calibrated": 5,
        "dims_auto": 0, "dims_default": 10,
        "last_run": _hours_ago(24),
    })
    assert score is not None and score < 60


def test_gate_calibration_returns_none_on_error():
    score, _ = score_gate_calibration({"ok": False, "error": "Undef"})
    assert score is None


# score_niche_pulse


def test_niche_pulse_full_credit_when_fresh():
    score, _ = score_niche_pulse({
        "ok": True, "niches_with_data": 5,
        "embedded_rows": 200,
        "last_refresh": _hours_ago(24),
    })
    assert score == 100.0


def test_niche_pulse_zero_when_very_stale():
    score, _ = score_niche_pulse({
        "ok": True, "niches_with_data": 5,
        "embedded_rows": 200,
        "last_refresh": _hours_ago(20 * 24),
    })
    assert score == 0.0


def test_niche_pulse_returns_none_on_cold_start():
    score, _ = score_niche_pulse({"ok": True, "niches_with_data": 0})
    assert score is None


# score_retention_coverage


def test_retention_coverage_full_credit_when_covered():
    score, _ = score_retention_coverage({
        "ok": True, "eligible": 50, "with_curve": 45,
        "coverage": 0.9, "last_fetch": _hours_ago(12),
    })
    assert score == 100.0


def test_retention_coverage_zero_when_wedged():
    """Sub-20% coverage → daily fetch is wedged."""
    score, _ = score_retention_coverage({
        "ok": True, "eligible": 50, "with_curve": 5,
        "coverage": 0.10, "last_fetch": None,
    })
    assert score == 0.0


def test_retention_coverage_none_when_window_empty():
    """No eligible videos yet (cold start) → exclude."""
    score, _ = score_retention_coverage({
        "ok": True, "eligible": 0, "coverage": None,
    })
    assert score is None


# score_diversity_floor


def test_diversity_floor_full_credit_in_healthy_band():
    """Force rate 5-25% is the goldilocks band."""
    score, _ = score_diversity_floor({
        "ok": True, "picks_7d": 100, "forced_7d": 15,
        "force_rate": 0.15,
    })
    assert score == 100.0


def test_diversity_floor_almost_full_credit_at_zero():
    """0% force is *probably* fine but ambiguous; we score 90 so
    operators only get nudged on real problems (high force rate)."""
    score, _ = score_diversity_floor({
        "ok": True, "picks_7d": 100, "forced_7d": 0,
        "force_rate": 0.0,
    })
    assert score == 90.0


def test_diversity_floor_penalises_high_force_rate():
    """Above 25% means we're constantly forcing — collapse or bad
    threshold."""
    score, _ = score_diversity_floor({
        "ok": True, "picks_7d": 100, "forced_7d": 40,
        "force_rate": 0.40,
    })
    assert score is not None and score < 60


def test_diversity_floor_zero_at_very_high_force_rate():
    score, _ = score_diversity_floor({
        "ok": True, "picks_7d": 100, "forced_7d": 60,
        "force_rate": 0.60,
    })
    assert score == 0.0


def test_diversity_floor_returns_none_on_few_picks():
    """Under 5 picks isn't enough signal to score either way."""
    score, _ = score_diversity_floor({
        "ok": True, "picks_7d": 3, "forced_7d": 0, "force_rate": 0.0,
    })
    assert score is None


# score_calibration


def test_calibration_returns_none_when_too_few_predictions():
    """Sub-20 scored predictions → metrics too noisy to act on."""
    score, _ = score_calibration({
        "ok": True, "n": 10, "brier": 0.18, "ece": 0.05,
    })
    assert score is None


def test_calibration_full_credit_when_well_calibrated():
    score, _ = score_calibration({
        "ok": True, "n": 100, "brier": 0.10, "ece": 0.05,
    })
    assert score == 100.0


def test_calibration_zero_when_random_baseline():
    """Brier ≥0.25 means random; ECE ≥0.20 means very miscalibrated."""
    score, _ = score_calibration({
        "ok": True, "n": 100, "brier": 0.25, "ece": 0.20,
    })
    assert score == 0.0


def test_calibration_partial_credit():
    score, _ = score_calibration({
        "ok": True, "n": 100, "brier": 0.18, "ece": 0.10,
    })
    assert score is not None and 30 < score < 80


# aggregate_health (the headline)


def test_aggregate_unknown_when_no_subsystems_report():
    """Total cold start: every subsystem returns None."""
    result = aggregate_health({})
    assert result["score"] is None
    assert result["band"] == "unknown"
    assert result["n_active"] == 0
    assert result["n_total"] == len(SUBSYSTEM_WEIGHTS)


def test_aggregate_excludes_none_subsystems_from_average():
    """A subsystem without data must not pull the score down."""
    payload = {
        # Only services reports — must not be averaged with implicit zeros.
        "services": {"ok_count": 5, "total": 5},
    }
    result = aggregate_health(payload)
    # Score should be 100 (only contributing subsystem is perfect),
    # not 100 * (services_weight / total_weight) = 35.
    assert result["score"] == 100.0
    assert result["band"] == "green"
    assert result["n_active"] == 1


def test_aggregate_weighted_average_with_partial_reporting():
    """services=100 (35w), calibration=0 (16w) → weighted = 3500/(35+16) ≈ 68.6."""
    payload = {
        "services":    {"ok_count": 5, "total": 5},
        "calibration": {"ok": True, "n": 100, "brier": 0.25, "ece": 0.20},
    }
    result = aggregate_health(payload)
    expected = (100 * 35 + 0 * 16) / (35 + 16)
    assert result["score"] == pytest.approx(expected, abs=0.5)
    assert result["n_active"] == 2


def test_aggregate_full_payload_perfect_systems_scores_100():
    payload = {
        "services":   {"ok_count": 5, "total": 5},
        "db_pool":    {"size": 5, "idle": 5, "max_size": 20},
        "pressure_24h": {"quality_gate_blocks": 0, "video_failures": 0},
        "gate_calibration": {"ok": True, "niches_calibrated": 5,
                             "dims_auto": 10, "dims_default": 0,
                             "last_run": _hours_ago(24)},
        "niche_pulse":      {"ok": True, "niches_with_data": 5,
                             "embedded_rows": 200,
                             "last_refresh": _hours_ago(24)},
        "retention_coverage": {"ok": True, "eligible": 50,
                                "with_curve": 45, "coverage": 0.9,
                                "last_fetch": _hours_ago(12)},
        "diversity_floor":  {"ok": True, "picks_7d": 100,
                              "forced_7d": 15, "force_rate": 0.15},
        "calibration":      {"ok": True, "n": 100,
                              "brier": 0.10, "ece": 0.05},
    }
    result = aggregate_health(payload)
    assert result["score"] >= 95
    assert result["band"] == "green"
    assert result["n_active"] == result["n_total"]


def test_aggregate_breakdown_preserves_all_subsystems():
    """Even cold-start subsystems appear in the breakdown so the
    operator can see *what* hasn't reported."""
    payload = {"services": {"ok_count": 5, "total": 5}}
    result = aggregate_health(payload)
    names = {s["name"] for s in result["subsystems"]}
    assert names == set(SUBSYSTEM_WEIGHTS.keys())
    none_count = sum(1 for s in result["subsystems"] if s["score"] is None)
    assert none_count == len(SUBSYSTEM_WEIGHTS) - 1


def test_aggregate_breakdown_weights_match_module_constant():
    """Sanity: the breakdown 'weight' for each subsystem must match
    the module constant. Catches silent reordering."""
    result = aggregate_health({})
    for sub in result["subsystems"]:
        assert sub["weight"] == SUBSYSTEM_WEIGHTS[sub["name"]]


def test_aggregate_red_band_when_critical_systems_down():
    """Services down + DB saturated should land squarely in red."""
    payload = {
        "services": {"ok_count": 0, "total": 5},
        "db_pool":  {"size": 20, "idle": 0, "max_size": 20},
    }
    result = aggregate_health(payload)
    assert result["score"] == 0.0
    assert result["band"] == "red"


def test_aggregate_yellow_band_when_one_critical_down_others_perfect():
    """Services down (35w, score 0) but everything else perfect (65w,
    score 100) → 6500/100 = 65 → yellow."""
    payload = {
        "services":   {"ok_count": 0, "total": 5},
        "db_pool":    {"size": 5, "idle": 5, "max_size": 20},
        "pressure_24h": {"quality_gate_blocks": 0, "video_failures": 0},
        "gate_calibration": {"ok": True, "niches_calibrated": 5,
                             "dims_auto": 10, "dims_default": 0,
                             "last_run": _hours_ago(24)},
        "niche_pulse":      {"ok": True, "niches_with_data": 5,
                             "embedded_rows": 200,
                             "last_refresh": _hours_ago(24)},
        "retention_coverage": {"ok": True, "eligible": 50,
                                "with_curve": 45, "coverage": 0.9,
                                "last_fetch": _hours_ago(12)},
        "diversity_floor":  {"ok": True, "picks_7d": 100,
                              "forced_7d": 15, "force_rate": 0.15},
        "calibration":      {"ok": True, "n": 100,
                              "brier": 0.10, "ece": 0.05},
    }
    result = aggregate_health(payload)
    assert 50 <= result["score"] < 80
    assert result["band"] == "yellow"


def test_aggregate_monotonic_in_subsystem_quality():
    """Improving any subsystem's quality must never lower the score —
    the headline number is monotone in subsystem quality. This is
    the property an operator implicitly relies on when triaging."""
    base = {
        "services":   {"ok_count": 4, "total": 5},   # 80
        "db_pool":    {"size": 5, "idle": 1, "max_size": 20},
        "pressure_24h": {"quality_gate_blocks": 5, "video_failures": 2},
    }
    base_score = aggregate_health(base)["score"]

    improved = dict(base)
    improved["services"] = {"ok_count": 5, "total": 5}   # 100
    improved_score = aggregate_health(improved)["score"]

    assert improved_score >= base_score


# Reason strings (sanity)


def test_reasons_are_concise_and_human_readable():
    """Reason strings appear in the breakdown UI; they must be short
    and not contain debug noise like exception class names."""
    payload = {
        "services":      {"ok_count": 3, "total": 5},
        "db_pool":       {"size": 5, "idle": 1, "max_size": 20},
        "pressure_24h":  {"quality_gate_blocks": 2, "video_failures": 1},
        "diversity_floor": {"ok": True, "picks_7d": 100,
                            "forced_7d": 15, "force_rate": 0.15},
    }
    result = aggregate_health(payload)
    for sub in result["subsystems"]:
        # Every reason fits on a single line in the UI.
        assert len(sub["reason"]) < 80, f"reason too long: {sub['reason']!r}"
        # No tracebacks or raw exception text.
        assert "Traceback" not in sub["reason"]
