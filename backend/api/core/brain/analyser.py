"""Brain Pattern Analyser — reads DB signals for a channel.

Produces a :class:`ChannelSignals` snapshot that the decision engine uses
to determine whether a HALT, HOLD, NUDGE, or ADVISE decision is warranted.

All queries are read-only and tolerant of missing rows — a brand-new channel
with no history returns safe zero-defaults so the engine never panics.

AE-P1 / Brain Service.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import structlog

from core.db import get_pool

logger = structlog.get_logger()

_RECENT_VIDEOS = 10
_FAILURE_WINDOW_H = 48


@dataclass
class ChannelSignals:
    channel_id: str

    avg_composite_score: float = 0.0
    min_composite_score: float = 0.0
    recent_scores: list[float] = field(default_factory=list)

    avg_cost_per_video: float = 0.0
    latest_cost: float = 0.0
    cost_spike_factor: float = 1.0

    consecutive_failures: int = 0
    total_recent_failures: int = 0

    total_delivered: int = 0
    total_failed: int = 0

    daily_budget_limit: float = 0.0
    daily_spend_today: float = 0.0
    daily_budget_remaining: float = 0.0

    @property
    def is_new_channel(self) -> bool:
        return self.total_delivered == 0

    @property
    def budget_exhausted(self) -> bool:
        return self.daily_budget_limit > 0 and self.daily_spend_today >= self.daily_budget_limit


async def analyse_channel(channel_id: str) -> ChannelSignals:
    """Return a :class:`ChannelSignals` snapshot for *channel_id*.

    Never raises — on any DB error returns a zeroed snapshot logged at WARN.
    """
    try:
        return await _fetch_signals(channel_id)
    except Exception as exc:
        logger.warning("brain.analyser.failed", channel_id=channel_id, error=str(exc))
        return ChannelSignals(channel_id=channel_id)


async def _fetch_signals(channel_id: str) -> ChannelSignals:
    pool = await get_pool()

    quality_task = _fetch_quality(pool, channel_id)
    cost_task = _fetch_cost(pool, channel_id)
    failure_task = _fetch_failures(pool, channel_id)
    volume_task = _fetch_volume(pool, channel_id)
    budget_task = _fetch_budget(pool, channel_id)

    (scores, (avg_cost, latest_cost), (consec, total_fail), (delivered, failed), budget) = await asyncio.gather(
        quality_task, cost_task, failure_task, volume_task, budget_task
    )

    avg_score = sum(scores) / len(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0
    spike = (latest_cost / avg_cost) if avg_cost > 0 else 1.0
    remaining = max(budget["limit"] - budget["today"], 0.0)

    return ChannelSignals(
        channel_id=channel_id,
        avg_composite_score=round(avg_score, 2),
        min_composite_score=round(min_score, 2),
        recent_scores=scores,
        avg_cost_per_video=round(avg_cost, 4),
        latest_cost=round(latest_cost, 4),
        cost_spike_factor=round(spike, 2),
        consecutive_failures=consec,
        total_recent_failures=total_fail,
        total_delivered=delivered,
        total_failed=failed,
        daily_budget_limit=budget["limit"],
        daily_spend_today=round(budget["today"], 4),
        daily_budget_remaining=round(remaining, 4),
    )


async def _fetch_quality(pool, channel_id: str) -> list[float]:
    rows = await pool.fetch(
        """
        SELECT final_composite_score
        FROM videos
        WHERE channel_id = $1
          AND status = 'delivered'
          AND final_composite_score IS NOT NULL
        ORDER BY created_at DESC
        LIMIT $2
        """,
        channel_id,
        _RECENT_VIDEOS,
    )
    return [float(r["final_composite_score"]) for r in rows]


async def _fetch_cost(pool, channel_id: str) -> tuple[float, float]:
    """Return (avg_cost_per_video, latest_video_cost)."""
    rows = await pool.fetch(
        """
        SELECT content_id, SUM(cost_usd) AS total
        FROM api_usage
        WHERE channel_id = $1
        GROUP BY content_id
        ORDER BY MAX(created_at) DESC
        LIMIT $2
        """,
        channel_id,
        _RECENT_VIDEOS,
    )
    if not rows:
        return 0.0, 0.0
    costs = [float(r["total"]) for r in rows]
    return sum(costs) / len(costs), costs[0]


async def _fetch_failures(pool, channel_id: str) -> tuple[int, int]:
    """Return (consecutive_failures, total_recent_failures)."""
    rows = await pool.fetch(
        """
        SELECT status
        FROM videos
        WHERE channel_id = $1
          AND created_at > NOW() - ($2 || ' hours')::interval
        ORDER BY created_at DESC
        LIMIT 20
        """,
        channel_id,
        str(_FAILURE_WINDOW_H),
    )
    statuses = [r["status"] for r in rows]
    total_fail = sum(1 for s in statuses if s == "failed")

    consec = 0
    for s in statuses:
        if s == "failed":
            consec += 1
        else:
            break

    return consec, total_fail


async def _fetch_volume(pool, channel_id: str) -> tuple[int, int]:
    row = await pool.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'delivered') AS delivered,
            COUNT(*) FILTER (WHERE status = 'failed')    AS failed
        FROM videos
        WHERE channel_id = $1
        """,
        channel_id,
    )
    if not row:
        return 0, 0
    return int(row["delivered"] or 0), int(row["failed"] or 0)


async def _fetch_budget(pool, channel_id: str) -> dict:
    """Return {limit, today} — limit=0 means no cap configured."""
    row = await pool.fetchrow(
        "SELECT daily_budget_limit FROM channels WHERE channel_id = $1",
        channel_id,
    )
    limit = float(row["daily_budget_limit"]) if row and row["daily_budget_limit"] else 0.0

    spend_row = await pool.fetchrow(
        """
        SELECT COALESCE(SUM(cost_usd), 0) AS today
        FROM api_usage
        WHERE channel_id = $1
          AND created_at >= CURRENT_DATE
        """,
        channel_id,
    )
    today = float(spend_row["today"]) if spend_row else 0.0
    return {"limit": limit, "today": today}
