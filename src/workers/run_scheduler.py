"""Temporal Worker: scheduler task queue.

Registers the DailySchedulerWorkflow.
Start with:  python -m src.workers.run_scheduler
"""
from __future__ import annotations

import asyncio

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from src.config import settings
from src.observability.sentry import init_sentry
init_sentry("worker-scheduler")
from src.temporal_workflows.daily_scheduler import DailySchedulerWorkflow
from src.temporal_workflows.model_maintenance import ModelMaintenanceWorkflow
from src.temporal_workflows.model_activities import (
    check_model_freshness,
    check_model_drift,
    retrain_model,
    update_model_health_activity,
)
from src.temporal_workflows.gate_calibration import GateCalibrationWorkflow
from src.temporal_workflows.gate_activities import (
    list_niches_with_outcomes_activity,
    calibrate_gate_for_niche_activity,
)
from src.temporal_workflows.niche_pulse import NichePulseRefreshWorkflow
from src.temporal_workflows.niche_pulse_activities import (
    refresh_niche_pulse_activity,
)
from src.temporal_workflows.retention_fetch import RetentionFetchWorkflow
from src.temporal_workflows.retention_activities import (
    list_videos_needing_retention_activity,
    fetch_retention_for_video_activity,
)
from src.workers.provider_health_beat import (
    HealthBeatWorkflow,
    check_all_provider_health,
)
from src.workers.activities.common import (
    acquire_channel_lock,
    check_system_status,
    get_eligible_channels,
    send_notification,
)
from src.workers.change_request_beat import (
    ChangeRequestExpiryWorkflow,
    expire_stale_change_requests,
)

logger = structlog.get_logger()


async def main() -> None:
    logger.info(
        "worker.scheduler.starting",
        temporal_host=settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    worker = Worker(
        client,
        task_queue="scheduler",
        workflows=[
            DailySchedulerWorkflow,
            ModelMaintenanceWorkflow,
            GateCalibrationWorkflow,
            NichePulseRefreshWorkflow,
            RetentionFetchWorkflow,
            HealthBeatWorkflow,
            ChangeRequestExpiryWorkflow,
        ],
        activities=[
            check_system_status,
            get_eligible_channels,
            acquire_channel_lock,
            send_notification,
            # Model maintenance activities
            check_model_freshness,
            check_model_drift,
            retrain_model,
            update_model_health_activity,
            # Phase 7 — gate calibration activities
            list_niches_with_outcomes_activity,
            calibrate_gate_for_niche_activity,
            # Phase 8 — niche pulse activities (re-uses
            # list_niches_with_outcomes_activity from Phase 7)
            refresh_niche_pulse_activity,
            # Phase 9 — retention-curve fetch activities
            list_videos_needing_retention_activity,
            fetch_retention_for_video_activity,
            # AE-75 — provider health beat
            check_all_provider_health,
            # AE-76 — change request expiry
            expire_stale_change_requests,
        ],
        max_concurrent_activities=settings.temporal_scheduler_max_activities,
    )

    logger.info("worker.scheduler.listening", task_queue="scheduler",
                max_activities=settings.temporal_scheduler_max_activities)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
