"""Phase 11 first-retrain trigger.

Checks whether there are enough delivered videos with retention curves (analytics ingested)
to make a meaningful first training run. If the threshold is met, starts one
ModelMaintenanceWorkflow per active niche.

docs/future/pending.md: 'after 30+ delivered videos with analytics ingested, manually trigger
train_model(niche=...) for one channel and verify n_weighted_samples > 0.'

Usage:
    python -m scripts.trigger_first_retrain [--min-samples 30] [--temporal-host localhost:7233]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta

import asyncpg
from temporalio.client import Client

from core.config import settings

DEFAULT_MIN_SAMPLES = 30


async def main(temporal_host: str, min_samples: int) -> None:
    conn = await asyncpg.connect(
        host=settings.db_host, port=settings.db_port, database=settings.db_name,
        user=settings.db_user, password=settings.db_password,
    )
    try:
        total = await conn.fetchval("""
            SELECT COUNT(DISTINCT v.id)
              FROM videos v
              JOIN retention_curves rc ON rc.content_id = v.id
             WHERE v.status = 'delivered'
        """)
        niches = [r["niche"] for r in await conn.fetch(
            "SELECT DISTINCT niche FROM channels "
            "WHERE status = 'active' AND niche IS NOT NULL ORDER BY niche"
        )]
    finally:
        await conn.close()

    print(f"Delivered videos with analytics: {total}")
    print(f"Active niches: {', '.join(niches) if niches else '(none)'}\n")

    if total < min_samples:
        print(f"⚠️  Only {total} sample(s) — need ≥{min_samples} before first retrain.")
        print("    Run backfill-phase9 first, then re-run this once more videos are delivered.")
        sys.exit(0)

    print(f"✅  {total} samples — threshold met. Starting ModelMaintenanceWorkflow …\n")

    try:
        client = await Client.connect(temporal_host)
    except Exception as exc:
        print(f"❌  Temporal unreachable: {exc}", file=sys.stderr)
        sys.exit(1)

    for niche in niches:
        wf_id = f"first-retrain-{niche.lower().replace(' ', '-')}"
        handle = await client.start_workflow(
            "ModelMaintenanceWorkflow",
            id=wf_id,
            task_queue="scheduler",
            execution_timeout=timedelta(hours=2),
        )
        print(f"  ✅  niche={niche!r} — workflow ID: {handle.id}")

    print(f"\n{len(niches)} workflow(s) started.")
    print("Verify in Temporal UI → Workflows → ModelMaintenanceWorkflow.")
    print("Success criterion: model_health.n_weighted_samples > 0 for each niche.")


def _main() -> None:
    parser = argparse.ArgumentParser(description="Phase 11 first-retrain trigger")
    parser.add_argument(
        "--min-samples", type=int, default=DEFAULT_MIN_SAMPLES,
        help=f"Minimum delivered+analytics videos required (default: {DEFAULT_MIN_SAMPLES})",
    )
    parser.add_argument("--temporal-host", default="localhost:7233")
    args = parser.parse_args()
    asyncio.run(main(args.temporal_host, args.min_samples))


if __name__ == "__main__":
    _main()
