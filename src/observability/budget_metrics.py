"""Budget Prometheus gauge refresher.

Runs as a background task inside the dashboard-BFF process. Every 60 seconds
it queries ``channels`` + ``videos`` to compute today's API spend and budget
limit per channel, then pushes the values into ``YT_DAILY_API_SPEND`` and
``YT_DAILY_BUDGET_LIMIT`` gauges so the Prometheus alert rules added in Phase C
can actually fire.

Usage (in BFF lifespan):

    from src.observability.budget_metrics import start_budget_gauge_refresh
    asyncio.create_task(start_budget_gauge_refresh(get_pool))
"""
from __future__ import annotations

import asyncio

import structlog

from src.observability.metrics import YT_DAILY_API_SPEND, YT_DAILY_BUDGET_LIMIT

logger = structlog.get_logger()

_REFRESH_INTERVAL_S = 60


async def _refresh_once(pool: object) -> None:
    """Single pass: query spend + limits and update gauges."""
    try:
        rows = await pool.fetch(  # type: ignore[attr-defined]
            """
            SELECT
                c.channel_id,
                COALESCE(c.max_daily_api_spend, 5.0)              AS budget_limit,
                COALESCE(SUM(v.total_cost), 0.0)                  AS today_spend
            FROM channels c
            LEFT JOIN videos v
                ON v.channel_id = c.channel_id
                AND v.created_at::date = CURRENT_DATE
            WHERE c.status = 'active'
            GROUP BY c.channel_id, c.max_daily_api_spend
            """
        )
        for row in rows:
            cid = row["channel_id"]
            YT_DAILY_API_SPEND.labels(channel_id=cid).set(float(row["today_spend"]))
            YT_DAILY_BUDGET_LIMIT.labels(channel_id=cid).set(float(row["budget_limit"]))
    except Exception as exc:
        logger.warning("budget_metrics.refresh_failed", error=str(exc))


async def start_budget_gauge_refresh(get_pool_fn: object) -> None:
    """Infinite loop — meant to be spawned as an asyncio task at BFF startup.

    Args:
        get_pool_fn: The ``get_pool`` coroutine from ``src.db`` (passed in to
                     avoid circular imports at module load time).
    """
    await asyncio.sleep(5)  # brief delay so DB pool is fully ready
    while True:
        try:
            pool = await get_pool_fn()  # type: ignore[operator]
            await _refresh_once(pool)
        except Exception as exc:
            logger.warning("budget_metrics.task_error", error=str(exc))
        await asyncio.sleep(_REFRESH_INTERVAL_S)
