"""Temporal Worker v2: scheduler-v2 task queue.

Registers ALL periodic + fanout workflows (previously Go-orchestrated).
The Go worker on ``scheduler`` remains running until callers/schedules are
switched to ``scheduler-v2``.

Start with::

    python -m temporal_workers.run_scheduler_v2
"""

from __future__ import annotations

import asyncio

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from core.config import settings
from observability.sentry import init_sentry

init_sentry("worker-scheduler-v2")

# Activities (same set as run_scheduler.py)
from src.temporal_workflows.gate_activities import (
    calibrate_gate_for_niche_activity,
    list_niches_with_outcomes_activity,
)
from src.temporal_workflows.model_activities import (
    check_model_drift,
    check_model_freshness,
    retrain_model,
    update_model_health_activity,
)
from src.temporal_workflows.niche_pulse_activities import (
    refresh_niche_pulse_activity,
)
from src.temporal_workflows.retention_activities import (
    fetch_retention_for_video_activity,
    list_videos_needing_retention_activity,
)

from temporal_workers.activities.common import (
    acquire_channel_lock,
    check_system_status,
    get_eligible_channels,
    release_channel_lock,
    send_notification,
)
from temporal_workers.change_request_beat import expire_stale_change_requests
from temporal_workers.provider_health_beat import check_all_provider_health

# Python-ported workflows (Phase 4)
from temporal_workers.workflows import (
    ChangeRequestExpiryWorkflow,
    DailySchedulerWorkflow,
    GateCalibrationWorkflow,
    HealthBeatWorkflow,
    ModelMaintenanceWorkflow,
    NichePulseRefreshWorkflow,
    RetentionFetchWorkflow,
)

logger = structlog.get_logger()

TASK_QUEUE = "scheduler"


async def main() -> None:
    logger.info(
        "worker.scheduler_v2.starting",
        temporal_host=settings.temporal_host,
        namespace=settings.temporal_namespace,
        task_queue=TASK_QUEUE,
    )

    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            HealthBeatWorkflow,
            ChangeRequestExpiryWorkflow,
            GateCalibrationWorkflow,
            NichePulseRefreshWorkflow,
            RetentionFetchWorkflow,
            ModelMaintenanceWorkflow,
            DailySchedulerWorkflow,
        ],
        activities=[
            check_system_status,
            get_eligible_channels,
            acquire_channel_lock,
            release_channel_lock,
            send_notification,
            check_model_freshness,
            check_model_drift,
            retrain_model,
            update_model_health_activity,
            list_niches_with_outcomes_activity,
            calibrate_gate_for_niche_activity,
            refresh_niche_pulse_activity,
            list_videos_needing_retention_activity,
            fetch_retention_for_video_activity,
            check_all_provider_health,
            expire_stale_change_requests,
        ],
        max_concurrent_activities=settings.temporal_scheduler_max_activities,
    )

    logger.info(
        "worker.scheduler_v2.listening",
        task_queue=TASK_QUEUE,
        max_activities=settings.temporal_scheduler_max_activities,
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
