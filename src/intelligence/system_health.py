"""System-wide health aggregation (Phase 12).

After 11 phases the fleet panel exposes 9 distinct cards: services,
DB pool, render queue, gate calibration, niche pulse, retention
coverage, diversity floor, prediction calibration, and 24h pressure.
That's a lot of mental aggregation for an operator at 2 a.m.

This module collapses all of them into one number on [0, 100] with a
traffic-light band, *plus* a per-subsystem breakdown so drilling down
remains trivial. The original detail panels are preserved verbatim —
this is purely additive.

Design decisions:

  * **Pure functions only.** All scoring takes a plain dict (the
    fleet-health payload) and returns a plain dict. No DB, no I/O.
    Trivially testable, trivially refactorable.
  * **Each subsystem has a fixed weight in the aggregate.** Weights
    are chosen by *operator impact*, not by data-pipeline ordering:
    services down (50% pts) matters more than slightly-stale niche
    pulse (5% pts).
  * **Missing data ≠ broken.** A subsystem that hasn't reported
    yet (cold-start, schema not yet applied) scores ``None`` and is
    *excluded* from the weighted average. This avoids penalising the
    score on day-1 of deployment when half the tables are empty.
  * **Bands are operator-actionable, not statistical.** ``green`` is
    "no action needed," ``yellow`` is "investigate when convenient,"
    ``red`` is "investigate now." No pretty-but-meaningless gradients.

Subsystem weights (sum to 100):
    services           : 35   - the literal "is anything responding"
    db_pool            : 10   - back-pressure leading indicator
    pressure_24h       :  8   - recent gate blocks + failures
    gate_calibration   :  8   - thresholds adapting?
    niche_pulse        :  7   - saturation scorer fed?
    retention_coverage :  8   - calibrator getting curves?
    diversity_floor    :  8   - bandits exploring?
    calibration        : 16   - prediction quality (the headline ML signal)
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


# ── Weights & thresholds (tunable; documented in module docstring) ───


SUBSYSTEM_WEIGHTS: dict[str, int] = {
    "services":           35,
    "db_pool":            10,
    "pressure_24h":        8,
    "gate_calibration":    8,
    "niche_pulse":         7,
    "retention_coverage":  8,
    "diversity_floor":     8,
    "calibration":        16,
}
assert sum(SUBSYSTEM_WEIGHTS.values()) == 100, (
    "subsystem weights must sum to 100 to keep the headline score "
    "interpretable as a percentage"
)

# Traffic-light bands on the aggregate score.
GREEN_THRESHOLD  = 80   # >= 80 : no action needed
YELLOW_THRESHOLD = 50   # 50-79 : investigate when convenient
                        # <  50 : investigate now (red)


# ── Helpers ─────────────────────────────────────────────────────────


def _hours_since(iso_ts: str | None) -> float | None:
    """Return age of an ISO timestamp in hours, or None if unparseable."""
    if not iso_ts:
        return None
    try:
        # Postgres TIMESTAMPTZ → ISO with offset; tolerate trailing 'Z'.
        s = iso_ts.replace("Z", "+00:00") if iso_ts.endswith("Z") else iso_ts
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return delta.total_seconds() / 3600.0
    except (ValueError, TypeError):
        return None


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _linear_band(x: float, *, ok_at: float, fail_at: float) -> float:
    """Map ``x`` to [0, 1] with a linear ramp.

    ``ok_at`` → score 1.0, ``fail_at`` → score 0.0, with linear
    interpolation between. Direction is inferred from the order:
    if ``ok_at > fail_at`` higher is better; if ``ok_at < fail_at``
    lower is better.

    This is the workhorse for "graceful degradation" scoring — most
    subsystems have a clear good and bad threshold and we want partial
    credit in between, not a step function.
    """
    if ok_at == fail_at:
        return 1.0 if x >= ok_at else 0.0
    if ok_at > fail_at:
        # Higher is better.
        if x >= ok_at: return 1.0
        if x <= fail_at: return 0.0
        return (x - fail_at) / (ok_at - fail_at)
    # Lower is better.
    if x <= ok_at: return 1.0
    if x >= fail_at: return 0.0
    return (fail_at - x) / (fail_at - ok_at)


# ── Per-subsystem scorers ───────────────────────────────────────────
#
# Each scorer takes the relevant slice of the fleet payload and
# returns either a float in [0, 100], or None when there's no data
# yet. ``None`` is propagated to the aggregator which excludes the
# subsystem from the weighted average.


def score_services(s: dict | None) -> tuple[float | None, str]:
    """Fraction of probes returning OK, plus a short reason."""
    if not s:
        return None, "no probe data"
    ok = int(s.get("ok_count") or 0)
    total = int(s.get("total") or 0)
    if total == 0:
        return None, "no probes registered"
    pct = (ok / total) * 100
    if ok == total:
        reason = f"all {total} services responding"
    else:
        down = total - ok
        reason = f"{down}/{total} service{'s' if down != 1 else ''} not responding"
    return pct, reason


def score_db_pool(p: dict | None) -> tuple[float | None, str]:
    """Pool pressure: idle/size ratio. Pressure>0.8 means the pool
    is mostly idle (good); <0.2 means saturated (bad)."""
    if not p:
        return None, "no pool data"
    size = int(p.get("size") or 0)
    idle = int(p.get("idle") or 0)
    max_size = int(p.get("max_size") or 1)
    if size == 0:
        return 100.0, "pool not yet warmed"
    headroom = idle / max(size, 1)
    # Healthy when ≥ 30% of the pool is idle; saturated at 0%.
    score_norm = _linear_band(headroom, ok_at=0.30, fail_at=0.0)
    pct = round(score_norm * 100, 1)
    if size >= max_size and idle == 0:
        return 0.0, f"pool saturated ({size}/{max_size}, 0 idle)"
    if idle == 0:
        return pct, f"pool fully checked out ({size}/{max_size})"
    return pct, f"{idle}/{size} idle (max {max_size})"


def score_pressure_24h(p: dict | None) -> tuple[float | None, str]:
    """Recent gate blocks + failures. Both small = healthy."""
    if not p:
        return None, "no pressure data"
    blocks = p.get("quality_gate_blocks")
    fails  = p.get("video_failures")
    if blocks is None and fails is None:
        return None, "no pressure data"
    blocks = int(blocks or 0)
    fails  = int(fails or 0)
    # Combined backpressure index. Failures matter more than blocks
    # (a block is the gate doing its job; a failure is a wedged
    # pipeline). 0 → 100, 5 combined → ~80, 25 combined → ~0.
    combined = blocks + fails * 2
    score_norm = _linear_band(float(combined), ok_at=0.0, fail_at=25.0)
    pct = round(score_norm * 100, 1)
    return pct, f"{blocks} gate blocks, {fails} failures (24h)"


def score_gate_calibration(g: dict | None) -> tuple[float | None, str]:
    """Have thresholds been calibrated, and recently?"""
    if not g or not g.get("ok"):
        return None, (g or {}).get("error") or "no calibration data"
    niches = int(g.get("niches_calibrated") or 0)
    auto   = int(g.get("dims_auto") or 0)
    default = int(g.get("dims_default") or 0)
    if niches == 0:
        # Cold start — not a failure, just not calibrated yet.
        return None, "no niches calibrated yet"
    last = _hours_since(g.get("last_run"))
    # Score combines: (a) fraction of dims auto-calibrated vs default,
    # (b) staleness of the last run.
    total_dims = auto + default
    auto_frac = auto / total_dims if total_dims else 0.0
    auto_score = _linear_band(auto_frac, ok_at=0.7, fail_at=0.0)
    if last is None:
        stale_score = 0.5   # unknown — partial credit
    else:
        # Weekly calibration; score 1.0 if <168h, 0.0 if >336h.
        stale_score = _linear_band(last, ok_at=168.0, fail_at=336.0)
    pct = round(((auto_score + stale_score) / 2) * 100, 1)
    return pct, f"{auto}/{total_dims} dims auto, {niches} niches"


def score_niche_pulse(n: dict | None) -> tuple[float | None, str]:
    """Saturation pulse freshness."""
    if not n or not n.get("ok"):
        return None, (n or {}).get("error") or "no pulse data"
    rows   = int(n.get("embedded_rows") or 0)
    niches = int(n.get("niches_with_data") or 0)
    if niches == 0:
        return None, "pulse not yet refreshed"
    last = _hours_since(n.get("last_refresh"))
    if last is None:
        return 50.0, f"{niches} niches, freshness unknown"
    # Weekly refresh; OK <168h, fail >336h.
    score_norm = _linear_band(last, ok_at=168.0, fail_at=336.0)
    pct = round(score_norm * 100, 1)
    return pct, f"{niches} niches, last refresh {round(last)}h ago"


def score_retention_coverage(r: dict | None) -> tuple[float | None, str]:
    """Fraction of curve-stable videos with a fetched retention curve."""
    if not r or not r.get("ok"):
        return None, (r or {}).get("error") or "no coverage data"
    eligible  = int(r.get("eligible") or 0)
    if eligible == 0:
        # No videos in the curve-stable window yet.
        return None, "no videos in 7-30d window yet"
    cov = r.get("coverage")
    if cov is None:
        return None, "coverage unknown"
    # 80% coverage = healthy; 30% = warn; <20% = the daily fetch is wedged.
    score_norm = _linear_band(float(cov), ok_at=0.80, fail_at=0.20)
    pct = round(score_norm * 100, 1)
    return pct, f"{int(cov * 100)}% of {eligible} eligible"


def score_diversity_floor(d: dict | None) -> tuple[float | None, str]:
    """Force-rate of the diversity floor. Healthy: 5-25%.

    Edge case: 0% with substantial picks_7d is *ambiguous* — could be
    naturally diverse bandits (good) or a too-loose threshold (bad).
    We score it as 'unknown' (None) below ~5 picks; otherwise treat
    it as healthy by default since the alternative interpretation
    requires manual judgment."""
    if not d or not d.get("ok"):
        return None, (d or {}).get("error") or "no pick data"
    picks = int(d.get("picks_7d") or 0)
    if picks < 5:
        return None, f"only {picks} picks last 7d (too few)"
    rate = d.get("force_rate")
    if rate is None:
        return 100.0, f"{picks} picks, no force rate"
    rate = float(rate)
    if rate <= 0.05:
        # Low rate may be benign or threshold-too-loose; we score this
        # as 'mostly healthy' (90) so the operator only gets nudged
        # when force rate is high (collapse).
        return 90.0, f"force rate {round(rate * 100)}% (likely healthy)"
    if rate <= 0.25:
        return 100.0, f"force rate {round(rate * 100)}% (healthy)"
    # Above 25% means we're constantly forcing — threshold too aggressive
    # or bandits genuinely collapsing.
    score_norm = _linear_band(rate, ok_at=0.25, fail_at=0.50)
    pct = round(score_norm * 100, 1)
    return pct, f"force rate {round(rate * 100)}% (high)"


def score_calibration(c: dict | None) -> tuple[float | None, str]:
    """Brier + ECE on the topic-success predictor."""
    if not c or not c.get("ok"):
        return None, (c or {}).get("error") or "no calibration data"
    n = int(c.get("n") or 0)
    if n < 20:
        # Too few scored predictions for the metrics to be reliable.
        return None, f"{n} scored (need ≥20)"
    brier = c.get("brier")
    ece   = c.get("ece")
    parts: list[float] = []
    if brier is not None:
        # Brier 0.10 = excellent, 0.25 = random baseline → fail.
        parts.append(_linear_band(float(brier), ok_at=0.10, fail_at=0.25))
    if ece is not None:
        # ECE 0.05 = excellent, 0.20 = noticeable miscalibration → fail.
        parts.append(_linear_band(float(ece), ok_at=0.05, fail_at=0.20))
    if not parts:
        return None, "metrics not yet computed"
    pct = round((sum(parts) / len(parts)) * 100, 1)
    bits = []
    if brier is not None:
        bits.append(f"Brier {brier:.3f}")
    if ece is not None:
        bits.append(f"ECE {ece:.3f}")
    return pct, ", ".join(bits) + f" over {n} preds"


# ── Aggregation ─────────────────────────────────────────────────────


SUBSYSTEM_SCORERS = {
    "services":           score_services,
    "db_pool":            score_db_pool,
    "pressure_24h":       score_pressure_24h,
    "gate_calibration":   score_gate_calibration,
    "niche_pulse":        score_niche_pulse,
    "retention_coverage": score_retention_coverage,
    "diversity_floor":    score_diversity_floor,
    "calibration":        score_calibration,
}


def band(score: float) -> str:
    """Map [0, 100] score → 'green' / 'yellow' / 'red'."""
    if score >= GREEN_THRESHOLD:
        return "green"
    if score >= YELLOW_THRESHOLD:
        return "yellow"
    return "red"


def aggregate_health(payload: dict) -> dict:
    """Reduce the fleet-health payload to a single score + breakdown.

    Returns
    -------
    dict
        ``{
          "score":     float,         # 0-100 weighted avg
          "band":      'green'|'yellow'|'red',
          "n_active":  int,           # subsystems that contributed
          "n_total":   int,           # subsystems known
          "subsystems": [
            {
              "name":   str,
              "score":  float | None,   # None = no data
              "weight": int,
              "reason": str,
            }, ...
          ],
        }``

    Subsystems with ``score=None`` (no data yet) are *excluded* from
    the weighted average — we don't want a cold-start system to
    score 0 just because the prediction calibration table is empty.
    Their entries remain in the breakdown so the operator can see
    *what* hasn't reported.
    """
    breakdown: list[dict[str, Any]] = []
    weighted_sum = 0.0
    weight_total = 0

    for name, weight in SUBSYSTEM_WEIGHTS.items():
        scorer = SUBSYSTEM_SCORERS[name]
        slice_ = payload.get(name)
        # `services` lives under a different shape than the rest;
        # adapt where needed.
        score, reason = scorer(slice_)
        breakdown.append({
            "name":   name,
            "score":  None if score is None else round(float(score), 1),
            "weight": weight,
            "reason": reason,
        })
        if score is not None:
            weighted_sum += float(score) * weight
            weight_total += weight

    if weight_total == 0:
        # Total cold start — no subsystem has reported. Score is
        # explicitly 'unknown' rather than 0. Render as a neutral state.
        return {
            "score":      None,
            "band":       "unknown",
            "n_active":   0,
            "n_total":    len(SUBSYSTEM_WEIGHTS),
            "subsystems": breakdown,
        }

    overall = weighted_sum / weight_total
    return {
        "score":      round(overall, 1),
        "band":       band(overall),
        "n_active":   sum(1 for b in breakdown if b["score"] is not None),
        "n_total":    len(SUBSYSTEM_WEIGHTS),
        "subsystems": breakdown,
    }
