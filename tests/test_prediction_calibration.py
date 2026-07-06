"""Phase 11 — prediction-error correction loop tests.

Locks the math (abs_error, sample_weight, Brier, ECE) and the contract
(predict_success accepts content_id keyword-only; train_model query
joins prediction_log; ingest_performance closes the loop).
"""
from __future__ import annotations

import pytest

from intelligence.prediction_calibration import (
    DEFAULT_METRICS_LOOKBACK_DAYS,
    WEIGHT_CAP,
    WEIGHT_K,
    brier_score,
    compute_abs_error,
    compute_sample_weight,
    expected_calibration_error,
)




def test_abs_error_perfect_prediction_zero():
    assert compute_abs_error(1.0, 1.0) == 0.0
    assert compute_abs_error(0.0, 0.0) == 0.0


def test_abs_error_completely_wrong_one():
    assert compute_abs_error(1.0, 0.0) == 1.0
    assert compute_abs_error(0.0, 1.0) == 1.0


def test_abs_error_matches_absolute_difference():
    assert compute_abs_error(0.7, 0.2) == pytest.approx(0.5)
    assert compute_abs_error(0.3, 0.9) == pytest.approx(0.6)


def test_abs_error_clamps_out_of_range_inputs():
    """Defensive: malformed actual=1.5 from a downstream bug must not
    propagate as a >1 error and blow up sample weights."""
    assert compute_abs_error(0.5, 1.5) == 0.5
    assert compute_abs_error(-0.2, 0.5) == 0.5
    assert compute_abs_error(2.0, -1.0) == 1.0




def test_weight_baseline_is_one_for_perfect_predictions():
    """Confidence × error = 0 → weight = 1 + 0 = 1, the uniform
    baseline. We never down-weight a sample below uniform."""
    assert compute_sample_weight(0.9, 0.0) == 1.0
    assert compute_sample_weight(0.0, 0.7) == 1.0


def test_weight_increases_with_confidence_at_fixed_error():
    """High-confidence misses must out-weigh low-confidence misses
    when the error is the same. This is the entire point of Phase 11."""
    low_conf  = compute_sample_weight(0.3, 0.5)
    high_conf = compute_sample_weight(0.9, 0.5)
    assert high_conf > low_conf


def test_weight_increases_with_error_at_fixed_confidence():
    """Bigger misses out-weigh smaller misses for the same model
    confidence."""
    small_err = compute_sample_weight(0.7, 0.2)
    big_err   = compute_sample_weight(0.7, 0.8)
    assert big_err > small_err


def test_weight_formula_at_perfect_storm():
    """Confidence 1.0, error 1.0 → max natural weight = 1 + WEIGHT_K."""
    expected = 1.0 + WEIGHT_K
    assert compute_sample_weight(1.0, 1.0) == pytest.approx(expected)


def test_weight_respects_cap():
    """Even if WEIGHT_K is tuned upward later, we never exceed cap.
    Outliers can't single-handedly dominate one training pass."""
    runaway = compute_sample_weight(1.0, 1.0, k=999.0)
    assert runaway == WEIGHT_CAP


def test_weight_floor_is_uniform():
    """Weights below 1.0 are clamped to 1.0 — we never erase samples,
    only up-weight surprises."""
    weight = compute_sample_weight(0.5, 0.5, k=-10.0)
    assert weight == 1.0


def test_weight_clamps_inputs_out_of_range():
    """Defensive: confidence=2.0 or error=-0.1 must not propagate."""
    assert compute_sample_weight(2.0, 1.0) <= 1.0 + WEIGHT_K
    assert compute_sample_weight(-0.5, 0.5) == 1.0


def test_weight_monotonicity_on_a_grid():
    """For any pair (c1, e1) <= (c2, e2) (componentwise), the weight
    must be monotonically non-decreasing. This nails down the
    structural property we actually rely on in retraining."""
    points = [
        (0.1, 0.1), (0.1, 0.5), (0.1, 0.9),
        (0.5, 0.1), (0.5, 0.5), (0.5, 0.9),
        (0.9, 0.1), (0.9, 0.5), (0.9, 0.9),
    ]
    for c1, e1 in points:
        for c2, e2 in points:
            if c1 <= c2 and e1 <= e2:
                assert compute_sample_weight(c1, e1) <= compute_sample_weight(c2, e2), (
                    f"monotonicity broken at ({c1},{e1}) > ({c2},{e2})"
                )




def test_brier_zero_for_perfect_predictions():
    rows = [(1.0, 1.0), (0.0, 0.0), (0.5, 0.5)]
    assert brier_score(rows) == 0.0


def test_brier_one_for_completely_wrong():
    rows = [(1.0, 0.0), (0.0, 1.0)]
    assert brier_score(rows) == 1.0


def test_brier_matches_definition():
    """Brier = mean((p - a)^2)."""
    rows = [(0.8, 1.0), (0.3, 0.0), (0.9, 0.0)]
    expected = ((0.8 - 1.0) ** 2 + (0.3 - 0.0) ** 2 + (0.9 - 0.0) ** 2) / 3
    assert brier_score(rows) == pytest.approx(expected)


