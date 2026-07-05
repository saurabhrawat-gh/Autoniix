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
from src.observability.sentry import init_sentry
init_sentry("worker-production")
# VideoProductionWorkflow orchestration has been migrated to the Go worker.
# This Python worker handles ACTIVITIES ONLY.
from src.workers.activities.common import (
    acquire_channel_lock,
    check_system_status,
    emit_job_event,
    get_eligible_channels,
    load_checkpoint_data,
    release_channel_lock,
    save_checkpoint_data,
    send_notification,
    update_video_status,
)
from src.workers.activities.research import research_activity
from src.workers.activities.script import script_activity, title_activity
from src.workers.activities.voice import voice_activity
from src.workers.activities.assets import assets_activity
from src.workers.activities.thumbnail import thumbnail_activity
from src.workers.activities.direction import direction_activity
from src.workers.activities.music import music_activity
from src.workers.activities.assembly import assembly_activity
from src.services.finishing.activity import finishing_activity
from src.workers.activities.render import render_activity
from src.workers.activities.delivery import delivery_activity, compute_metadata_activity
from src.workers.activities.analytics import analytics_activity
from src.workers.activities.brand import brand_activity
from src.workers.activities.editor import editor_activity
from src.temporal_workflows.brain_activities import brain_directive_check_activity

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
        workflows=[],  # Go worker handles workflow orchestration on this queue.
        activities=[
            research_activity,
            script_activity,
            title_activity,
            voice_activity,
            assets_activity,
            thumbnail_activity,
            direction_activity,
            music_activity,
            assembly_activity,
            finishing_activity,
            render_activity,
            delivery_activity,
            compute_metadata_activity,
            analytics_activity,
            brand_activity,
            editor_activity,
            brain_directive_check_activity,
            update_video_status,
            emit_job_event,
            release_channel_lock,
            check_system_status,
            get_eligible_channels,
            acquire_channel_lock,
            send_notification,
            save_checkpoint_data,
            load_checkpoint_data,
        ],
        max_concurrent_activities=settings.temporal_production_max_activities,
        max_concurrent_workflow_tasks=settings.temporal_production_max_workflow_tasks,
    )

    logger.info("worker.production.listening", task_queue="video-production",
                max_activities=settings.temporal_production_max_activities,
                max_workflow_tasks=settings.temporal_production_max_workflow_tasks)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
