# Temporal Workflow Definitions

> All orchestration logic lives in Temporal workflows. Services are stateless; Temporal handles state, retries, checkpoints, and versioning.

---

## Workflow Overview

| Workflow | Task Queue | Schedule | Purpose |
|----------|-----------|----------|---------|
| `DailySchedulerWorkflow` | `scheduler` | Every 6 hours | Check channels, trigger production |
| `VideoProductionWorkflow` | `video-production` | On-demand (child) | Full video pipeline |
| `AnalyticsWorkflow` | `analytics` | Weekly | Collect YouTube analytics |
| `TrendScanWorkflow` | `analytics` | Every 8 hours | Scan trends across niches |

---

## Workflow 1: DailySchedulerWorkflow

Runs every 6 hours. Checks system health, budget, and channel schedules. Starts child workflows for eligible channels.

```python
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

from activities.scheduler import (
    check_system_status,
    get_eligible_channels,
    acquire_channel_lock,
)
from workflows.video_production import VideoProductionWorkflow
from models.schemas import SystemStatus, ChannelEligibility, VideoParams


@workflow.defn
class DailySchedulerWorkflow:

    @workflow.run
    async def run(self) -> dict:
        # Step 1: System health check
        status: SystemStatus = await workflow.execute_activity(
            check_system_status,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        if not status.is_active:
            workflow.logger.info(
                f"System not active: status={status.system_status}, "
                f"emergency={status.emergency_stop}"
            )
            return {"triggered": 0, "reason": "system_inactive"}

        if status.budget_remaining <= 0:
            workflow.logger.warning(
                f"Budget exhausted: ${status.daily_budget_used}/${status.daily_budget_limit}"
            )
            return {"triggered": 0, "reason": "budget_exhausted"}

        # Step 2: Get eligible channels
        channels: list[ChannelEligibility] = await workflow.execute_activity(
            get_eligible_channels,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        triggered = 0
        for channel in channels:
            # Step 3: Acquire execution lock (prevent double-runs)
            locked = await workflow.execute_activity(
                acquire_channel_lock,
                args=[channel.channel_id],
                start_to_close_timeout=timedelta(seconds=10),
            )
            if not locked:
                workflow.logger.info(f"Channel {channel.channel_id} already locked, skipping")
                continue

            # Step 4: Start child workflow (runs independently)
            await workflow.start_child_workflow(
                VideoProductionWorkflow.run,
                args=[VideoParams(
                    channel_id=channel.channel_id,
                    content_mode=channel.content_mode,
                    topic_candidates=channel.topic_candidates,
                    max_cost_usd=min(status.budget_remaining / len(channels), 5.0),
                )],
                id=f"video-{channel.channel_id}-{workflow.now().strftime('%Y%m%d-%H%M')}",
                task_queue="video-production",
            )
            triggered += 1

        return {"triggered": triggered, "total_eligible": len(channels)}
```

### Temporal Schedule (cron)

```python
# Register schedule via Temporal client (run once at setup)
from temporalio.client import Client, Schedule, ScheduleSpec, ScheduleIntervalSpec

async def setup_schedules(client: Client):
    await client.create_schedule(
        "daily-scheduler",
        Schedule(
            action=ScheduleActionStartWorkflow(
                DailySchedulerWorkflow.run,
                id="scheduler-run",
                task_queue="scheduler",
            ),
            spec=ScheduleSpec(
                intervals=[ScheduleIntervalSpec(every=timedelta(hours=6))],
            ),
        ),
    )
```

---

## Workflow 2: VideoProductionWorkflow

The main pipeline. Produces one video from research to delivery.

