"""Phase 8 — niche-saturation scorer tests.

The scorer is split deliberately: a pure function over already-fetched
``_PulseRow`` objects (tested here) and a DB wrapper (tested via the
existing integration suite). This file only exercises the math so the
contract is locked even if pgvector or the embedding model changes.
"""
from __future__ import annotations

import pytest

from src.services.research.saturation import (
    COSINE_THRESHOLD,
    SaturationResult,
    TOP_K,
    VELOCITY_REFERENCE,
    _PulseRow,
    _recency_decay,
    _velocity_factor,
    compute_saturation_from_pulse,
)




def test_empty_pulse_returns_cold_start():
    res = compute_saturation_from_pulse([])
    assert res.cold_start is True
    assert res.saturation == 0.0
    assert res.saturation_gap == 1.0
    assert res.n_matches == 0


def test_pulse_with_no_matches_returns_zero_saturation():
    """Niche has data but nothing matches our candidate. The candidate
    is in unexplored territory — opportunity scorer should not penalise."""
    rows = [
        _PulseRow(similarity=0.20, view_velocity=1000, age_days=1.0),
        _PulseRow(similarity=0.30, view_velocity=2000, age_days=2.0),
        _PulseRow(similarity=0.40, view_velocity=500,  age_days=5.0),
    ]
    res = compute_saturation_from_pulse(rows)
    assert res.cold_start is False
    assert res.n_matches == 0
    assert res.saturation_gap == 1.0




def test_single_perfect_match_with_viral_velocity_pushes_saturation_up():
    """One perfect-match recent viral video should produce meaningful
    saturation but not max it out — that's reserved for ≥5 such matches."""
    rows = [
        _PulseRow(similarity=0.95, view_velocity=VELOCITY_REFERENCE, age_days=0.5),
    ]
    res = compute_saturation_from_pulse(rows)
    assert res.n_matches == 1
    assert 0.10 <= res.saturation <= 0.30
    assert res.saturation_gap == round(1 - res.saturation, 4)


def test_many_perfect_matches_saturate():
    """≥5 perfect-match recent viral videos → saturation clips at 1.0."""
    rows = [
        _PulseRow(similarity=1.0, view_velocity=VELOCITY_REFERENCE, age_days=0.0)
        for _ in range(8)
    ]
    res = compute_saturation_from_pulse(rows)
    assert res.saturation == 1.0
    assert res.saturation_gap == 0.0
    assert res.n_matches == min(8, TOP_K)




def test_old_matches_contribute_less_than_recent():
    """A 14-day-old perfect match must contribute meaningfully less
    than a 1-day-old one. Exponential decay with 7-day half life."""
    fresh = [_PulseRow(similarity=0.9, view_velocity=2000, age_days=1.0)]
    old   = [_PulseRow(similarity=0.9, view_velocity=2000, age_days=14.0)]
    fresh_res = compute_saturation_from_pulse(fresh)
    old_res   = compute_saturation_from_pulse(old)
    assert fresh_res.saturation > old_res.saturation
    assert fresh_res.saturation >= old_res.saturation * 3.0


def test_recency_decay_monotone_decreasing():
    last = _recency_decay(0.0)
    for d in [0.5, 1.0, 3.0, 7.0, 14.0, 30.0]:
        cur = _recency_decay(d)
        assert cur <= last
        last = cur
    assert 0.45 < _recency_decay(7.0) < 0.55




def test_velocity_factor_log_scaled():
    """A 10× velocity difference must NOT become a 10× factor difference;
    one outlier viral video should not drown out 5 mid-velocity matches."""
    low  = _velocity_factor(100)
    mid  = _velocity_factor(1_000)
    high = _velocity_factor(10_000)
    assert low < mid < high
    assert (mid - low) < 0.6
    assert (high - mid) < 0.6


def test_zero_velocity_contributes_zero():
    rows = [_PulseRow(similarity=0.99, view_velocity=0, age_days=0.0)]
    res = compute_saturation_from_pulse(rows)
    assert res.saturation == 0.0




def test_below_cosine_threshold_treated_as_no_match():
    eps = 0.01
    rows = [
        _PulseRow(similarity=COSINE_THRESHOLD - eps, view_velocity=VELOCITY_REFERENCE,
                  age_days=0.0),
    ] * 10
    res = compute_saturation_from_pulse(rows)
    assert res.n_matches == 0
    assert res.saturation == 0.0


def test_just_above_cosine_threshold_starts_contributing():
    eps = 0.01
    rows = [
        _PulseRow(similarity=COSINE_THRESHOLD + eps, view_velocity=VELOCITY_REFERENCE,
                  age_days=0.0),
    ] * 5
    res = compute_saturation_from_pulse(rows)
    assert res.n_matches == 5
    assert res.saturation > 0.0




def test_saturation_gap_is_one_minus_saturation():
    """The opportunity scorer relies on this invariant. Lock it down."""
    rows = [
        _PulseRow(similarity=0.85, view_velocity=2000, age_days=2.0),
        _PulseRow(similarity=0.70, view_velocity=500,  age_days=5.0),
    ]
    res = compute_saturation_from_pulse(rows)
    assert res.saturation_gap == round(1 - res.saturation, 4)
    assert 0.0 <= res.saturation <= 1.0
    assert 0.0 <= res.saturation_gap <= 1.0


def test_top_match_similarity_reflects_actual_top():
    rows = [
        _PulseRow(similarity=0.62, view_velocity=1000, age_days=1.0),
        _PulseRow(similarity=0.91, view_velocity=2000, age_days=2.0),
        _PulseRow(similarity=0.71, view_velocity=500,  age_days=3.0),
    ]
    res = compute_saturation_from_pulse(rows)
    assert res.top_match_similarity == 0.91




def test_opportunity_weights_include_saturation_gap_and_sum_to_one():
    """The weights must sum to ~1.0 so the score stays in [0, 1]."""
    from src.services.research.opportunity_scorer import DEFAULT_WEIGHTS
    assert "saturation_gap" in DEFAULT_WEIGHTS
    total = sum(DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, f"weights sum to {total}, expected 1.0"
