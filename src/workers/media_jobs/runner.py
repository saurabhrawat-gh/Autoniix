"""media_jobs worker — atomic claim + dispatch loop.

The queue (``media_jobs``) holds one row per (asset, kind) pair. This worker
runs N concurrent ``_consume()`` coroutines that each:

1. ATOMICALLY claim the next pending job (``FOR UPDATE SKIP LOCKED`` so
   multiple workers can run side-by-side without lock contention or
   double-dispatch).
2. Look up the asset row.
3. Resolve the handler for ``kind`` (falls back to ``skip_handler``).
4. Execute it, store the outcome in ``media_jobs.status / result / error``,
   and bump ``attempts``.
5. On failure, exponential backoff via ``scheduled_at`` until
   ``max_attempts`` is reached.

The worker is meant to be a separate container (``worker-media-jobs``)
defined in ``docker-compose.yml``. It can also be invoked directly in
development with ``python -m src.workers.media_jobs.runner``.

This module is part of AE-355 / Sprint Library.
"""
from __future__ import annotations

import asyncio
import json
import os
import platform
import signal
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from src.db import get_pool
from src.observability.sentry import init_sentry
from src.workers.media_jobs.handlers import resolve as resolve_handler

logger = structlog.get_logger()

_BACKOFF_BASE_S = 30
_BACKOFF_FACTOR = 4
_BACKOFF_CAP_S = 600

_POLL_INTERVAL_S = 5.0
_DEFAULT_CONCURRENCY = int(os.getenv("MEDIA_JOBS_CONCURRENCY", "2"))


def _worker_id() -> str:
    return f"{platform.node()}:{os.getpid()}"


async def _claim_next_job(pool: Any) -> dict | None:
    """Atomically pull the next runnable job and mark it ``running``.

    ``FOR UPDATE SKIP LOCKED`` is the canonical Postgres queue pattern —
    each worker grabs an exclusive row lock on its candidate row, and any
    other worker landing on the same row simply skips it.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, asset_id, kind, attempts, max_attempts, priority
                  FROM media_jobs
                 WHERE status = 'pending'
                   AND scheduled_at <= NOW()
                 ORDER BY priority ASC, scheduled_at ASC
                 LIMIT 1
                 FOR UPDATE SKIP LOCKED
                """,
            )
            if row is None:
                return None
            await conn.execute(
                """
                UPDATE media_jobs
                   SET status = 'running',
                       started_at = NOW(),
                       worker_id = $2,
                       attempts = attempts + 1
                 WHERE id = $1
                """,
                row["id"],
                _worker_id(),
            )
    return dict(row)


async def _load_asset(pool: Any, asset_id: int) -> dict | None:
    row = await pool.fetchrow(
        "SELECT id, scope, scope_id, kind, display_name, mime_type, bytes, "
        "       content_hash, storage_key, thumbnail_key, tags, ai_tags, metadata "
        "  FROM dam_assets "
        " WHERE id = $1 AND deleted_at IS NULL",
        asset_id,
    )
    return dict(row) if row else None


def _backoff_seconds(attempt: int) -> int:
    return min(_BACKOFF_BASE_S * (_BACKOFF_FACTOR ** max(attempt - 1, 0)), _BACKOFF_CAP_S)


async def _finalize_done(pool: Any, job_id: int, result: dict) -> None:
    await pool.execute(
        """
        UPDATE media_jobs
           SET status = 'done',
               finished_at = NOW(),
               error = NULL,
               result = $2::jsonb
         WHERE id = $1
        """,
        job_id,
        json.dumps(result.get("result") or result),
    )


async def _finalize_skipped(pool: Any, job_id: int, reason: str) -> None:
    await pool.execute(
        """
        UPDATE media_jobs
           SET status = 'skipped',
               finished_at = NOW(),
               error = $2,
               result = '{}'::jsonb
         WHERE id = $1
        """,
        job_id,
        reason[:1000],
    )


async def _finalize_failure(pool: Any, job: dict, reason: str) -> None:
    """Either reschedule (more attempts left) or mark permanently failed."""
    attempts = int(job.get("attempts", 0)) + 1
    max_attempts = int(job.get("max_attempts", 3))
    if attempts >= max_attempts:
        await pool.execute(
            """
            UPDATE media_jobs
               SET status = 'failed',
                   finished_at = NOW(),
                   error = $2
             WHERE id = $1
            """,
            job["id"],
            reason[:1000],
        )
        return
    delay = _backoff_seconds(attempts)
    reschedule_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
    await pool.execute(
        """
        UPDATE media_jobs
           SET status = 'pending',
               started_at = NULL,
               worker_id = NULL,
               error = $2,
               scheduled_at = $3
         WHERE id = $1
        """,
        job["id"],
        reason[:1000],
        reschedule_at,
    )


async def process_one(pool: Any) -> bool:
    """Process a single job. Returns True if a job ran, False if queue empty.

    Public so tests can call it deterministically without spinning the loop.
    """
    claimed = await _claim_next_job(pool)
    if claimed is None:
        return False

    job_id = claimed["id"]
    asset = await _load_asset(pool, claimed["asset_id"])
    if asset is None:
        await _finalize_skipped(pool, job_id, "asset deleted or missing")
        return True

    handler = resolve_handler(claimed["kind"])
    log = logger.bind(job_id=job_id, kind=claimed["kind"], asset_id=asset["id"])
    log.info("media_jobs.claimed")

    try:
        outcome = await handler(pool, asset, claimed)
    except Exception as exc:  # noqa: BLE001 — convert to retry/fail decision
        log.warning("media_jobs.handler_exception", error=str(exc))
        await _finalize_failure(pool, claimed, f"unhandled exception: {exc!s}")
        return True

    status = (outcome or {}).get("status", "failed")
    if status == "done":
        await _finalize_done(pool, job_id, outcome)
        log.info("media_jobs.done")
    elif status == "skipped":
        await _finalize_skipped(pool, job_id, (outcome or {}).get("reason", ""))
        log.info("media_jobs.skipped", reason=(outcome or {}).get("reason"))
    else:
        await _finalize_failure(pool, claimed, (outcome or {}).get("reason", "unknown"))
        log.warning("media_jobs.failed", reason=(outcome or {}).get("reason"))
    return True


async def _consume(pool: Any, stop: asyncio.Event) -> None:
    """One concurrent consumer slot — loop until shutdown."""
    while not stop.is_set():
        try:
            did_work = await process_one(pool)
        except Exception as exc:  # noqa: BLE001 — runner must survive
            logger.warning("media_jobs.runner_loop_error", error=str(exc))
            did_work = False
        if not did_work:
            try:
                await asyncio.wait_for(stop.wait(), timeout=_POLL_INTERVAL_S)
            except asyncio.TimeoutError:
                pass


async def main() -> None:
    init_sentry("worker-media-jobs")
    pool = await get_pool()
    stop = asyncio.Event()

    def _on_signal(*_a: Any) -> None:
        logger.info("media_jobs.shutdown_requested")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:  # pragma: no cover — Windows
            pass

    concurrency = max(_DEFAULT_CONCURRENCY, 1)
    logger.info("media_jobs.starting", concurrency=concurrency, worker_id=_worker_id())
    consumers = [asyncio.create_task(_consume(pool, stop)) for _ in range(concurrency)]
    try:
        await stop.wait()
    finally:
        for c in consumers:
            c.cancel()
        for c in consumers:
            try:
                await c
            except asyncio.CancelledError:
                pass
    logger.info("media_jobs.stopped")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
