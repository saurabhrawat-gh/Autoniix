"""Brain Service entry point.

Runs three concurrent tasks:
  1. Pipeline event consumer (Redis pub/sub)
  2. Stale decision resolver (periodic, default every 1h)
  3. Health HTTP server (FastAPI on port 8012)

Start with::

    python -m src.services.brain.main

Or via Makefile::

    make brain

Environment:
  All config comes from ``src/config.py`` (reads .env). No additional vars needed.

AE-P1 / Brain Service.
"""
from __future__ import annotations

import asyncio
import os
import signal

import structlog
import uvicorn
from fastapi import FastAPI

from src.agents.registry import AgentRegistry
from src.db import close_pool, get_pool
from src.services.brain.agent import BrainAgent
from src.services.brain.consumer import run_consumer
from src.services.brain.resolver import run_resolver_loop

# Register BrainAgent with the agentic framework at import time so any
# component that asks ``AgentRegistry.get("brain")`` gets a working instance.
AgentRegistry.register(BrainAgent())

logger = structlog.get_logger()

_HEALTH_PORT = int(os.getenv("BRAIN_PORT", "8015"))
_RESOLVER_INTERVAL_S = int(os.getenv("BRAIN_RESOLVER_INTERVAL_S", "3600"))


# ─────────────────────────────────────────────────────────────────────────────
# Health endpoint
# ─────────────────────────────────────────────────────────────────────────────

health_app = FastAPI(title="Brain Service", version="0.1.0")


@health_app.get("/health")
async def health():
    """Lightweight health probe — checks DB connectivity."""
    try:
        pool = await get_pool()
        await pool.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    status = "healthy" if db_ok else "degraded"
    return {"status": status, "service": "brain", "components": {"db": db_ok}}


@health_app.get("/decisions/recent")
async def recent_decisions(limit: int = 20):
    """Return the most recent brain_decisions rows (for dashboard/debug)."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, decision_type, scope, scope_id, trigger_source,
               reasoning, directive, confidence, created_at, resolved_at
        FROM brain_decisions
        ORDER BY created_at DESC
        LIMIT $1
        """,
        limit,
    )
    return {"decisions": [dict(r) for r in rows]}


@health_app.post("/decisions/{decision_id}/resolve")
async def resolve_decision(decision_id: int, reason: str = "manual"):
    """Manually resolve an open decision."""
    import json as _json
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE brain_decisions
        SET resolved_at = NOW(),
            outcome = $1::jsonb
        WHERE id = $2 AND resolved_at IS NULL
        RETURNING id, decision_type, scope_id
        """,
        _json.dumps({"resolved_by": "manual", "reason": reason}),
        decision_id,
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Decision not found or already resolved")
    logger.info(
        "brain.decision.manually_resolved",
        decision_id=decision_id,
        reason=reason,
    )
    return {"resolved": True, "decision_id": row["id"]}


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

async def _run_all() -> None:
    stop_event = asyncio.Event()

    def _handle_signal(*_):
        logger.info("brain.shutdown_requested")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    logger.info("brain.starting", health_port=_HEALTH_PORT)

    config = uvicorn.Config(
        health_app,
        host="0.0.0.0",
        port=_HEALTH_PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)

    async def _run_health():
        await server.serve()

    async def _run_consumer():
        await run_consumer(stop_event=stop_event)

    async def _run_resolver():
        await run_resolver_loop(interval_s=_RESOLVER_INTERVAL_S, stop_event=stop_event)

    async def _shutdown_health():
        await stop_event.wait()
        server.should_exit = True

    await asyncio.gather(
        _run_health(),
        _run_consumer(),
        _run_resolver(),
        _shutdown_health(),
        return_exceptions=True,
    )

    await close_pool()
    logger.info("brain.stopped")


if __name__ == "__main__":
    asyncio.run(_run_all())
