"""DailySchedulerWorkflow — fans out one VideoProductionWorkflow per channel.

Ported from ``go-workflows/daily_scheduler.go``. Task queue: ``scheduler-v2``.
Child workflows run on ``video-production-v2``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

from .types import RETRY_STANDARD, VideoParams
from .video_production import VideoProductionWorkflow


@workflow.defn(name="DailySchedulerWorkflow")
class DailySchedulerWorkflow:
    @workflow.run
    async def run(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        log = workflow.logger

        # 1. System status check
        status = await workflow.execute_activity(
            "check_system_status",
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_STANDARD,
        )
        if not status.get("ready"):
            log.info(
                "system not ready — skipping daily run",
                extra={"reason": status.get("reason")},
            )
            return {"status": "skipped", "reason": status.get("reason")}

        # 2. Eligible channels
        channels: list[dict[str, Any]] = await workflow.execute_activity(
            "get_eligible_channels",
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_STANDARD,
        )
        if not channels:
            log.info("no eligible channels — nothing to do")
            return {"status": "ok", "started": 0}

        # 3. Start one child per channel
        started = 0
        ts = workflow.now().strftime("%Y%m%d-%H%M%S")

        for ch in channels:
            channel_id = ch.get("channel_id") or ch.get("id") or ""
            if not channel_id:
                continue

            mode = ch.get("content_mode") or "long_form"
            mode_prefix = "S" if mode in ("short_form", "short") else "L"

            topic_candidates = [t for t in (ch.get("topic_candidates") or []) if isinstance(t, str)]
            max_cost = float(ch.get("max_cost_usd") or 2.50)

            try:
                locked: bool = await workflow.execute_activity(
                    "acquire_channel_lock",
                    channel_id,
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=RETRY_STANDARD,
                )
            except Exception as exc:  # noqa: BLE001
                log.warn(
                    "acquire_channel_lock failed — skipping channel",
                    extra={"channel_id": channel_id, "error": str(exc)},
                )
                continue

            if not locked:
                log.warn(
                    "channel lock unavailable — skipping",
                    extra={"channel_id": channel_id},
                )
                continue

            child_params = VideoParams(
                channel_id=channel_id,
                content_mode=mode,
                topic_candidates=topic_candidates,
                max_cost_usd=max_cost,
                environment="production",
            )

            # Fire-and-forget child workflow — don't block scheduler.
            await workflow.start_child_workflow(
                VideoProductionWorkflow.run,
                child_params,
                id=f"video-{channel_id}-{mode_prefix}-{ts}",
                task_queue="video-production",
            )
            started += 1
            log.info(
                "started child VideoProductionWorkflow",
                extra={"channel_id": channel_id, "mode": mode},
            )

        return {"status": "ok", "started": started}
