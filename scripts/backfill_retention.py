"""Phase 9 first-deploy backfill — one-shot RetentionFetchWorkflow with limit=200.

Pulls audience-retention curves for the 200 most recent delivered videos aged 7-30 days.
Normally runs daily at 03:00 UTC. This seeds the data immediately so the Phase 11 calibrator
doesn't fall back to tier labels while waiting for the first scheduled cron run.

Usage:
    python -m scripts.backfill_retention [--limit 200] [--temporal-host localhost:7233]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta

from temporalio.client import Client


async def main(temporal_host: str, limit: int) -> None:
    print(f"Connecting to Temporal at {temporal_host} …")
    try:
        client = await Client.connect(temporal_host)
    except Exception as exc:
        print(f"❌  Temporal unreachable: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Starting RetentionFetchWorkflow (limit={limit}) …")
    handle = await client.start_workflow(
        "RetentionFetchWorkflow",
        {"limit": limit},
        id="backfill-retention-manual",
        task_queue="scheduler",
        execution_timeout=timedelta(hours=1),
    )
    print(f"  Workflow started — ID: {handle.id}")
    print("  Waiting for completion (may take a few minutes) …")

    try:
        result = await handle.result()
        fetched = result.get("fetched", 0)
        skipped = result.get("skipped", 0)
        failed  = result.get("failed", 0)
        print(f"\n✅  Done — fetched={fetched}, skipped={skipped}, failed={failed}")
        if failed:
            print(f"⚠️  {failed} video(s) failed — likely no analytics yet (normal for recent uploads).")
    except Exception as exc:
        print(f"\n❌  Workflow failed: {exc}", file=sys.stderr)
        sys.exit(1)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Phase 9 retention-curve backfill")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--temporal-host", default="localhost:7233")
    args = parser.parse_args()
    asyncio.run(main(args.temporal_host, args.limit))


if __name__ == "__main__":
    _main()
