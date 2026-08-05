"""Brain Decision Engine — converts ChannelSignals into brain_decisions rows.

The engine evaluates signals against configurable thresholds (all read from
``feature_flags`` so operators can tune without deploying) and writes a
decision when a threshold is crossed.

Decision priority:
  1. HALT  — hard stop; pipeline must not run. Highest severity.
  2. HOLD  — pause until human reviews. Recoverable.
  3. NUDGE — soft redirect (e.g. "pivot niche"). Pipeline continues.
  4. ADVISE — informational. Never stops anything.

Safety guarantee: when ``brain.advisory_mode`` is TRUE the pipeline ignores
all decisions regardless of type. The engine still WRITES decisions so the
audit trail is complete and operators can review quality before enforcement.

AE-P1 / Brain Service.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from llm.embeddings import EmbeddingConfigError, EmbeddingError, embed_and_store

from core.db import get_pool
from core.flags import get_flag
from services_api.brain.analyser import ChannelSignals

logger = structlog.get_logger()

_SOURCE = "brain-engine"


_DEFAULTS: dict[str, Any] = {
    "brain.threshold.halt.consecutive_failures": 3,
    "brain.threshold.halt.min_quality_score": 5.0,
    "brain.threshold.hold.cost_spike_factor": 3.0,
    "brain.threshold.hold.budget_pct_remaining": 0.05,
    "brain.threshold.nudge.avg_quality_score": 7.0,
}


async def _threshold(key: str) -> Any:
    return await get_flag(key, default=_DEFAULTS.get(key))


async def evaluate(signals: ChannelSignals, content_id: str | None = None) -> dict | None:
    """Evaluate *signals* and write a ``brain_decisions`` row if warranted.

    Returns the written row as a dict (including the ``id``), or ``None`` if
    no threshold was crossed. Never raises.
    """
    try:
        return await _evaluate(signals, content_id)
    except Exception as exc:
        logger.error(
            "brain.engine.evaluate_failed",
            channel_id=signals.channel_id,
            error=str(exc),
        )
        return None


async def _evaluate(signals: ChannelSignals, content_id: str | None) -> dict | None:
    if signals.is_new_channel:
        logger.debug("brain.engine.skip_new_channel", channel_id=signals.channel_id)
        return None

    halt_consec = await _threshold("brain.threshold.halt.consecutive_failures")
    if signals.consecutive_failures >= int(halt_consec):
        return await _write_decision(
            signals=signals,
            content_id=content_id,
            decision_type="HALT",
            confidence=min(0.95, 0.6 + signals.consecutive_failures * 0.1),
            directive={
                "action": "HALT",
                "reason": "consecutive_failures",
                "consecutive_failures": signals.consecutive_failures,
            },
            reasoning=(
                f"Channel {signals.channel_id} has {signals.consecutive_failures} consecutive "
                f"failed videos in the last 48h (threshold: {halt_consec}). "
                "Halting pipeline until root cause is resolved."
            ),
        )

    halt_quality = await _threshold("brain.threshold.halt.min_quality_score")
    if signals.recent_scores and signals.avg_composite_score < float(halt_quality) and len(signals.recent_scores) >= 3:
        return await _write_decision(
            signals=signals,
            content_id=content_id,
            decision_type="HALT",
            confidence=0.80,
            directive={
                "action": "HALT",
                "reason": "quality_floor_breach",
                "avg_composite_score": signals.avg_composite_score,
                "threshold": halt_quality,
            },
            reasoning=(
                f"Average composite score {signals.avg_composite_score:.2f} across the last "
                f"{len(signals.recent_scores)} videos is below the halt floor of {halt_quality}. "
                "Content quality is unacceptably low."
            ),
        )

    hold_spike = await _threshold("brain.threshold.hold.cost_spike_factor")
    if signals.cost_spike_factor >= float(hold_spike):
        return await _write_decision(
            signals=signals,
            content_id=content_id,
            decision_type="HOLD",
            confidence=0.85,
            directive={
                "action": "HOLD",
                "reason": "cost_spike",
                "cost_spike_factor": signals.cost_spike_factor,
                "latest_cost_usd": signals.latest_cost,
                "avg_cost_usd": signals.avg_cost_per_video,
            },
            reasoning=(
                f"Latest video cost ${signals.latest_cost:.4f} is "
                f"{signals.cost_spike_factor:.1f}× the rolling average "
                f"(${signals.avg_cost_per_video:.4f}). Holding pipeline for cost review."
            ),
        )

    hold_budget_pct = await _threshold("brain.threshold.hold.budget_pct_remaining")
    if signals.daily_budget_limit > 0:
        pct_remaining = signals.daily_budget_remaining / signals.daily_budget_limit
        if pct_remaining <= float(hold_budget_pct):
            return await _write_decision(
                signals=signals,
                content_id=content_id,
                decision_type="HOLD",
                confidence=0.95,
                directive={
                    "action": "HOLD",
                    "reason": "budget_exhausted",
                    "daily_limit_usd": signals.daily_budget_limit,
                    "spent_today_usd": signals.daily_spend_today,
                    "remaining_usd": signals.daily_budget_remaining,
                },
                reasoning=(
                    f"Daily budget ${signals.daily_budget_limit:.2f}: "
                    f"${signals.daily_spend_today:.4f} spent, "
                    f"only ${signals.daily_budget_remaining:.4f} ({pct_remaining * 100:.1f}%) left. "
                    "Holding to avoid overrun."
                ),
            )

    nudge_quality = await _threshold("brain.threshold.nudge.avg_quality_score")
    if signals.recent_scores and signals.avg_composite_score < float(nudge_quality) and len(signals.recent_scores) >= 5:
        return await _write_decision(
            signals=signals,
            content_id=content_id,
            decision_type="NUDGE",
            confidence=0.70,
            directive={
                "action": "NUDGE",
                "reason": "below_quality_target",
                "avg_composite_score": signals.avg_composite_score,
                "target": nudge_quality,
                "suggestion": "review_topic_selection",
            },
            reasoning=(
                f"Average composite score {signals.avg_composite_score:.2f} is below the "
                f"quality target of {nudge_quality}. Consider reviewing topic selection, "
                "script depth, or thumbnail strategy."
            ),
        )

    logger.debug(
        "brain.engine.no_decision",
        channel_id=signals.channel_id,
        avg_score=signals.avg_composite_score,
        consecutive_failures=signals.consecutive_failures,
    )
    return None


async def _write_decision(
    *,
    signals: ChannelSignals,
    content_id: str | None,
    decision_type: str,
    confidence: float,
    directive: dict,
    reasoning: str,
) -> dict:
    context_summary = (
        f"channel={signals.channel_id} "
        f"avg_score={signals.avg_composite_score} "
        f"consec_fails={signals.consecutive_failures} "
        f"cost_spike={signals.cost_spike_factor}x "
        f"budget_remaining=${signals.daily_budget_remaining:.2f}"
    )
    embed_text = f"{decision_type}: {reasoning}\n\nContext: {context_summary}"

    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO brain_decisions
            (decision_type, scope, scope_id, trigger_source,
             context_summary, reasoning, directive, confidence)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
        RETURNING id, decision_type, scope, scope_id, directive,
                  reasoning, confidence, created_at
        """,
        decision_type,
        "video" if content_id else "channel",
        content_id or signals.channel_id,
        _SOURCE,
        context_summary,
        reasoning,
        json.dumps(directive),
        round(confidence, 2),
    )

    decision_id = row["id"]

    try:
        await embed_and_store(
            embed_text,
            table="brain_decisions",
            row_id=decision_id,
            column="embedding",
        )
    except (EmbeddingError, EmbeddingConfigError) as exc:
        logger.warning(
            "brain.engine.embed_skipped",
            decision_id=decision_id,
            error=str(exc),
        )

    result = dict(row)
    result["directive"] = directive
    logger.info(
        "brain.engine.decision_written",
        decision_id=decision_id,
        decision_type=decision_type,
        channel_id=signals.channel_id,
        confidence=confidence,
    )
    return result
