"""Phase 8 first-deploy backfill — one-shot NichePulseRefreshWorkflow run.

Normally scheduled weekly (Sun 05:00 UTC). This script triggers an immediate run
so niche-pulse tables are seeded on day one instead of waiting up to 7 days.

Usage:
    python -m scripts.backfill_niche_pulse [--temporal-host localhost:7233]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta

import asyncpg
from temporalio.client import Client

from core.config import settings


async def main(temporal_host: str) -> None:
    conn = await asyncpg.connect(
        host=settings.db_host, port=settings.db_port, database=settings.db_name,
        user=settings.db_user, password=settings.db_password,
    )
    try:
        niches = [r["niche"] for r in await conn.fetch(
            "SELECT DISTINCT niche FROM channels "
            "WHERE status = 'active' AND niche IS NOT NULL ORDER BY niche"
        )]
    finally:
        await conn.close()

    if not niches:
        print("⚠️  No active niches found — nothing to backfill.")
        return

    print(f"Active niches: {', '.join(niches)}\n")

    print(f"Connecting to Temporal at {temporal_host} …")
    try:
        client = await Client.connect(temporal_host)
    except Exception as exc:
        print(f"❌  Temporal unreachable: {exc}", file=sys.stderr)
        sys.exit(1)

    handle = await client.start_workflow(
        "NichePulseRefreshWorkflow",
        id="backfill-niche-pulse-manual",
        task_queue="scheduler",
        execution_timeout=timedelta(minutes=30),
    )
    print(f"  Workflow started — ID: {handle.id}")
    print("  Waiting for completion …")

    try:
        result = await handle.result()
        print(f"\n✅  Niche-pulse backfill complete: {result}")
    except Exception as exc:
        print(f"\n❌  Workflow failed: {exc}", file=sys.stderr)
        sys.exit(1)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Phase 8 niche-pulse backfill")
    parser.add_argument("--temporal-host", default="localhost:7233")
    args = parser.parse_args()
    asyncio.run(main(args.temporal_host))


if __name__ == "__main__":
    _main()
