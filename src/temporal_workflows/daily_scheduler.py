from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.schemas.common import VideoParams


@workflow.defn
class DailySchedulerWorkflow:

    @workflow.run
    async def run(self) -> dict:
        # Step 1: Check system status
        status = await workflow.execute_activity(
            "check_system_status",
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        if not status.get("is_active", False):
            workflow.logger.info(f"System inactive: {status}")
            return {"triggered": 0, "reason": "system_inactive"}

        budget_remaining = status.get("budget_remaining", 0)
        if budget_remaining <= 0:
            workflow.logger.warning("Budget exhausted")
            return {"triggered": 0, "reason": "budget_exhausted"}

        # Step 2: Get eligible channels
        channels = await workflow.execute_activity(
            "get_eligible_channels",
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        triggered = 0
        for ch in channels:
            # Step 3: Acquire lock
            locked = await workflow.execute_activity(
                "acquire_channel_lock",
                args=[ch["channel_id"]],
                start_to_close_timeout=timedelta(seconds=10),
            )
            if not locked:
                workflow.logger.info(f"Channel {ch['channel_id']} already locked")
                continue

            # Step 4: Start child workflow
            per_video_budget = min(budget_remaining / max(len(channels), 1), 5.0)

            await workflow.start_child_workflow(
                "VideoProductionWorkflow",
                args=[VideoParams(
                    channel_id=ch["channel_id"],
                    content_mode=ch.get("content_mode", "long_form"),
                    topic_candidates=ch.get("topic_candidates", []),
                    max_cost_usd=per_video_budget,
                )],
                id=f"video-{ch['channel_id']}-{workflow.now().strftime('%Y%m%d-%H%M')}",
                task_queue="video-production",
            )
            triggered += 1

        return {"triggered": triggered, "total_eligible": len(channels)}
