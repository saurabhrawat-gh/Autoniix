"""Temporal Worker v2: video-production-v2 task queue.

Registers the ported Python ``VideoProductionWorkflow`` PLUS all activities.
This is the Phase 4 migration target — the Go worker on ``video-production``
remains running until all in-flight workflows drain.

Start with::

    python -m temporal_workers.run_production_v2
"""

from __future__ import annotations

import asyncio

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from core.config import settings
from observability.sentry import init_sentry

init_sentry("worker-production-v2")

# Activities (same set as run_production.py)
from src.temporal_workflows.brain_activities import brain_directive_check_activity

from services_api.finishing.activity import finishing_activity
from temporal_workers.activities.analytics import analytics_activity
from temporal_workers.activities.assembly import assembly_activity
from temporal_workers.activities.assets import assets_activity
from temporal_workers.activities.brand import brand_activity
from temporal_workers.activities.common import (
    acquire_channel_lock,
    acquire_channel_lock_v2,
    check_system_status,
    emit_job_event,
    get_eligible_channels,
    load_checkpoint_data,
    refresh_channel_lock,
    release_channel_lock,
    save_checkpoint_data,
    send_notification,
    update_video_status,
)
from temporal_workers.activities.delivery import compute_metadata_activity, delivery_activity
from temporal_workers.activities.direction import direction_activity
from temporal_workers.activities.editor import editor_activity
from temporal_workers.activities.music import music_activity
from temporal_workers.activities.render import render_activity
from temporal_workers.activities.research import research_activity
from temporal_workers.activities.script import script_activity, title_activity
from temporal_workers.activities.thumbnail import thumbnail_activity
from temporal_workers.activities.voice import voice_activity

# Python-ported workflow (Phase 4)
from temporal_workers.workflows import VideoProductionWorkflow

logger = structlog.get_logger()

TASK_QUEUE = "video-production"


def _compute_worker_sizing() -> tuple[int, int]:
    """Cap activity concurrency to <= 80% of DB pool so an activity storm
    can never exhaust the pool and starve unrelated queries.

    Returns ``(max_activities, max_workflow_tasks)``.
    """
    configured_acts = int(settings.temporal_production_max_activities)
    db_max = int(settings.db_pool_max_size)
    safe_cap = max(1, int(db_max * 0.8))
    max_acts = min(configured_acts, safe_cap)
    max_wf = int(settings.temporal_production_max_workflow_tasks)
    if max_acts != configured_acts:
        logger.warning(
            "worker.production_v2.activity_concurrency_capped",
            configured=configured_acts,
            db_pool_max=db_max,
            safe_cap=safe_cap,
            applied=max_acts,
        )
    return max_acts, max_wf


async def main() -> None:
    max_acts, max_wf = _compute_worker_sizing()
    logger.info(
        "worker.production_v2.starting",
        temporal_host=settings.temporal_host,
        namespace=settings.temporal_namespace,
        task_queue=TASK_QUEUE,
        max_activities=max_acts,
        max_workflow_tasks=max_wf,
        db_pool_max=settings.db_pool_max_size,
    )

    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[VideoProductionWorkflow],
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
            refresh_channel_lock,
            check_system_status,
            get_eligible_channels,
            acquire_channel_lock,
            acquire_channel_lock_v2,
            send_notification,
            save_checkpoint_data,
            load_checkpoint_data,
        ],
        max_concurrent_activities=max_acts,
        max_concurrent_workflow_tasks=max_wf,
    )

    logger.info(
        "worker.production_v2.listening",
        task_queue=TASK_QUEUE,
        max_activities=max_acts,
        max_workflow_tasks=max_wf,
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
