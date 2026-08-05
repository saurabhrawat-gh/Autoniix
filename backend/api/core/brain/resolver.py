"""Stale decision resolver — auto-closes brain_decisions that have expired.

A HALT/HOLD decision becomes stale when:
  * It was created more than N days ago (configurable via
    ``brain.resolver.stale_days``, default 7), AND
  * ``resolved_at`` is still NULL.

This is a safety net: if the Brain issued a HALT/HOLD but the operator never
manually resolved it, the pipeline would stay blocked forever. The resolver
runs on a configurable interval and stamps ``resolved_at = NOW()`` with an
``outcome`` of ``{"auto_resolved": true, "reason": "stale"}``.

Decisions of type ADVISE or NUDGE are resolved after 1 day (they are
informational and have a shorter useful life).

AE-P1 / Brain Service.
"""
from __future__ import annotations

import asyncio

import structlog

from core.db import get_pool
from core.flags import get_flag

logger = structlog.get_logger()

_HALTING_TYPES = ("HALT", "HOLD")
_SOFT_TYPES = ("ADVISE", "NUDGE", "RESUME")


async def resolve_stale(dry_run: bool = False) -> int:
    """Stamp ``resolved_at`` on stale unresolved decisions.

    Returns the count of decisions resolved. If *dry_run* is True, runs the
    query but does not commit any changes (for testing / preview).
    """
    try:
        return await _resolve(dry_run=dry_run)
    except Exception as exc:
        logger.error("brain.resolver.failed", error=str(exc))
        return 0


async def _resolve(dry_run: bool) -> int:
    stale_hard_days = await get_flag("brain.resolver.stale_hard_days", default=7)
    stale_soft_days = await get_flag("brain.resolver.stale_soft_days", default=1)

    pool = await get_pool()

    result = await pool.fetchrow(
        """
        WITH resolved AS (
            UPDATE brain_decisions
            SET
                resolved_at = NOW(),
                outcome = jsonb_build_object(
                    'auto_resolved', true,
                    'reason', 'stale',
                    'stale_hard_days', $1,
                    'stale_soft_days', $2
                )
            WHERE resolved_at IS NULL
              AND (
                    (decision_type = ANY($3::text[])
                     AND created_at < NOW() - ($1 || ' days')::interval)
                 OR (decision_type = ANY($4::text[])
                     AND created_at < NOW() - ($2 || ' days')::interval)
              )
            RETURNING id
        )
        SELECT COUNT(*) AS resolved_count FROM resolved
        """,
        str(stale_hard_days),
        str(stale_soft_days),
        list(_HALTING_TYPES),
        list(_SOFT_TYPES),
    )

    count = int(result["resolved_count"] or 0)
    if count > 0:
        logger.info(
            "brain.resolver.resolved",
            count=count,
            dry_run=dry_run,
            stale_hard_days=stale_hard_days,
            stale_soft_days=stale_soft_days,
        )
    return count


async def run_resolver_loop(
    interval_s: int = 3600, stop_event: asyncio.Event | None = None
) -> None:
    """Run the resolver periodically until *stop_event* is set."""
    logger.info("brain.resolver.starting", interval_s=interval_s)
    while True:
        if stop_event is not None and stop_event.is_set():
            break
        await resolve_stale()
        try:
            if stop_event is not None:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_s)
                break
            else:
                await asyncio.sleep(interval_s)
        except asyncio.TimeoutError:
            pass
    logger.info("brain.resolver.stopped")
