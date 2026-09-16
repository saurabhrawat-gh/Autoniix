"""AE-76 — Change Request Expiry Beat: Temporal activity + workflow.

Runs hourly via the ``change-request-expiry`` Temporal schedule.
Marks any `pending_admin` or `pending_owner` requests whose
``expires_at`` has passed as ``expired`` and fires notification stubs.
"""

from __future__ import annotations

from typing import Any

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    import structlog

logger = structlog.get_logger()


@activity.defn
async def expire_stale_change_requests() -> dict[str, Any]:
    """Mark timed-out change requests as expired."""
    from core.db import get_pool

    pool = await get_pool()
    rows = await pool.fetch(
        """UPDATE provider_change_requests
              SET status='expired'
            WHERE status IN ('pending_admin', 'pending_owner')
              AND expires_at < NOW()
           RETURNING id, requested_by, category, request_type""",
    )
    expired_ids = [r["id"] for r in rows]
    if expired_ids:
        logger.info("change_request.expired", count=len(expired_ids), ids=expired_ids)
    return {"expired": len(expired_ids), "ids": expired_ids}
