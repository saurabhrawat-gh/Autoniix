"""Prediction-error correction loop (Phase 11).

The Phase 5 success predictors (``predict_success`` in research/script
self_learning) return a probability and a confidence at decision time.
After delivery the feedback ingestor learns the actual outcome. Until
Phase 11 we threw away the gap between predicted and actual: training
proceeded with uniform sample weights, treating "model said 0.85
confidently and was wrong" the same as "model said 0.55 hesitantly
and was wrong." That's wasted signal.

This module:

1. Logs every prediction (``log_prediction``) so we have a record
   joinable against later actuals.
2. After analytics ingest, computes ``abs_error`` and a
   ``sample_weight`` that biases retraining toward
   high-confidence misses (``update_prediction_actual``).
3. Computes calibration health metrics — Brier score and expected
   calibration error — for the fleet panel.

The pure-function core (``compute_abs_error``,
``compute_sample_weight``, ``brier_score``,
``expected_calibration_error``) is exhaustively tested and DB-free.
The async wrappers persist + retrieve.

Sample-weight design:
    weight = 1 + WEIGHT_K * confidence * abs_error
With ``WEIGHT_K = 4``:
  * confidence 0.9, error 0.7 → weight 3.52  (model was sure but
    very wrong; teach hard)
  * confidence 0.5, error 0.7 → weight 2.40  (mediocre confidence,
    big error; teach moderately)
  * confidence 0.9, error 0.05 → weight 1.18 (model was right;
    standard weight)
  * confidence 0.3, error 0.5 → weight 1.60  (low confidence, fair
    error; barely above standard)

The +1 baseline ensures every sample contributes something — we never
zero out a training point. The product `confidence * abs_error` is
the Bayesian "surprise" of the prediction: prior credence in being
right, scaled by how wrong it actually was.
"""

from __future__ import annotations

from typing import Iterable

import structlog

logger = structlog.get_logger()


WEIGHT_K = 4.0

WEIGHT_CAP = 6.0

DEFAULT_METRICS_LOOKBACK_DAYS = 30


def compute_abs_error(predicted: float, actual: float) -> float:
    """Absolute error |predicted - actual|, clamped to [0, 1].

    Both inputs are expected to be in [0, 1] (predicted = probability,
    actual = 0/1 success label or fractional engagement). We clamp
    defensively so a malformed actual (e.g. 1.5 from a downstream bug)
    can't propagate as a >1 error and blow up sample weights.
    """
    p = max(0.0, min(1.0, float(predicted)))
    a = max(0.0, min(1.0, float(actual)))
    return abs(p - a)


def compute_sample_weight(
    confidence: float,
    abs_error: float,
    *,
    k: float = WEIGHT_K,
    cap: float = WEIGHT_CAP,
) -> float:
    """Per-sample training weight biased toward high-confidence misses.

    Formula: ``1 + k * confidence * abs_error``, clamped to ``[1, cap]``.

    The +1 baseline ensures we never down-weight a sample below
    uniform; this function only ever *up-weights*. That's deliberate:
    "this prediction was a hit and confident" is the boring,
    correctly-modelled case, and uniform weight is exactly right for
    it. We never want to *erase* a sample.
    """
    confidence = max(0.0, min(1.0, float(confidence)))
    abs_error = max(0.0, min(1.0, float(abs_error)))
    raw = 1.0 + k * confidence * abs_error
    return min(cap, max(1.0, raw))


def brier_score(rows: Iterable[tuple[float, float]]) -> float | None:
    """Mean squared error between predictions and actuals.

    ``rows`` is an iterable of ``(predicted_prob, actual_outcome)``.
    Lower is better; perfect calibration scores 0. Random scores
    around 0.25 for a balanced binary problem; a baseline that always
    predicts the population rate scores around 0.21.

    Returns None for empty input — the caller distinguishes
    "no data yet" from "perfect calibration."
    """
    pairs = list(rows)
    if not pairs:
        return None
    total = sum((float(p) - float(a)) ** 2 for p, a in pairs)
    return total / len(pairs)


def expected_calibration_error(
    rows: Iterable[tuple[float, float]],
    *,
    n_bins: int = 10,
) -> float | None:
    """Expected Calibration Error (ECE) over equal-width probability bins.

    For each bin, computes |mean_predicted - mean_actual| weighted by
    the number of samples falling in that bin. Returns the weighted
    average. Range [0, 1]; 0 = perfect calibration; 0.10 is "noticeable
    miscalibration"; 0.25+ is "model is wrong about its own
    confidence."

    Standard implementation: bins on predicted probability, equal
    width over [0, 1]. Other partitionings (e.g. equal-mass bins) are
    valid but harder to read at a glance — and ECE is mostly used as
    a one-glance health number, so equal-width wins.
    """
    pairs = list(rows)
    if not pairs:
        return None
    if n_bins < 1:
        return None

    bins: list[list[tuple[float, float]]] = [[] for _ in range(n_bins)]
    for p, a in pairs:
        p_clamped = max(0.0, min(1.0, float(p)))
        idx = min(n_bins - 1, int(p_clamped * n_bins))
        bins[idx].append((p_clamped, float(a)))

    total = len(pairs)
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        mean_p = sum(p for p, _ in bucket) / len(bucket)
        mean_a = sum(a for _, a in bucket) / len(bucket)
        ece += (len(bucket) / total) * abs(mean_p - mean_a)
    return ece