```python
import asyncio
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

from activities.research import research_activity
from activities.script import script_activity
from activities.voice import voice_activity
from activities.assets import assets_activity
from activities.thumbnail import thumbnail_activity
from activities.assembly import assembly_activity
from activities.render import render_activity
from activities.delivery import delivery_activity
from activities.common import (
    update_video_status,
    send_notification,
    log_cost,
    release_channel_lock,
)
from models.schemas import VideoParams, VideoResult


RETRY_STANDARD = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    non_retryable_error_types=["BudgetExceededError", "ValidationError"],
)

RETRY_CREATIVE = RetryPolicy(
    maximum_attempts=2,
    initial_interval=timedelta(seconds=15),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    non_retryable_error_types=["BudgetExceededError", "ValidationError"],
)


@workflow.defn
class VideoProductionWorkflow:

    def __init__(self):
        self._human_approved: bool | None = None
        self._accrued_cost: float = 0.0

    # ── Signals ──────────────────────────────────────────────

    @workflow.signal
    async def approve_video(self, approved: bool):
        """Human review signal: approve or reject."""
        self._human_approved = approved

    @workflow.signal
    async def emergency_stop(self):
        """Immediate halt signal."""
        self._human_approved = False

    # ── Queries ──────────────────────────────────────────────

    @workflow.query
    def get_status(self) -> dict:
        return {
            "accrued_cost": self._accrued_cost,
            "human_approved": self._human_approved,
        }

    # ── Main workflow ────────────────────────────────────────

    @workflow.run
    async def run(self, params: VideoParams) -> VideoResult:
        content_id = f"VID_{params.channel_id}_{workflow.now().strftime('%Y%m%d')}_{workflow.now().strftime('%H%M')}"
        budget_guard = {"max_cost_usd": params.max_cost_usd, "accrued_cost_usd": 0}

        try:
            # ── PHASE 1: Research ────────────────────────────
            await self._update_status(content_id, "researching")

            research = await workflow.execute_activity(
                research_activity,
                args=[params.channel_id, params.content_mode, params.topic_candidates, budget_guard],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RETRY_STANDARD,
            )
            self._accrued_cost += research["cost"]["cost_usd"]
            budget_guard["accrued_cost_usd"] = self._accrued_cost

            workflow.logger.info(f"Research complete: {research['data']['selected_topic']}")

            # ── PHASE 2: Script ──────────────────────────────
            await self._update_status(content_id, "scripting")

            script = await workflow.execute_activity(
                script_activity,
                args=[research["data"], params.channel_id, budget_guard],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RETRY_CREATIVE,
            )
            self._accrued_cost += script["cost"]["cost_usd"]
            budget_guard["accrued_cost_usd"] = self._accrued_cost

            workflow.logger.info(f"Script complete, score: {script['data']['scores']['overall']}")

            # ── PHASE 3: Parallel asset generation ───────────
            await self._update_status(content_id, "generating_assets")

            voice_task = workflow.execute_activity(
                voice_activity,
                args=[script["data"]["script_base"], params.channel_id, budget_guard],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RETRY_STANDARD,
            )
            assets_task = workflow.execute_activity(
                assets_activity,
                args=[script["data"]["script_base"], budget_guard],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RETRY_STANDARD,
            )
            thumbnail_task = workflow.execute_activity(
                thumbnail_activity,
                args=[script["data"], params.channel_id, budget_guard],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RETRY_STANDARD,
            )

            # Run all three in parallel
            voice, assets, thumbnail = await asyncio.gather(
                voice_task, assets_task, thumbnail_task
            )

            self._accrued_cost += voice["cost"]["cost_usd"]
            self._accrued_cost += assets["cost"]["cost_usd"]
            self._accrued_cost += thumbnail["cost"]["cost_usd"]
            budget_guard["accrued_cost_usd"] = self._accrued_cost

            workflow.logger.info("All assets generated in parallel")

            # ── PHASE 4: Assembly + QA ───────────────────────
            await self._update_status(content_id, "assembling")

            assembly = await workflow.execute_activity(
                assembly_activity,
                args=[script["data"], voice["data"], assets["data"], thumbnail["data"], params.channel_id, budget_guard],
                start_to_close_timeout=timedelta(minutes=8),
                retry_policy=RETRY_CREATIVE,
            )
            self._accrued_cost += assembly["cost"]["cost_usd"]

            workflow.logger.info(f"Assembly complete, score: {assembly['data']['quality_report']['final_composite_score']}")

            # ── QUALITY GATE ─────────────────────────────────
            final_score = assembly["data"]["quality_report"]["final_composite_score"]

            if final_score < 8.0:
                await self._update_status(content_id, "awaiting_review")

                # Notify human
                await workflow.execute_activity(
                    send_notification,
                    args=[{
                        "type": "human_review_required",
                        "content_id": content_id,
                        "channel_id": params.channel_id,
                        "score": final_score,
                        "report": assembly["data"]["quality_report"],
                    }],
                    start_to_close_timeout=timedelta(seconds=30),
                )

                # Wait for human signal (up to 48 hours)
                try:
                    await workflow.wait_condition(
                        lambda: self._human_approved is not None,
                        timeout=timedelta(hours=48),
                    )
                except asyncio.TimeoutError:
                    await self._update_status(content_id, "rejected")
                    return VideoResult(status="rejected", reason="human_review_timeout", cost=self._accrued_cost)

                if not self._human_approved:
                    await self._update_status(content_id, "rejected")
                    return VideoResult(status="rejected", reason="human_rejected", cost=self._accrued_cost)

            # ── PHASE 5: Render ──────────────────────────────
            await self._update_status(content_id, "rendering")

            render = await workflow.execute_activity(
                render_activity,
                args=[assembly["data"]["v3_json"], params.channel_id],
                start_to_close_timeout=timedelta(minutes=20),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    maximum_attempts=2,
                    initial_interval=timedelta(seconds=30),
                    backoff_coefficient=2.0,
                ),
            )

            workflow.logger.info(f"Render complete: {render['data']['video_url']}")

            # ── PHASE 6: Delivery ────────────────────────────
            await self._update_status(content_id, "delivering")

            delivery = await workflow.execute_activity(
                delivery_activity,
                args=[render["data"], script["data"]["metadata"], assembly["data"]["quality_report"]["compliance"], params.channel_id],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RETRY_STANDARD,
            )

            # ── DONE ─────────────────────────────────────────
            await self._update_status(content_id, "delivered")

            # Log final cost
            await workflow.execute_activity(
                log_cost,
                args=[content_id, self._accrued_cost],
                start_to_close_timeout=timedelta(seconds=10),
            )

            return VideoResult(
                status="delivered",
                content_id=content_id,
                youtube_video_id=delivery["data"].get("youtube_video_id"),
                cost=self._accrued_cost,
            )

        except Exception as e:
            workflow.logger.error(f"Pipeline failed: {e}")
            await self._update_status(content_id, "failed")
            raise

        finally:
            # Always release the channel lock
            await workflow.execute_activity(
                release_channel_lock,
                args=[params.channel_id],
                start_to_close_timeout=timedelta(seconds=10),
            )

    # ── Helpers ───────────────────────────────────────────────

    async def _update_status(self, content_id: str, status: str):
        await workflow.execute_activity(
            update_video_status,
            args=[content_id, status],
            start_to_close_timeout=timedelta(seconds=10),
        )
```

