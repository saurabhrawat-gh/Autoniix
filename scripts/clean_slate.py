"""CLI equivalent of the /api/admin/clean-slate endpoint.

Wipes all job history (DB + MinIO + Temporal + Redis) while preserving channel
configs, brand profiles, prompts, and ML models.

Usage (from the host, via docker):
    docker compose exec dashboard-bff python -m scripts.clean_slate --yes

Or locally with env vars set:
    python -m scripts.clean_slate --yes
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import structlog

from core.db import get_pool
from core.redis_client import get_redis

logger = structlog.get_logger()


async def _terminate_workflows() -> int:
    count = 0
    try:
        from temporalio.client import Client

        from core.config import settings

        client = await Client.connect(
            settings.temporal_host,
            namespace=getattr(settings, "temporal_namespace", "default"),
        )
        for wf_type in ("VideoProductionWorkflow", "DailySchedulerWorkflow"):
            query = f'WorkflowType = "{wf_type}" AND ExecutionStatus = "Running"'
            async for wf in client.list_workflows(query=query):
                try:
                    await client.get_workflow_handle(wf.id).terminate("Clean slate (CLI)")
                    count += 1
                except Exception as exc:
                    logger.warning("terminate.failed", workflow_id=wf.id, error=str(exc))
    except Exception as exc:
        logger.warning("temporal.scan_failed", error=str(exc))
    return count


async def _truncate_tables() -> list[str]:
    pool = await get_pool()
    tables = [
        "videos",
        "job_events",
        "analytics_records",
        "feedback_loop",
        "experiment_assignments",
        "experiment_outcomes",
        "performance_outcomes",
        "script_outcomes",
    ]
    done: list[str] = []
    for t in tables:
        try:
            await pool.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
            done.append(t)
        except Exception as exc:
            logger.warning("truncate.failed", table=t, error=str(exc))
    return done


def _wipe_minio() -> int:
    total = 0
    try:
        from providers.storage.minio_provider import MinIOStorage

        storage = MinIOStorage()
        for prefix in ("test/", "prod/"):
            try:
                total += storage.delete_prefix(prefix)
            except Exception as exc:
                logger.warning("minio.prefix_failed", prefix=prefix, error=str(exc))
    except Exception as exc:
        logger.warning("minio.init_failed", error=str(exc))
    return total


async def _clear_redis() -> int:
    total = 0
    try:
        r = await get_redis()
        for pattern in ("lock:channel:*", "progress:*"):
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await r.delete(*keys)
                    total += len(keys)
                if cursor == 0:
                    break
    except Exception as exc:
        logger.warning("redis.scan_failed", error=str(exc))
    return total


async def main() -> int:
    parser = argparse.ArgumentParser(description="Wipe all job history")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation")
    args = parser.parse_args()

    if not args.yes:
        print("This will DELETE all videos, job events, analytics, renders, and checkpoints.")
        print("Channels, brand profiles, system config, and ML models are preserved.")
        reply = input("Type RESET to confirm: ").strip()
        if reply != "RESET":
            print("Aborted.")
            return 1

    print("→ Terminating running Temporal workflows...")
    wf_count = await _terminate_workflows()
    print(f"  terminated: {wf_count}")

    print("→ Truncating DB tables...")
    tables = await _truncate_tables()
    print(f"  cleared: {', '.join(tables) or '(none)'}")

    print("→ Wiping MinIO blobs (test/ + prod/)...")
    blob_count = _wipe_minio()
    print(f"  deleted: {blob_count} object(s)")

    print("→ Clearing Redis locks and progress keys...")
    redis_count = await _clear_redis()
    print(f"  deleted: {redis_count} key(s)")

    print("\n✓ Clean slate complete.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
