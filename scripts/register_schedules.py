"""Register Temporal workflow schedules for production.

Run this ONCE after first deploy (or re-run idempotently — existing schedules
are left unchanged; only missing ones are created).

Usage:
    python -m scripts.register_schedules [--temporal-host localhost:7233]

Schedules created:
    gate-calibration-weekly  — GateCalibrationWorkflow  — Sun 04:00 UTC
    niche-pulse-weekly       — NichePulseRefreshWorkflow — Sun 05:00 UTC
    retention-fetch-daily    — RetentionFetchWorkflow    — daily 03:00 UTC
    model-maintenance-weekly — ModelMaintenanceWorkflow  — Sun 06:00 UTC
    daily-scheduler          — DailySchedulerWorkflow    — daily 07:00 UTC
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow
from temporalio.client import ScheduleAlreadyRunningError, ScheduleCalendarSpec, ScheduleRange
from temporalio.client import ScheduleSpec, ScheduleState
from temporalio.service import RPCError


_SCHEDULES: list[dict] = [
    {
        "id": "gate-calibration-weekly",
        "workflow": "GateCalibrationWorkflow",
        "task_queue": "scheduler",
        "cron": "0 4 * * 0",  # Sun 04:00 UTC
        "note": "Weekly quality-gate threshold tuning across all niches",
    },
    {
        "id": "niche-pulse-weekly",
        "workflow": "NichePulseRefreshWorkflow",
        "task_queue": "scheduler",
        "cron": "0 5 * * 0",  # Sun 05:00 UTC (1h after gate-calibration)
        "note": "Weekly niche trend-signal refresh",
    },
    {
        "id": "retention-fetch-daily",
        "workflow": "RetentionFetchWorkflow",
        "task_queue": "scheduler",
        "cron": "0 3 * * *",  # Daily 03:00 UTC
        "note": "Daily YouTube Analytics retention-curve ingestion",
    },
    {
        "id": "model-maintenance-weekly",
        "workflow": "ModelMaintenanceWorkflow",
        "task_queue": "scheduler",
        "cron": "0 6 * * 0",  # Sun 06:00 UTC (after gate-calibration + niche-pulse)
        "note": "Weekly ML model freshness check and retraining",
    },
    {
        "id": "daily-scheduler",
        "workflow": "DailySchedulerWorkflow",
        "task_queue": "scheduler",
        "cron": "0 7 * * *",  # Daily 07:00 UTC — trigger video production
        "note": "Daily video production trigger for all active channels",
    },
    {
        "id": "provider-health-beat",
        "workflow": "HealthBeatWorkflow",
        "task_queue": "scheduler",
        "cron": "*/5 * * * *",  # Every 5 minutes
        "note": "AE-75: Health-check all enabled provider credentials every 5 min",
    },
    {
        "id": "change-request-expiry",
        "workflow": "ChangeRequestExpiryWorkflow",
        "task_queue": "scheduler",
        "cron": "0 * * * *",  # Hourly
        "note": "AE-76: Expire stale provider change requests after 7 days",
    },
]


def _cron_to_spec(cron: str) -> ScheduleSpec:
    """Convert a simple 5-field cron string to a ScheduleSpec.

    Supports:
    - ``*``          — wildcard (match all)
    - integer        — exact value
    - ``*/N``        — every N units → converted to a ScheduleIntervalSpec
    """
    from temporalio.client import ScheduleIntervalSpec

    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"Expected 5-field cron, got: {cron!r}")
    minute, hour, dom, month, dow = parts

    # Detect interval-only expressions like "*/5 * * * *"
    if minute.startswith("*/") and all(p == "*" for p in [hour, dom, month, dow]):
        interval_minutes = int(minute[2:])
        return ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(minutes=interval_minutes))])

    def _range(val: str, offset: int = 0) -> list[ScheduleRange]:
        if val == "*":
            return []  # match all
        return [ScheduleRange(start=int(val) + offset, end=int(val) + offset)]

    return ScheduleSpec(
        calendars=[
            ScheduleCalendarSpec(
                minute=_range(minute),
                hour=_range(hour),
                day_of_month=_range(dom),
                month=_range(month),
                day_of_week=_range(dow),
            )
        ]
    )


async def register_all(temporal_host: str) -> None:
    try:
        client = await Client.connect(temporal_host)
    except Exception as exc:
        print(f"⚠️  Temporal unreachable at {temporal_host}: {exc}", file=sys.stderr)
        print("Skipping schedule registration — will retry on next deploy.")
        return

    created = 0
    skipped = 0
    failed = 0

    for s in _SCHEDULES:
        schedule_id = s["id"]
        try:
            await client.create_schedule(
                schedule_id,
                Schedule(
                    action=ScheduleActionStartWorkflow(
                        s["workflow"],
                        id=schedule_id,
                        task_queue=s["task_queue"],
                    ),
                    spec=_cron_to_spec(s["cron"]),
                    state=ScheduleState(note=s["note"]),
                ),
            )
            print(f"  ✅ Created  {schedule_id}  ({s['cron']})")
            created += 1
        except (RPCError, ScheduleAlreadyRunningError) as exc:
            if isinstance(exc, ScheduleAlreadyRunningError) or "already exists" in str(exc).lower():
                print(f"  ⏭  Skipped  {schedule_id}  (already exists)")
                skipped += 1
            else:
                print(f"  ⚠️  Warning  {schedule_id}: {exc} — will retry on next deploy", file=sys.stderr)
                failed += 1

    print(f"\nDone — {created} created, {skipped} already existed, {failed} deferred.")
    if failed and not created and not skipped:
        print("⚠️  All schedules failed — Temporal may be degraded.", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Register Temporal workflow schedules")
    parser.add_argument(
        "--temporal-host",
        default="localhost:7233",
        help="Temporal frontend address (default: localhost:7233)",
    )
    args = parser.parse_args()
    print(f"Connecting to Temporal at {args.temporal_host} …\n")
    asyncio.run(register_all(args.temporal_host))


if __name__ == "__main__":
    main()
