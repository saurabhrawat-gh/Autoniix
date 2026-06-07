"""resolve-finisher — Phase 1B DaVinci Resolve headless finishing service (AE-295).

Contract (called by src/services/finishing/activity.py when require_resolve_finish=True):

    POST /jobs
        Request:  FinishJob
        Response: {"job_id": "<uuid>"}

    GET  /jobs/{job_id}
        Response: FinishJobStatus

    GET  /health
        Response: {"status": "ok"}

    GET  /metrics
        Prometheus text exposition (port 8014 same host, scraped by prometheus)

Phase 1B is a stub — it accepts jobs and returns them as "completed" immediately.
Swap the _run_job body for real Resolve CLI invocation when hardware is available.
"""
from __future__ import annotations

import asyncio
import uuid
from enum import Enum
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from starlette.responses import Response

logger = structlog.get_logger()

app = FastAPI(title="resolve-finisher", version="0.1.0")

# ---------------------------------------------------------------------------
# In-memory job store (replaced by Redis / DB in a future phase)
# ---------------------------------------------------------------------------
_jobs: dict[str, dict[str, Any]] = {}
_queue: asyncio.Queue[str] = asyncio.Queue()

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
JOBS_SUBMITTED = Counter("resolve_finisher_jobs_submitted_total", "Total jobs submitted")
JOBS_COMPLETED = Counter("resolve_finisher_jobs_completed_total", "Total jobs completed")
JOBS_FAILED = Counter("resolve_finisher_jobs_failed_total", "Total jobs failed")
QUEUE_DEPTH = Gauge("resolve_finisher_queue_depth", "Current queue depth")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class FinishJob(BaseModel):
    channel_id: str
    project_id: str
    input_path: str = Field(..., description="S3 / local path of the rendered video")
    output_path: str = Field(..., description="S3 / local path for the finished output")
    color_grade_preset: str = "none"
    audio_loudness_lufs: float = -14.0
    audio_true_peak_dbtps: float = -1.0
    audio_denoise: bool = False
    audio_eq: bool = False
    audio_compress: bool = False
    audio_music_duck: bool = False


class FinishJobStatus(BaseModel):
    job_id: str
    status: JobStatus
    error: str | None = None


# ---------------------------------------------------------------------------
# Background worker (stub — replace with Resolve CLI call)
# ---------------------------------------------------------------------------
async def _worker() -> None:
    while True:
        job_id = await _queue.get()
        QUEUE_DEPTH.dec()
        job = _jobs.get(job_id)
        if job is None:
            _queue.task_done()
            continue

        job["status"] = JobStatus.running
        logger.info("resolve_finisher.job_started", job_id=job_id)

        try:
            # Phase 1B stub: simulate work then mark completed.
            # Replace this block with actual DaVinci Resolve headless CLI call.
            await asyncio.sleep(0)
            job["status"] = JobStatus.completed
            JOBS_COMPLETED.inc()
            logger.info("resolve_finisher.job_completed", job_id=job_id)
        except Exception as exc:  # noqa: BLE001
            job["status"] = JobStatus.failed
            job["error"] = str(exc)
            JOBS_FAILED.inc()
            logger.error("resolve_finisher.job_failed", job_id=job_id, error=str(exc))
        finally:
            _queue.task_done()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(_worker())
    logger.info("resolve_finisher.started")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/jobs", status_code=202)
async def submit_job(body: FinishJob) -> dict[str, str]:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "status": JobStatus.pending,
        "error": None,
        **body.model_dump(),
    }
    await _queue.put(job_id)
    QUEUE_DEPTH.inc()
    JOBS_SUBMITTED.inc()
    logger.info("resolve_finisher.job_queued", job_id=job_id, channel_id=body.channel_id)
    return {"job_id": job_id}


@app.get("/jobs/{job_id}", response_model=FinishJobStatus)
async def get_job(job_id: str) -> FinishJobStatus:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return FinishJobStatus(
        job_id=job_id,
        status=job["status"],
        error=job.get("error"),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
