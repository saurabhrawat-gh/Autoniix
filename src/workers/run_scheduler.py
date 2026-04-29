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
from src.temporal_workflows.daily_scheduler import DailySchedulerWorkflow
from src.temporal_workflows.model_maintenance import ModelMaintenanceWorkflow
from src.temporal_workflows.model_activities import (
    check_model_freshness,
    check_model_drift,
    retrain_model,
    update_model_health_activity,
)
from src.workers.activities.common import (
    acquire_channel_lock,
    check_system_status,
    get_eligible_channels,
    send_notification,
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
        workflows=[DailySchedulerWorkflow, ModelMaintenanceWorkflow],
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
        ],
        max_concurrent_activities=3,
    )

    logger.info("worker.scheduler.listening", task_queue="scheduler")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
