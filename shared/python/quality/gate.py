"""Strict pre-publish quality gate.

Two independent checks must both pass before a video can be published:

1. **Hard floors** — every dimension must clear its individual minimum.
   A 9.5 hook can't compensate for a 5.0 voice score; we'd rather hold
   the video for human review than publish something with one obviously
   broken pillar.

2. **Composite score** — the weighted sum (same weights the delivery
   service has used since day one) must clear the composite threshold.

The gate runs in two profiles:

* ``production`` — the published thresholds from the master plan.
* ``test``       — every floor is 0 so test-mode workflows always pass.

A third path exists, ``override``: an admin can force-publish a video
that fails the gate. Every override is recorded in
``quality_gate_decisions`` along with the reason and the operator's
identity, so the same audit trail lights up Grafana whether the gate
passed, blocked, or was bypassed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


WEIGHTS: dict[str, float] = {
    "research_depth_score": 0.15,
    "script_structure_score": 0.25,
    "hook_retention_score": 0.15,
    "voice_quality_score": 0.10,
    "thumbnail_score": 0.15,
    "direction_score": 0.10,
    "production_score": 0.10,
}

PRODUCTION_THRESHOLDS: dict[str, float] = {
    "research_depth_score": 7.0,
    "script_structure_score": 7.5,
    "hook_retention_score": 7.5,
    "voice_quality_score": 7.0,
    "thumbnail_score": 7.5,
    "direction_score": 7.0,
    "production_score": 7.0,
    "composite_score": 8.0,
}

TEST_THRESHOLDS: dict[str, float] = {k: 0.0 for k in PRODUCTION_THRESHOLDS}


@dataclass
class GateProfile:
    name: str
    thresholds: dict[str, float]


PROFILES: dict[str, GateProfile] = {
    "production": GateProfile("production", PRODUCTION_THRESHOLDS),
    "test": GateProfile("test", TEST_THRESHOLDS),
}


@dataclass
class GateDecision:
    passed: bool
    composite_score: float
    sub_scores: dict[str, float]
    failures: list[str] = field(default_factory=list)
    profile: str = "production"

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "composite_score": round(self.composite_score, 2),
            "sub_scores": {k: round(v, 2) for k, v in self.sub_scores.items()},
            "failures": list(self.failures),
            "profile": self.profile,
        }


def _composite(sub_scores: dict[str, float]) -> float:
    """Same weighted formula delivery.main._compute_final_score uses.

    Missing dimensions default to 7.0 so a partially-populated payload
    doesn't artificially fail the composite check (the hard floor still
    catches genuinely missing data, e.g. a 0 from a service that never ran).
    """
    total = 0.0
    for key, weight in WEIGHTS.items():
        total += float(sub_scores.get(key, 7.0)) * weight
    return round(total, 2)


def evaluate(
    sub_scores: dict[str, Any],
    *,
    profile: str = "production",
) -> GateDecision:
    """Run the gate. Returns a :class:`GateDecision` — never raises.

    Callers decide what to do with a failed decision (block publish, queue
    for human review, override with audit trail, etc.).
    """
    prof = PROFILES.get(profile, PROFILES["production"])
    coerced: dict[str, float] = {}
    for k, v in sub_scores.items():
        try:
            coerced[k] = float(v)
        except (TypeError, ValueError):
            coerced[k] = 0.0

    composite = _composite(coerced)
    failures: list[str] = []
    for dim, floor in prof.thresholds.items():
        if dim == "composite_score":
            if composite < floor:
                failures.append(f"composite_score={composite:.2f}<{floor:.2f}")
            continue
        actual = coerced.get(dim)
        if actual is None:
            failures.append(f"{dim}=missing<{floor:.2f}")
            continue
        if actual < floor:
            failures.append(f"{dim}={actual:.2f}<{floor:.2f}")

    return GateDecision(
        passed=not failures,
        composite_score=composite,
        sub_scores=coerced,
        failures=failures,
        profile=prof.name,
    )


async def evaluate_for_niche(
    sub_scores: dict[str, Any],
    *,
    niche: str | None = None,
    profile: str = "production",
) -> GateDecision:
    """Niche-aware variant of :func:`evaluate`.

    Loads per-niche thresholds from ``gate_thresholds`` (Phase 7's
    self-tuning calibrator) and falls back to the static profile for
    any dimension the calibrator hasn't written yet. The ``profile``
    argument is honoured for the test profile (zeros everything out),
    so test-mode workflows keep passing unchanged.

    Cold-start safe: when ``niche`` is ``None``, when the DB is
    unreachable, or when no rows exist for the niche, this degrades
    cleanly to the static-default behaviour.
    """
    if profile == "test" or not niche:
        return evaluate(sub_scores, profile=profile)

    from quality.calibrator import load_thresholds_for_niche

    thresholds = await load_thresholds_for_niche(niche)

    coerced: dict[str, float] = {}
    for k, v in sub_scores.items():
        try:
            coerced[k] = float(v)
        except (TypeError, ValueError):
            coerced[k] = 0.0

    composite = _composite(coerced)
    failures: list[str] = []
    for dim, floor in thresholds.items():
        if dim == "composite_score":
            if composite < floor:
                failures.append(f"composite_score={composite:.2f}<{floor:.2f}")
            continue
        actual = coerced.get(dim)
        if actual is None:
            failures.append(f"{dim}=missing<{floor:.2f}")
            continue
        if actual < floor:
            failures.append(f"{dim}={actual:.2f}<{floor:.2f}")

    return GateDecision(
        passed=not failures,
        composite_score=composite,
        sub_scores=coerced,
        failures=failures,
        profile=f"production:{niche}",
    )


async def record_decision(
    *,
    content_id: str,
    channel_id: str,
    decision: GateDecision,
    overridden: bool = False,
    override_reason: str = "",
    override_by: str = "",
) -> None:
    """Persist a gate evaluation to ``quality_gate_decisions``.

    The table is the source of truth for the ``quality_gate_blocks_total``
    Prometheus metric (we sum ``decision = 'block'`` rows in Grafana) and
    for any future per-channel threshold auto-tuning model.
    """
    decision_str = "override" if overridden else ("pass" if decision.passed else "block")
    try:
        from core.db import get_pool

        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO quality_gate_decisions (
                content_id, channel_id, decision, composite_score,
                hard_floor_failures, sub_scores, threshold_profile,
                override_reason, override_by
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
            """,
            content_id,
            channel_id,
            decision_str,
            decision.composite_score,
            decision.failures,
            json.dumps(decision.sub_scores),
            decision.profile,
            override_reason or None,
            override_by or None,
        )
    except Exception as exc:
        logger.warning("quality_gate.record_failed", error=str(exc))
