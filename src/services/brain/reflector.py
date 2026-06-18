"""BrainReflector — periodic self-tuning loop over scored brain_decisions.

The fourth piece of the AE-P1 agentic foundation (after BaseAgent / RAG
recall / Critic). Closes the feedback loop:

    decide  →  act  →  outcome scored  →  reflect  →  proposal queue

The Reflector reads brain_decisions rows whose outcome has been scored
(``outcome_score IS NOT NULL``) within a lookback window, groups them by
``decision_type``, and looks for classes whose average outcome falls
below a configurable threshold over a sufficiently large sample. For
each such class it emits ONE proposal into ``brain_flag_proposals``
(write-protected queue) recommending a specific tweak to a
``brain.threshold.*`` flag.

The Reflector NEVER mutates ``feature_flags``. The only side-effect is
inserting (or updating) a row in the proposal queue. Operators (or a
future auto-apply policy) move the proposal through
``pending → approved → applied``.

Pattern → flag mapping is intentionally small and explicit. Adding a
new mapping is just a row in :data:`_PATTERN_TO_FLAG`.

Part of AE-P1 / Agentic Foundation.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.db import get_pool
from src.flags import get_flag

logger = structlog.get_logger()


@dataclass
class Pattern:
    """One row of the per-decision_type aggregation."""
    decision_type: str
    sample_size: int
    avg_score: float
    sample_decision_ids: list[int] = field(default_factory=list)


@dataclass
class Proposal:
    """One proposed flag change. Persisted into ``brain_flag_proposals``."""
    flag_key: str
    current_payload: dict[str, Any] | None
    proposed_payload: dict[str, Any]
    rationale: str
    supporting_evidence: dict[str, Any]
    sample_size: int
    observed_avg_score: float


#: Map of (decision_type, direction) → (flag_key, new_value generator).
#:
#: ``direction`` is currently always ``"raise"`` — the Reflector only fires
#: on *under-performing* decision classes, and the safe response is to
#: make the trigger threshold harder to hit (raise it). Future work can
#: add ``"lower"`` patterns once we model over-performing classes too.
#:
#: Each entry's ``next_value`` function takes the current numeric value
#: and returns the proposed next value. Single bump per pass — operator
#: approves, observes, then the next pass can bump again if needed.
_PATTERN_TO_FLAG: dict[str, dict[str, Any]] = {
    "HALT": {
        "flag_key": "brain.threshold.halt.consecutive_failures",
        "rationale_template": (
            "HALT decisions averaged outcome_score={avg:.2f} over "
            "{n} samples in the last {days} days — raising the "
            "consecutive-failures trigger from {old} to {new} to "
            "reduce false-positive halts."
        ),
        "next_value": lambda cur: int(cur) + 1,
        "min_value": 1,
        "max_value": 10,
    },
    "HOLD": {
        "flag_key": "brain.threshold.hold.cost_spike_factor",
        "rationale_template": (
            "HOLD decisions averaged outcome_score={avg:.2f} over "
            "{n} samples in the last {days} days — raising the "
            "cost-spike multiplier from {old} to {new} so we only "
            "hold on genuinely anomalous spikes."
        ),
        "next_value": lambda cur: round(float(cur) + 0.5, 2),
        "min_value": 1.0,
        "max_value": 10.0,
    },
    "NUDGE": {
        "flag_key": "brain.threshold.nudge.avg_quality_score",
        "rationale_template": (
            "NUDGE decisions averaged outcome_score={avg:.2f} over "
            "{n} samples in the last {days} days — lowering the "
            "avg-quality trigger from {old} to {new} so we nudge "
            "only when quality is actually a problem."
        ),
        # Lowering this threshold makes NUDGE rarer (harder to trip).
        "next_value": lambda cur: round(float(cur) - 0.5, 2),
        "min_value": 1.0,
        "max_value": 10.0,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


async def reflect_once(*, dry_run: bool = False) -> int:
    """Run a single reflection pass.

    Returns the number of proposals written (or that would have been
    written, in ``dry_run`` mode). Errors are caught and logged so a
    transient DB blip never kills the loop.
    """
    try:
        enabled = await get_flag("brain.reflector.enabled", default=False)
    except Exception as exc:
        logger.warning("brain.reflector.flag_read_failed", error=str(exc))
        return 0
    if not enabled:
        logger.debug("brain.reflector.disabled")
        return 0

    try:
        return await _reflect(dry_run=dry_run)
    except Exception as exc:
        logger.error("brain.reflector.failed", error=str(exc))
        return 0


async def run_reflector_loop(
    interval_s: int | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run :func:`reflect_once` periodically until ``stop_event`` is set.

    ``interval_s`` defaults to ``brain.reflector.interval_hours`` × 3600.
    The interval is re-read each loop so operators can speed up tuning
    by lowering the flag without restarting the service.
    """
    logger.info("brain.reflector.starting")
    while True:
        if stop_event is not None and stop_event.is_set():
            break

        await reflect_once()

        # Determine sleep interval for the next pass.
        if interval_s is None:
            try:
                hours = await get_flag(
                    "brain.reflector.interval_hours", default=24
                )
                sleep_for = max(60, int(float(hours) * 3600))
            except Exception:
                sleep_for = 24 * 3600
        else:
            sleep_for = max(60, int(interval_s))

        try:
            if stop_event is not None:
                await asyncio.wait_for(stop_event.wait(), timeout=sleep_for)
                break
            else:
                await asyncio.sleep(sleep_for)
        except asyncio.TimeoutError:
            pass
    logger.info("brain.reflector.stopped")


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