async def log_prediction(
    *,
    content_id: str,
    model_kind: str,
    niche: str | None,
    predicted_prob: float,
    confidence: float,
    model_version: int | None = None,
) -> None:
    """Append/upsert a prediction row.

    Idempotent on ``(content_id, model_kind)``: a retry of the predict
    call updates the prediction in place rather than logging two rows.
    Failure to log is non-fatal — the prediction is already returned
    to the caller; we'd rather lose audit data than break the pipeline.
    """
    try:
        from core.db import get_pool

        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO prediction_log
                (content_id, model_kind, niche, predicted_prob,
                 confidence, model_version, predicted_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (content_id, model_kind) DO UPDATE SET
                predicted_prob = EXCLUDED.predicted_prob,
                confidence     = EXCLUDED.confidence,
                model_version  = EXCLUDED.model_version,
                niche          = EXCLUDED.niche,
                predicted_at   = NOW(),
                -- A re-predict invalidates the previous actuals join:
                -- clear them so update_prediction_actual recomputes.
                actual_outcome = NULL,
                abs_error      = NULL,
                sample_weight  = NULL,
                scored_at      = NULL
            """,
            content_id,
            model_kind,
            niche,
            round(float(predicted_prob), 4),
            round(float(confidence), 4),
            model_version,
        )
    except Exception as exc:
        logger.warning(
            "calibration.log_prediction_failed", content_id=content_id, model_kind=model_kind, error=str(exc)
        )


async def update_prediction_actual(
    *,
    content_id: str,
    model_kind: str,
    actual_outcome: float,
) -> dict | None:
    """Fill in actual + computed fields for one prediction row.

    Reads back the predicted_prob and confidence to compute abs_error
    and sample_weight server-side (no second roundtrip). Returns a
    summary dict for logging, or None if the prediction wasn't logged
    (typical when the model was rule-based at decision time and we
    skipped logging).
    """
    try:
        from core.db import get_pool

        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT predicted_prob, confidence FROM prediction_log
            WHERE content_id = $1 AND model_kind = $2
            """,
            content_id,
            model_kind,
        )
        if row is None:
            return None
        predicted = float(row["predicted_prob"])
        confidence = float(row["confidence"])
        abs_err = compute_abs_error(predicted, actual_outcome)
        weight = compute_sample_weight(confidence, abs_err)
        await pool.execute(
            """
            UPDATE prediction_log SET
                actual_outcome = $3,
                abs_error      = $4,
                sample_weight  = $5,
                scored_at      = NOW()
            WHERE content_id = $1 AND model_kind = $2
            """,
            content_id,
            model_kind,
            round(float(actual_outcome), 4),
            round(abs_err, 4),
            round(weight, 3),
        )
        return {
            "predicted": predicted,
            "actual": float(actual_outcome),
            "abs_error": abs_err,
            "sample_weight": weight,
        }
    except Exception as exc:
        logger.warning("calibration.update_actual_failed", content_id=content_id, model_kind=model_kind, error=str(exc))
        return None


async def get_calibration_metrics(
    *,
    model_kind: str,
    niche: str | None = None,
    lookback_days: int = DEFAULT_METRICS_LOOKBACK_DAYS,
) -> dict:
    """Brier + ECE + count for the fleet panel.

    Returns ``{"n": int, "brier": float|None, "ece": float|None}``.
    Both metrics are None when there are no scored predictions; the
    dashboard renders that as "—" rather than a misleading 0.
    """
    try:
        from core.db import get_pool

        pool = await get_pool()
        params: list = [model_kind, lookback_days]
        query = """
            SELECT predicted_prob::float AS p, actual_outcome::float AS a
            FROM prediction_log
            WHERE model_kind = $1
              AND scored_at IS NOT NULL
              AND scored_at > NOW() - ($2::int * INTERVAL '1 day')
        """
        if niche:
            query += " AND niche = $3"
            params.append(niche)
        rows = await pool.fetch(query, *params)
        pairs = [(r["p"], r["a"]) for r in rows]
        return {
            "n": len(pairs),
            "brier": brier_score(pairs),
            "ece": expected_calibration_error(pairs),
        }
    except Exception as exc:
        logger.warning("calibration.metrics_failed", model_kind=model_kind, error=str(exc))
        return {"n": 0, "brier": None, "ece": None}


async def get_sample_weights(
    *,
    model_kind: str,
    content_ids: list[str],
) -> dict[str, float]:
    """Look up ``content_id → sample_weight`` for a training batch.

    Caller passes the list of training content_ids and we return a
    sparse mapping (only those with computed weights). Missing entries
    use the uniform default weight 1.0.

    Tuned for the train_model query path: one fetch with a single
    ``ANY($1)`` is enough — we don't need to paginate.
    """
    if not content_ids:
        return {}
    try:
        from core.db import get_pool

        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT content_id, sample_weight::float AS w
            FROM prediction_log
            WHERE model_kind = $1
              AND content_id = ANY($2::text[])
              AND sample_weight IS NOT NULL
            """,
            model_kind,
            content_ids,
        )
        return {r["content_id"]: float(r["w"]) for r in rows}
    except Exception as exc:
        logger.warning("calibration.weights_fetch_failed", model_kind=model_kind, error=str(exc))
        return {}