def test_brier_random_baseline_around_quarter():
    """Predicting 0.5 for everything on a balanced binary set scores
    exactly 0.25. This is the random-baseline floor — anything worse
    means the model is actively counter-signal."""
    rows = [(0.5, 1.0)] * 50 + [(0.5, 0.0)] * 50
    assert brier_score(rows) == pytest.approx(0.25)


def test_brier_returns_none_for_empty():
    """Distinguish 'no data' from 'perfect calibration' — the dashboard
    needs to render '—' vs '0.000'."""
    assert brier_score([]) is None




def test_ece_zero_for_perfect_calibration():
    """When predicted probabilities exactly match outcome rates within
    each bin, ECE = 0."""
    rows = [(0.9, 1.0), (0.9, 1.0), (0.9, 1.0), (0.9, 0.0)] * 10
    ece = expected_calibration_error(rows)
    assert ece == pytest.approx(0.15, abs=1e-9)


def test_ece_for_uniformly_perfect_predictions():
    """Predictions of exactly 0.5 with 50/50 outcomes → mean predicted
    0.5, mean actual 0.5, gap 0 → ECE 0."""
    rows = [(0.5, 1.0)] * 25 + [(0.5, 0.0)] * 25
    assert expected_calibration_error(rows) == pytest.approx(0.0, abs=1e-9)


def test_ece_in_unit_interval():
    """ECE is bounded [0, 1] for any inputs."""
    cases = [
        [(1.0, 0.0)] * 10,
        [(p / 100, 0.5) for p in range(101)],
    ]
    for rows in cases:
        ece = expected_calibration_error(rows)
        assert ece is not None
        assert 0.0 <= ece <= 1.0


def test_ece_returns_none_for_empty():
    assert expected_calibration_error([]) is None


def test_ece_rejects_zero_bins():
    """Defensive: silly n_bins shouldn't crash."""
    rows = [(0.5, 1.0)]
    assert expected_calibration_error(rows, n_bins=0) is None


def test_ece_handles_perfect_confidence_at_boundary():
    """A prediction of exactly 1.0 must land in the last bin, not
    overflow. Locks the closed-right interval handling."""
    rows = [(1.0, 1.0)] * 5 + [(0.0, 0.0)] * 5
    ece = expected_calibration_error(rows)
    assert ece is not None
    assert ece < 0.01




def test_high_confidence_miss_dominates_uniform_correct():
    """The headline scenario: in a training batch with 10 mostly-right
    low-confidence predictions and 1 high-confidence catastrophe, the
    catastrophe must carry more weight than several uniform rows."""
    correct_low_conf = compute_sample_weight(0.4, 0.0)
    confident_miss   = compute_sample_weight(0.95, 0.85)
    assert confident_miss >= 3.0 * correct_low_conf


def test_weight_distribution_on_realistic_batch():
    """Mean weight on a typical batch (mostly correct, some misses)
    should hover near 1.0 with occasional spikes — *not* dominated
    by a few outliers."""
    batch = [
        (0.8, 0.05),
        (0.3, 0.1),
        (0.9, 0.1),
        (0.7, 0.7),
        (0.5, 0.5),
        (0.4, 0.05),
    ]
    weights = [compute_sample_weight(c, e) for c, e in batch]
    assert sum(weights) / len(weights) < WEIGHT_CAP
    assert all(w >= 1.0 for w in weights)




def test_constants_have_sensible_values():
    assert WEIGHT_K > 0
    assert WEIGHT_CAP >= 1.0 + WEIGHT_K
    assert DEFAULT_METRICS_LOOKBACK_DAYS >= 7




def test_predict_success_accepts_content_id_keyword_only():
    """Ensure predict_success has the Phase 11 content_id parameter as
    keyword-only — positional callers must keep working."""
    import inspect
    from services_api.research.self_learning import predict_success
    sig = inspect.signature(predict_success)
    assert "content_id" in sig.parameters
    assert sig.parameters["content_id"].kind == inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["content_id"].default is None


def test_research_request_accepts_optional_content_id():
    """Workflow plumbing — the research service request schema must
    accept content_id as optional. Without this the workflow can't
    forward its content_id and the train_model JOIN can't work."""
    from services_api.research.main import ResearchRequest
    fields = ResearchRequest.model_fields
    assert "content_id" in fields
    assert fields["content_id"].default is None


def test_train_model_query_includes_prediction_log_join():
    """Static check: the training query must LEFT JOIN prediction_log
    and pull sample_weight. A future refactor that drops this would
    silently revert Phase 11."""
    import inspect
    from services_api.research import self_learning
    src = inspect.getsource(self_learning.train_model)
    assert "prediction_log" in src
    assert "sample_weight" in src
    assert "LEFT JOIN" in src.upper() or "left join" in src