---

## Workflow 3: AnalyticsWorkflow

Runs weekly. Collects YouTube analytics and updates performance memory.

```python
@workflow.defn
class AnalyticsWorkflow:

    @workflow.run
    async def run(self) -> dict:
        # Get all active channels
        channels = await workflow.execute_activity(
            get_active_channels,
            start_to_close_timeout=timedelta(seconds=30),
        )

        results = []
        for channel in channels:
            analytics = await workflow.execute_activity(
                collect_analytics,
                args=[channel.channel_id, 30],  # 30-day lookback
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            # Update performance memory
            await workflow.execute_activity(
                update_performance_memory,
                args=[channel.channel_id, analytics],
                start_to_close_timeout=timedelta(seconds=30),
            )

            results.append({
                "channel_id": channel.channel_id,
                "views": analytics.get("total_views"),
                "patterns": len(analytics.get("patterns", [])),
            })

        # Send weekly report
        await workflow.execute_activity(
            send_notification,
            args=[{"type": "weekly_analytics", "data": results}],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {"channels_processed": len(results)}
```

---

## Workflow 4: TrendScanWorkflow

Runs every 8 hours. Scans trending topics across niches and caches results.

```python
@workflow.defn
class TrendScanWorkflow:

    @workflow.run
    async def run(self) -> dict:
        niches = await workflow.execute_activity(
            get_active_niches,
            start_to_close_timeout=timedelta(seconds=30),
        )

        trends = await workflow.execute_activity(
            scan_trends,
            args=[niches],
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        await workflow.execute_activity(
            cache_trends,
            args=[trends],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {"niches_scanned": len(niches), "trends_found": len(trends)}
```