async def _reflect(*, dry_run: bool) -> int:
    min_sample_size = int(
        await get_flag("brain.reflector.min_sample_size", default=5) or 5
    )
    score_threshold = float(
        await get_flag("brain.reflector.score_threshold", default=4) or 4
    )
    lookback_days = int(
        await get_flag("brain.reflector.lookback_days", default=14) or 14
    )

    patterns = await _analyse_patterns(lookback_days=lookback_days)
    if not patterns:
        logger.info(
            "brain.reflector.no_scored_decisions",
            lookback_days=lookback_days,
        )
        return 0

    proposals: list[Proposal] = []
    for pattern in patterns:
        if pattern.sample_size < min_sample_size:
            continue
        if pattern.avg_score >= score_threshold:
            continue
        proposal = await _propose_for_pattern(
            pattern, lookback_days=lookback_days
        )
        if proposal is not None:
            proposals.append(proposal)

    if not proposals:
        logger.info(
            "brain.reflector.no_proposals",
            patterns=len(patterns),
            min_sample_size=min_sample_size,
            score_threshold=score_threshold,
        )
        return 0

    written = 0
    for proposal in proposals:
        if dry_run:
            logger.info(
                "brain.reflector.would_propose",
                flag_key=proposal.flag_key,
                proposed=proposal.proposed_payload,
                sample_size=proposal.sample_size,
                avg_score=proposal.observed_avg_score,
            )
            written += 1
            continue
        try:
            await _persist_proposal(proposal)
            written += 1
        except Exception as exc:
            logger.warning(
                "brain.reflector.persist_failed",
                flag_key=proposal.flag_key, error=str(exc),
            )

    logger.info(
        "brain.reflector.cycle_complete",
        patterns_analysed=len(patterns),
        proposals_written=written,
        dry_run=dry_run,
        lookback_days=lookback_days,
    )
    return written


async def _analyse_patterns(*, lookback_days: int) -> list[Pattern]:
    """Group scored brain_decisions in the lookback window by type."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT
            decision_type,
            COUNT(*) AS n,
            AVG(outcome_score)::float AS avg_score,
            ARRAY_AGG(id ORDER BY created_at DESC) AS ids
        FROM brain_decisions
        WHERE outcome_score IS NOT NULL
          AND created_at >= NOW() - ($1 || ' days')::interval
        GROUP BY decision_type
        ORDER BY decision_type
        """,
        str(lookback_days),
    )
    return [
        Pattern(
            decision_type=r["decision_type"],
            sample_size=int(r["n"]),
            avg_score=float(r["avg_score"] or 0),
            sample_decision_ids=list(r["ids"])[:25],
        )
        for r in rows
    ]


