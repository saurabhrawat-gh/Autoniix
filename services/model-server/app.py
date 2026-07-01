"""
Phase 2C — Model server skeleton.

This is the runnable protocol contract. The four model implementations
(RIFE, SCUNet, Real-ESRGAN, DDColor) are wired in stub form below; replacing
each `_run_*` function with the real model invocation is the GPU-host
follow-up (see services/model-server/README.md).

Run (CPU, stub-only — useful to test the wiring):
    cd services/model-server && pip install -r requirements.txt && \
        uvicorn app:app --host 0.0.0.0 --port 8400

The server keys a content-addressed cache by sha256(input, kind, params,
model_version). Cache hits return status="done" synchronously from the
submit endpoint, so the TS client gets identical behaviour for repeated
requests.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

ModelKind = Literal["rife", "scunet", "real-esrgan", "ddcolor"]

MODEL_VERSIONS: Dict[ModelKind, str] = {
    "rife": "rife-v4.13",
    "scunet": "scunet-color-real_psnr",
    "real-esrgan": "realesrgan-x4plus-v0.2.5",
    "ddcolor": "ddcolor-modelscope-v1",
}

OUTPUT_BUCKET_URL = os.environ.get("MODEL_OUTPUT_BUCKET_URL", "http://minio:9000/derived")




class JobRequest(BaseModel):
    kind: ModelKind
    inputUrl: str
    inputSha256: str = Field(min_length=64, max_length=64)
    params: Dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    jobId: str
    status: Literal["queued", "running", "done", "failed"]
    outputUrl: Optional[str] = None
    outputSha256: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[float] = None




@dataclass
class _Job:
    job_id: str
    kind: ModelKind
    cache_key: str
    request: JobRequest
    status: str = "queued"
    output_url: Optional[str] = None
    output_sha256: Optional[str] = None
    error: Optional[str] = None
    progress: float = 0.0
    started_at: float = field(default_factory=time.time)


_jobs: Dict[str, _Job] = {}
_cache: Dict[str, _Job] = {}


def _compute_cache_key(req: JobRequest) -> str:
    body = {
        "kind": req.kind,
        "inputSha256": req.inputSha256,
        "params": req.params,
        "modelVersion": MODEL_VERSIONS[req.kind],
    }
    blob = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()




async def _run_stub(kind: ModelKind, req: JobRequest) -> tuple[str, str]:
    """
    Pretend to run the model. Returns (outputUrl, outputSha256).

    A real implementation would:
      1. Download `req.inputUrl` to a local temp path.
      2. Run the model on the GPU, writing an output mp4.
      3. Hash the output, upload it to MinIO at derived/<sha>.mp4.
      4. Return the public URL + sha.
    """
    durations = {"rife": 4.0, "scunet": 2.5, "real-esrgan": 3.5, "ddcolor": 5.0}
    await asyncio.sleep(durations.get(kind, 2.0))
    pseudo_sha = hashlib.sha256(
        f"{kind}:{req.inputSha256}:{json.dumps(req.params, sort_keys=True)}".encode()
    ).hexdigest()
    return f"{OUTPUT_BUCKET_URL}/{pseudo_sha}.mp4", pseudo_sha


async def _process_job(job: _Job) -> None:
    job.status = "running"
    try:
        url, sha = await _run_stub(job.kind, job.request)
        job.output_url = url
        job.output_sha256 = sha
        job.status = "done"
        job.progress = 1.0
        _cache[job.cache_key] = job
    except Exception as e:  # pragma: no cover — defensive
        job.status = "failed"
        job.error = str(e)




app = FastAPI(title="model-server", version="0.1.0")


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    return "ok"


@app.post("/jobs", response_model=JobResponse)
async def submit_job(req: JobRequest) -> JobResponse:
    cache_key = _compute_cache_key(req)
    cached = _cache.get(cache_key)
    if cached:
        return JobResponse(
            jobId=cached.job_id,
            status=cached.status,  # type: ignore[arg-type]
            outputUrl=cached.output_url,
            outputSha256=cached.output_sha256,
        )
    job_id = str(uuid.uuid4())
    job = _Job(job_id=job_id, kind=req.kind, cache_key=cache_key, request=req)
    _jobs[job_id] = job
    asyncio.create_task(_process_job(job))
    return JobResponse(jobId=job_id, status="queued")


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return JobResponse(
        jobId=job.job_id,
        status=job.status,  # type: ignore[arg-type]
        outputUrl=job.output_url,
        outputSha256=job.output_sha256,
        error=job.error,
        progress=job.progress,
    )


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> Dict[str, bool]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status not in ("done", "failed"):
        job.status = "failed"
        job.error = "cancelled"
    return {"ok": True}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    """Prometheus exposition. Stub counters; real impl uses prometheus_client."""
    queued = sum(1 for j in _jobs.values() if j.status == "queued")
    running = sum(1 for j in _jobs.values() if j.status == "running")
    done = sum(1 for j in _jobs.values() if j.status == "done")
    failed = sum(1 for j in _jobs.values() if j.status == "failed")
    cache_hits = len(_cache)
    return (
        f"# HELP model_server_jobs_total Number of jobs by status\n"
        f"# TYPE model_server_jobs_total gauge\n"
        f'model_server_jobs_total{{status="queued"}} {queued}\n'
        f'model_server_jobs_total{{status="running"}} {running}\n'
        f'model_server_jobs_total{{status="done"}} {done}\n'
        f'model_server_jobs_total{{status="failed"}} {failed}\n'
        f"# HELP model_server_cache_size Cached job count\n"
        f"# TYPE model_server_cache_size gauge\n"
        f"model_server_cache_size {cache_hits}\n"
    )
