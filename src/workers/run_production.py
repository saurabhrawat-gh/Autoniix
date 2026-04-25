"""Temporal Worker: video-production task queue.

Registers the VideoProductionWorkflow and ALL pipeline activities.
Start with:  python -m src.workers.run_production
"""
from __future__ import annotations

import asyncio

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from src.config import settings
from src.temporal_workflows.video_production import VideoProductionWorkflow
from src.workers.activities.common import (
    acquire_channel_lock,
    check_system_status,
    get_eligible_channels,
    release_channel_lock,
    send_notification,
    update_video_status,
)
from src.workers.activities.research import research_activity
from src.workers.activities.script import script_activity, title_activity
from src.workers.activities.voice import voice_activity
from src.workers.activities.assets import assets_activity
from src.workers.activities.thumbnail import thumbnail_activity
from src.workers.activities.assembly import assembly_activity
from src.workers.activities.render import render_activity
from src.workers.activities.delivery import delivery_activity
from src.workers.activities.analytics import analytics_activity

logger = structlog.get_logger()


async def main() -> None:
    logger.info(
        "worker.production.starting",
        temporal_host=settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    worker = Worker(
        client,
        task_queue="video-production",
        workflows=[VideoProductionWorkflow],
        activities=[
            # Pipeline activities (in order)
            research_activity,
            script_activity,
            title_activity,
            voice_activity,
            assets_activity,
            thumbnail_activity,
            assembly_activity,
            render_activity,
            delivery_activity,
            analytics_activity,
            # Infrastructure activities
            update_video_status,
            release_channel_lock,
            check_system_status,
            get_eligible_channels,
            acquire_channel_lock,
            send_notification,
        ],
        max_concurrent_activities=5,
        max_concurrent_workflow_tasks=10,
    )

    logger.info("worker.production.listening", task_queue="video-production")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
