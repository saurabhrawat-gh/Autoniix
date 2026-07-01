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

        channels = await workflow.execute_activity(
            "get_eligible_channels",
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        triggered = 0
        for ch in channels:
            mode = ch.get("content_mode", "long_form")

            locked = await workflow.execute_activity(
                "acquire_channel_lock",
                args=[ch["channel_id"]],
                start_to_close_timeout=timedelta(seconds=10),
            )
            if not locked:
                workflow.logger.info(f"Channel {ch['channel_id']} already locked")
                continue

            per_video_budget = min(
                ch.get("max_daily_api_spend", 5.0),
                budget_remaining / max(len(channels) - triggered, 1),
            )

            await workflow.start_child_workflow(
                "VideoProductionWorkflow",
                args=[VideoParams(
                    channel_id=ch["channel_id"],
                    content_mode=mode,
                    topic_candidates=ch.get("topic_candidates", []),
                    max_cost_usd=per_video_budget,
                    environment="production",
                )],
                id=f"video-{ch['channel_id']}-{mode[:1]}-{workflow.now().strftime('%Y%m%d-%H%M%S')}",
                task_queue="video-production",
            )
            triggered += 1

        return {"triggered": triggered, "total_eligible": len(channels)}
