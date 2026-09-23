"""Start one VideoProductionWorkflow from the CLI and follow it to completion.

Mirrors what POST /api/channels/{id}/trigger does in the dashboard BFF (videos
row + Temporal start) but needs no auth token, so it can be run from inside any
container that has PYTHONPATH=/app/src::

    docker compose exec -T worker-production \\
        python -m scripts.trigger_video --channel test_97db --max-cost 3 --watch

    # follow an existing run
    docker compose exec -T worker-production \\
        python -m scripts.trigger_video --watch --workflow-id manual-VID_test_97db_20260923_201500

--watch prints every activity as it is scheduled / completes / fails, with the
failure message and the activity input, which is what you need to fix a broken
step. Exit code is 0 on a completed workflow, 1 otherwise.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

from temporalio.client import Client, WorkflowExecutionStatus, WorkflowHandle

from core.db import close_pool, get_pool
from temporal_workers.workflows.types import VideoParams

TASK_QUEUE = "video-production"


def _payload_to_text(payloads) -> str:
    """Render Temporal payloads (activity input/result) compactly."""
    out = []
    for p in payloads or []:
        try:
            data = p.data.decode("utf-8", errors="replace")
        except Exception:
            data = str(p.data)
        if len(data) > 600:
            data = data[:600] + "…"
        out.append(data)
    return " | ".join(out)


async def _start(client: Client, channel_id: str, content_mode: str | None, topics: list[str], max_cost: float) -> str:
    pool = await get_pool()
    ch = await pool.fetchrow("SELECT channel_id, content_mode, status FROM channels WHERE channel_id = $1", channel_id)
    if not ch:
        sys.exit(f"channel {channel_id!r} not found")
    if ch["status"] != "active":
        sys.exit(f"channel {channel_id!r} is {ch['status']!r}, not active")
    mode = content_mode or ch["content_mode"]

    running = await pool.fetchval(
        "SELECT COUNT(*) FROM videos WHERE channel_id = $1 AND content_mode = $2 "
        "AND status NOT IN ('delivered','test_delivered','failed','stopped','superseded','rejected','retrying')",
        channel_id,
        mode,
    )
    if running:
        sys.exit(f"channel already has {running} in-progress {mode} job(s); stop it or wait")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    content_id = f"VID_{channel_id}_{ts}"
    workflow_id = f"manual-{content_id}"
    env = os.getenv("ENVIRONMENT_MODE", "production")
    await pool.execute(
        "UPDATE videos SET status = 'superseded', updated_at = NOW() "
        "WHERE channel_id = $1 AND content_mode = $2 AND status IN ('failed','stopped')",
        channel_id,
        mode,
    )
    await pool.execute(
        "INSERT INTO videos (content_id, channel_id, status, content_mode, environment, updated_at) "
        "VALUES ($1, $2, 'researching', $3, $4, NOW()) ON CONFLICT (content_id) DO NOTHING",
        content_id,
        channel_id,
        mode,
        env,
    )
    try:
        await client.start_workflow(
            "VideoProductionWorkflow",
            VideoParams(
                channel_id=channel_id,
                content_mode=mode,
                topic_candidates=topics,
                max_cost_usd=max_cost,
                content_id=content_id,
            ),
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
    except Exception:
        await pool.execute("DELETE FROM videos WHERE content_id = $1", content_id)
        raise
    print(f"started  workflow_id={workflow_id}  content_id={content_id}  mode={mode}  cap=${max_cost:.2f}")
    return workflow_id


async def _watch(handle: WorkflowHandle, poll_s: float) -> int:
    """Stream activity events until the workflow closes."""
    seen: set[int] = set()
    scheduled: dict[int, str] = {}  # scheduled_event_id -> activity name
    started_at = datetime.now(timezone.utc)
    while True:
        async for ev in handle.fetch_history_events():
            if ev.event_id in seen:
                continue
            seen.add(ev.event_id)
            t = ev.event_time.ToDatetime().strftime("%H:%M:%S") if ev.event_time else "--:--:--"
            if ev.HasField("activity_task_scheduled_event_attributes"):
                a = ev.activity_task_scheduled_event_attributes
                scheduled[ev.event_id] = a.activity_type.name
                print(f"{t}  ▶ scheduled  {a.activity_type.name}")
            elif ev.HasField("activity_task_completed_event_attributes"):
                a = ev.activity_task_completed_event_attributes
                name = scheduled.get(a.scheduled_event_id, "?")
                print(f"{t}  ✓ completed  {name}")
            elif ev.HasField("activity_task_failed_event_attributes"):
                a = ev.activity_task_failed_event_attributes
                name = scheduled.get(a.scheduled_event_id, "?")
                f = a.failure
                cause = f.cause.message if f.HasField("cause") else ""
                print(f"{t}  ✗ FAILED     {name}: {f.message}" + (f"\n             cause: {cause}" if cause else ""))
            elif ev.HasField("activity_task_timed_out_event_attributes"):
                a = ev.activity_task_timed_out_event_attributes
                print(f"{t}  ⏱ TIMED OUT  {scheduled.get(a.scheduled_event_id, '?')}")
            elif ev.HasField("workflow_execution_failed_event_attributes"):
                f = ev.workflow_execution_failed_event_attributes.failure
                print(f"{t}  ✗✗ WORKFLOW FAILED: {f.message}")
                if f.HasField("cause"):
                    print(f"             cause: {f.cause.message}")
            elif ev.HasField("workflow_execution_completed_event_attributes"):
                r = ev.workflow_execution_completed_event_attributes.result
                print(f"{t}  ✓✓ WORKFLOW COMPLETED")
                print("   result:", _payload_to_text(r.payloads))
            elif ev.HasField("workflow_execution_terminated_event_attributes"):
                print(f"{t}  ■ WORKFLOW TERMINATED: {ev.workflow_execution_terminated_event_attributes.reason}")
            elif ev.HasField("workflow_execution_signaled_event_attributes"):
                print(f"{t}  ⚑ signal {ev.workflow_execution_signaled_event_attributes.signal_name}")

        desc = await handle.describe()
        if desc.status not in (WorkflowExecutionStatus.RUNNING, None):
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            print(f"\nstatus={desc.status.name}  watched for {elapsed:.0f}s")
            return 0 if desc.status == WorkflowExecutionStatus.COMPLETED else 1
        await asyncio.sleep(poll_s)


async def _show_last_failure_input(handle: WorkflowHandle) -> None:
    """Print the input of the last failed activity — usually the fastest way to reproduce it against the service."""
    last_failed_sched = None
    sched_inputs: dict[int, tuple[str, str]] = {}
    async for ev in handle.fetch_history_events():
        if ev.HasField("activity_task_scheduled_event_attributes"):
            a = ev.activity_task_scheduled_event_attributes
            sched_inputs[ev.event_id] = (a.activity_type.name, _payload_to_text(a.input.payloads))
        elif ev.HasField("activity_task_failed_event_attributes"):
            last_failed_sched = ev.activity_task_failed_event_attributes.scheduled_event_id
    if last_failed_sched and last_failed_sched in sched_inputs:
        name, inp = sched_inputs[last_failed_sched]
        print(f"\nlast failed activity: {name}\ninput: {inp}")


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", help="channel_id to produce for")
    ap.add_argument("--mode", choices=["short", "long_form"], help="override channel content_mode")
    ap.add_argument("--topic", action="append", default=[], help="topic candidate (repeatable)")
    ap.add_argument("--max-cost", type=float, default=2.5, help="per-video USD cap passed to the workflow")
    ap.add_argument("--workflow-id", help="follow an existing workflow instead of starting one")
    ap.add_argument("--watch", action="store_true", help="follow the run until it closes")
    ap.add_argument("--poll", type=float, default=5.0, help="seconds between history polls")
    ap.add_argument("--temporal-host", default=os.getenv("TEMPORAL_HOST", "temporal:7233"))
    ap.add_argument("--namespace", default=os.getenv("TEMPORAL_NAMESPACE", "default"))
    args = ap.parse_args()

    if not args.workflow_id and not args.channel:
        ap.error("--channel (to start) or --workflow-id (to follow) is required")

    client = await Client.connect(args.temporal_host, namespace=args.namespace)
    try:
        wf_id = args.workflow_id or await _start(client, args.channel, args.mode, args.topic, args.max_cost)
        if not args.watch:
            print(f"follow with: --watch --workflow-id {wf_id}")
            return 0
        handle = client.get_workflow_handle(wf_id)
        rc = await _watch(handle, args.poll)
        if rc != 0:
            await _show_last_failure_input(handle)
        return rc
    finally:
        await close_pool()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