---

## Human-in-the-Loop Pattern

### How it works

1. Assembly produces a quality score
2. If score < 8.0, workflow enters **waiting state**
3. A notification is sent (webhook, email, Slack) with:
   - Video preview artifacts (script, thumbnails, scores)
   - Approve/Reject buttons (hit a Temporal signal endpoint)
4. Workflow suspends (uses zero CPU while waiting)
5. Human clicks Approve → `approve_video(True)` signal → workflow resumes
6. Human clicks Reject → `approve_video(False)` signal → workflow terminates
7. If no response in 48h → auto-reject

### Sending a signal (from Admin API or webhook)

```python
# Admin API endpoint
@router.post("/videos/{workflow_id}/approve")
async def approve_video(workflow_id: str, body: ApproveRequest):
    handle = temporal_client.get_workflow_handle(workflow_id)
    await handle.signal(VideoProductionWorkflow.approve_video, body.approved)
    return {"status": "signal_sent"}
```

### Review scaling

| Phase | Review Rule |
|-------|------------|
| First 10 videos | ALL videos require human approval (score override) |
| Videos 11-50 | Only if score < 8.0 |
| Videos 51-200 | Only if score < 7.5 |
| After 200 videos | Only if score < 7.0 or flagged anomaly |
| 100+ channels | 10% random audit + anomaly detection |

The threshold is stored in `system_config` table and adjustable via Admin API.

---

## Budget Guard Pattern

### Pre-flight (in DailySchedulerWorkflow)

```python
# Before starting a child workflow
estimated_cost = estimate_video_cost(channel.content_mode)  # ~$0.76 long, ~$0.20 short
if estimated_cost > status.budget_remaining:
    workflow.logger.warning(f"Budget insufficient for {channel.channel_id}")
    continue
```

### In-flight (in VideoProductionWorkflow)

Every activity receives `budget_guard`:
```python
budget_guard = {
    "max_cost_usd": params.max_cost_usd,
    "accrued_cost_usd": self._accrued_cost,
}
```

Each service checks before processing:
```python
# Inside every service
estimated = estimate_activity_cost(payload)
if budget_guard["accrued_cost_usd"] + estimated > budget_guard["max_cost_usd"]:
    raise BudgetExceededError(
        f"Would exceed budget: accrued=${budget_guard['accrued_cost_usd']:.4f} "
        f"+ estimated=${estimated:.4f} > max=${budget_guard['max_cost_usd']:.2f}"
    )
```

### Daily cap (in system_config)

```sql
-- Checked by DailySchedulerWorkflow
SELECT config_value FROM system_config WHERE config_key = 'daily_budget_limit';
SELECT COALESCE(SUM(total_cost), 0) FROM videos
WHERE created_at >= CURRENT_DATE AND status != 'failed';
```

---

## Error Handling Strategy

### Retry with backoff