async def _propose_for_pattern(
    pattern: Pattern, *, lookback_days: int
) -> Proposal | None:
    """Turn an under-performing pattern into a concrete flag proposal.

    Returns ``None`` if there is no mapping for the decision_type, the
    flag is missing, or the proposed value would leave its safe range.
    """
    mapping = _PATTERN_TO_FLAG.get(pattern.decision_type)
    if mapping is None:
        logger.debug(
            "brain.reflector.no_mapping",
            decision_type=pattern.decision_type,
        )
        return None

    flag_key = mapping["flag_key"]
    current = await _read_flag_payload(flag_key)
    current_value = (current or {}).get("value")
    if current_value is None:
        logger.warning(
            "brain.reflector.flag_missing", flag_key=flag_key,
        )
        return None

    try:
        new_value = mapping["next_value"](current_value)
    except Exception as exc:
        logger.warning(
            "brain.reflector.next_value_failed",
            flag_key=flag_key, error=str(exc),
        )
        return None

    # Refuse to leave the safe range — operator can override manually.
    if (
        new_value < mapping["min_value"]
        or new_value > mapping["max_value"]
    ):
        logger.info(
            "brain.reflector.proposal_out_of_range",
            flag_key=flag_key,
            current=current_value,
            proposed=new_value,
        )
        return None
    if new_value == current_value:
        return None

    proposed_payload = {**(current or {}), "value": new_value}
    rationale = mapping["rationale_template"].format(
        avg=pattern.avg_score,
        n=pattern.sample_size,
        days=lookback_days,
        old=current_value,
        new=new_value,
    )
    evidence = {
        "decision_type": pattern.decision_type,
        "sample_size": pattern.sample_size,
        "avg_outcome_score": round(pattern.avg_score, 2),
        "lookback_days": lookback_days,
        "sample_decision_ids": pattern.sample_decision_ids,
    }
    return Proposal(
        flag_key=flag_key,
        current_payload=current,
        proposed_payload=proposed_payload,
        rationale=rationale,
        supporting_evidence=evidence,
        sample_size=pattern.sample_size,
        observed_avg_score=round(pattern.avg_score, 2),
    )


async def _read_flag_payload(flag_key: str) -> dict[str, Any] | None:
    """Read the raw payload jsonb for a flag, bypassing the in-process
    cache so the Reflector always sees the current operator state.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT payload FROM feature_flags WHERE key = $1",
        flag_key,
    )
    if row is None:
        return None
    payload = row["payload"] or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return None
    return payload if isinstance(payload, dict) else None


async def _persist_proposal(proposal: Proposal) -> None:
    """UPSERT the proposal into ``brain_flag_proposals``.

    Idempotence: a partial unique index on ``(flag_key) WHERE status =
    'pending'`` guarantees at most one pending proposal per flag at any
    time. On conflict we refresh the evidence + sample_size so the
    reviewer always sees the most recent observation.
    """
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO brain_flag_proposals
            (flag_key, current_payload, proposed_payload, rationale,
             supporting_evidence, sample_size, observed_avg_score, status)
        VALUES ($1, $2::jsonb, $3::jsonb, $4, $5::jsonb, $6, $7, 'pending')
        ON CONFLICT (flag_key) WHERE status = 'pending' DO UPDATE
        SET proposed_payload = EXCLUDED.proposed_payload,
            current_payload  = EXCLUDED.current_payload,
            rationale        = EXCLUDED.rationale,
            supporting_evidence = EXCLUDED.supporting_evidence,
            sample_size      = EXCLUDED.sample_size,
            observed_avg_score = EXCLUDED.observed_avg_score,
            created_at       = NOW()
        """,
        proposal.flag_key,
        json.dumps(proposal.current_payload) if proposal.current_payload else None,
        json.dumps(proposal.proposed_payload),
        proposal.rationale,
        json.dumps(proposal.supporting_evidence),
        proposal.sample_size,
        proposal.observed_avg_score,
    )
    logger.info(
        "brain.reflector.proposal_written",
        flag_key=proposal.flag_key,
        proposed=proposal.proposed_payload,
        sample_size=proposal.sample_size,
        avg_score=proposal.observed_avg_score,
    )
