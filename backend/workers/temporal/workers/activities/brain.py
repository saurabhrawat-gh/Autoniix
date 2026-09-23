"""Temporal activities exposing the Brain's HALT/HOLD signal to workflows.

The activity is intentionally minimal — it never decides anything itself.
It only reads ``brain_decisions`` for the requested scope and returns the
latest unresolved directive, or ``{}`` when the workflow should proceed
unchanged.

Safety rails — absolute and non-negotiable:

1. When ``brain.advisory_mode`` is ``TRUE`` (the default), the activity
   short-circuits to ``{}``. The Brain has not been hardened in production
   yet; advisory mode means "log decisions but never auto-halt."
2. When the ``brain_decisions`` table is empty for the scope, the activity
   returns ``{}``.
3. On any DB error, the activity logs and returns ``{}`` — the activity
   must NEVER itself break a workflow.

This module is part of AE-511 / P0 — Agentic Foundation.
"""

from __future__ import annotations

import structlog
from temporalio import activity

from core.db import get_pool
from core.flags import get_flag

logger = structlog.get_logger()

HALTING_ACTIONS: frozenset[str] = frozenset({"HALT", "HOLD"})


@activity.defn(name="brain_directive_check_activity")
async def brain_directive_check_activity(channel_id: str, content_id: str | None) -> dict:
    """Return the latest unresolved Brain directive for the given scope.

    Resolution order:

    1. Check ``brain.advisory_mode``. If TRUE, return ``{}`` immediately.
    2. Fetch the latest unresolved row scoped to ``video=content_id``.
    3. Fall back to the latest unresolved ``channel=channel_id`` row.
    4. Fall back to the latest unresolved ``global`` row.
    5. If none, return ``{}``.

    The activity never raises — DB errors are caught + logged + treated
    as "no directive" so workflow availability is independent of Brain
    availability.
    """
    try:
        if await get_flag("brain.advisory_mode", default=True):
            return {}
    except Exception as exc:
        logger.warning(
            "brain_directive_check.flag_read_failed",
            channel_id=channel_id,
            error=str(exc),
        )
        return {}

    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT id, decision_type, scope, scope_id, directive, reasoning, confidence
            FROM brain_decisions
            WHERE resolved_at IS NULL
              AND (
                    (scope = 'video'   AND scope_id = $1)
                 OR (scope = 'channel' AND scope_id = $2)
                 OR (scope = 'global'  AND scope_id IS NULL)
              )
            ORDER BY
                CASE scope WHEN 'video' THEN 0 WHEN 'channel' THEN 1 ELSE 2 END,
                created_at DESC
            LIMIT 1
            """,
            content_id,
            channel_id,
        )
    except Exception as exc:
        logger.warning(
            "brain_directive_check.db_failed",
            channel_id=channel_id,
            content_id=content_id,
            error=str(exc),
        )
        return {}

    if row is None:
        return {}

    action = (row["decision_type"] or "").upper()
    if action not in HALTING_ACTIONS:
        return {
            "action": action,
            "decision_id": row["id"],
            "scope": row["scope"],
            "directive": dict(row["directive"]) if row["directive"] else {},
            "reasoning": row["reasoning"] or "",
            "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
            "halting": False,
        }

    return {
        "action": action,
        "decision_id": row["id"],
        "scope": row["scope"],
        "directive": dict(row["directive"]) if row["directive"] else {},
        "reasoning": row["reasoning"] or "",
        "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
        "halting": True,
    }