All activities use `RetryPolicy` with exponential backoff. Non-retryable errors (budget exceeded, validation) fail immediately.

### Circuit breaker (per provider)

Implemented in service layer, checked before each API call:

```python
async def check_circuit(provider: str, redis: Redis) -> bool:
    failures = await redis.get(f"circuit:{provider}:failures")
    state = await redis.get(f"circuit:{provider}:state")
    
    if state == b"open":
        last_fail = await redis.get(f"circuit:{provider}:last_failure")
        if time.time() - float(last_fail) > 600:  # 10 min cooldown
            await redis.set(f"circuit:{provider}:state", "half_open")
            return True  # Allow one test request
        return False  # Circuit still open
    
    return True  # Circuit closed, proceed

async def record_failure(provider: str, redis: Redis):
    failures = await redis.incr(f"circuit:{provider}:failures")
    await redis.expire(f"circuit:{provider}:failures", 600)
    await redis.set(f"circuit:{provider}:last_failure", str(time.time()))
    
    if failures >= 5:
        await redis.set(f"circuit:{provider}:state", "open", ex=600)

async def record_success(provider: str, redis: Redis):
    await redis.delete(f"circuit:{provider}:failures")
    await redis.set(f"circuit:{provider}:state", "closed")
```

### Dead letter handling

Failed workflows are visible in the Temporal UI. For systematic failures:
1. Temporal retries activities per policy
2. If all retries exhausted, workflow fails
3. Failed workflow is queryable and can be:
   - **Reset** to a specific point (re-run from last good checkpoint)
   - **Terminated** (if unrecoverable)
   - **Replayed** (Temporal replays history for debugging)

---

## Workflow Versioning Strategy

When updating workflow logic (e.g., adding a new quality gate):

```python
@workflow.defn
class VideoProductionWorkflow:

    @workflow.run
    async def run(self, params: VideoParams) -> VideoResult:
        # ... earlier steps ...

        # Version gate: new behavior for new workflows only
        if workflow.patched("add-compliance-gate-v2"):
            # New: run enhanced compliance check
            compliance = await workflow.execute_activity(
                enhanced_compliance_check,
                args=[assembly["data"]],
                start_to_close_timeout=timedelta(minutes=2),
            )
        else:
            # Old: original compliance (for in-flight workflows)
            compliance = assembly["data"]["quality_report"]["compliance"]
```

This ensures in-flight workflows continue with old logic while new workflows use updated logic. Temporal handles the branching deterministically.

---

## Task Queue Configuration

```python
# Worker startup
from temporalio.worker import Worker

async def start_workers(client):
    # Production worker (main pipeline)
    production_worker = Worker(
        client,
        task_queue="video-production",
        workflows=[VideoProductionWorkflow],
        activities=[
            research_activity, script_activity, voice_activity,
            assets_activity, thumbnail_activity, assembly_activity,
            render_activity, delivery_activity,
            update_video_status, send_notification, log_cost,
            release_channel_lock,
        ],
        max_concurrent_activities=5,
        max_concurrent_workflow_tasks=10,
    )

    # Scheduler worker
    scheduler_worker = Worker(
        client,
        task_queue="scheduler",
        workflows=[DailySchedulerWorkflow],
        activities=[
            check_system_status, get_eligible_channels,
            acquire_channel_lock,
        ],
        max_concurrent_activities=3,
    )

    # Analytics worker
    analytics_worker = Worker(
        client,
        task_queue="analytics",
        workflows=[AnalyticsWorkflow, TrendScanWorkflow],
        activities=[
            get_active_channels, collect_analytics,
            update_performance_memory, get_active_niches,
            scan_trends, cache_trends, send_notification,
        ],
        max_concurrent_activities=3,
    )

    # Run all workers concurrently
    await asyncio.gather(
        production_worker.run(),
        scheduler_worker.run(),
        analytics_worker.run(),
    )
```
