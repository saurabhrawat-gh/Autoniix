"""Jobs v2 — progress, output, metadata, review, retry, job-level workflow control.

All Temporal-coupled operations (pause/resume/stop/retry/restart, active list,
progress with live status) proxy to the legacy BFF at ``http://localhost:8020``
so we don't duplicate the Temporal client setup. Read-only DB operations
(output, metadata, approve, reject) are implemented directly for lower latency.

Endpoints:
  GET  /jobs/active                  All in-progress + recently failed jobs
  GET  /jobs/{id}/progress           Timeline + live Temporal status
  GET  /jobs/{id}/output             Video URL, thumbnails, YouTube link
  GET  /jobs/{id}/metadata           YouTube metadata fields
  POST /jobs/{id}/approve            Mark delivered video as approved
  POST /jobs/{id}/reject             Reject delivered video
  POST /jobs/{id}/retry              Retry failed job (new content_id)
  POST /jobs/{id}/restart            Restart from checkpoint (same content_id)
  POST /jobs/{id}/pause              Pause running job
  POST /jobs/{id}/resume             Resume paused job
  POST /jobs/{id}/stop               Terminate running job
"""
from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from src.db import get_pool

from ._deps import Principal, audit, principal_dep, require_role

router = APIRouter()

_LEGACY = "http://localhost:8020"


async def _proxy(request: Request, method: str, path: str, **kwargs) -> dict:
    """Forward a request to the legacy BFF, forwarding the auth token."""
    token = request.headers.get("Authorization", "")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.request(
                method,
                f"{_LEGACY}{path}",
                headers={"Authorization": token},
                **kwargs,
            )
        if resp.status_code >= 400:
            detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise HTTPException(resp.status_code, detail)
        return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(502, f"Legacy BFF unreachable: {exc}") from exc


# ── Active jobs ────────────────────────────────────────────


@router.get("/active")
async def active_jobs(
    request: Request,
    _: Principal = Depends(principal_dep),
):
    """All in-progress + recently failed (24 h) jobs across all channels."""
    return await _proxy(request, "GET", "/api/jobs/active")


# ── Per-job detail ─────────────────────────────────────────


@router.get("/{content_id}/progress")
async def job_progress(
    content_id: str,
    request: Request,
    _: Principal = Depends(principal_dep),
):
    """Step-by-step timeline + live Temporal status."""
    return await _proxy(request, "GET", f"/api/jobs/{content_id}/progress")


@router.get("/{content_id}/output")
async def job_output(
    content_id: str,
    _: Principal = Depends(principal_dep),
):
    """Video URL, thumbnails, YouTube link — read directly from DB."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT title, rendered_video_url, thumbnail_variants_urls, "
        "youtube_video_id, total_cost, status "
        "FROM videos WHERE content_id = $1",
        content_id,
    )
    if not row:
        raise HTTPException(404, "Video not found")
    thumbnails = json.loads(row["thumbnail_variants_urls"]) if row["thumbnail_variants_urls"] else []
    proxy_url = f"/api/jobs/{content_id}/video" if row["rendered_video_url"] else ""
    return {
        "status": "ok",
        "data": {
            "content_id": content_id,
            "title": row["title"],
            "status": row["status"],
            "video_url": proxy_url,
            "download_url": proxy_url,
            "thumbnails": thumbnails,
            "youtube_video_id": row["youtube_video_id"],
            "youtube_url": f"https://youtu.be/{row['youtube_video_id']}" if row["youtube_video_id"] else None,
            "total_cost": float(row["total_cost"]) if row["total_cost"] else 0,
        },
    }


@router.get("/{content_id}/metadata")
async def job_metadata(
    content_id: str,
    _: Principal = Depends(principal_dep),
):
    """YouTube metadata fields — read directly from DB."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT title, delivery_result, thumbnail_variants_urls, content_mode "
        "FROM videos WHERE content_id = $1",
        content_id,
    )
    if not row:
        raise HTTPException(404, "Video not found")
    delivery = json.loads(row["delivery_result"]) if row["delivery_result"] else {}
    thumbnails = json.loads(row["thumbnail_variants_urls"]) if row["thumbnail_variants_urls"] else []
    return {
        "status": "ok",
        "data": {
            "content_id": content_id,
            "title": delivery.get("title") or row["title"] or "",
            "description": delivery.get("description", ""),
            "tags": delivery.get("tags", []),
            "hashtags": delivery.get("hashtags", []),
            "category": delivery.get("category", ""),
            "seo_score": delivery.get("seo_score"),
            "thumbnails": thumbnails,
            "content_mode": row["content_mode"],
        },
    }


# ── Review actions ─────────────────────────────────────────


@router.post("/{content_id}/approve")
async def approve_job(
    content_id: str,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin", "editor")),
):
    """Mark a delivered video as approved."""
    pool = await get_pool()
    video = await pool.fetchrow("SELECT status FROM videos WHERE content_id = $1", content_id)
    if not video:
        raise HTTPException(404, "Video not found")
    await pool.execute(
        "UPDATE videos SET approved_at = NOW(), approved_by = $1 WHERE content_id = $2",
        actor.user_id,
        content_id,
    )
    await audit(actor=actor, action="job.approve", target_type="video",
                target_id=content_id, request=request)
    return {"status": "ok", "data": {"content_id": content_id, "approved": True}}


@router.post("/{content_id}/reject")
async def reject_job(
    content_id: str,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin", "editor")),
):
    """Reject a delivered video, freeing the weekly slot for regeneration."""
    pool = await get_pool()
    video = await pool.fetchrow("SELECT status FROM videos WHERE content_id = $1", content_id)
    if not video:
        raise HTTPException(404, "Video not found")
    await pool.execute(
        "UPDATE videos SET status = 'rejected', updated_at = NOW() WHERE content_id = $1",
        content_id,
    )
    await audit(actor=actor, action="job.reject", target_type="video",
                target_id=content_id, request=request)
    return {"status": "ok", "data": {"content_id": content_id, "rejected": True}}


# ── Retry / restart (Temporal-coupled) ────────────────────


@router.post("/{content_id}/retry")
async def retry_job(
    content_id: str,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin", "editor")),
):
    """Retry a failed job — creates a brand-new video from scratch."""
    result = await _proxy(request, "POST", f"/api/jobs/{content_id}/retry")
    await audit(actor=actor, action="job.retry", target_type="video",
                target_id=content_id, request=request)
    return result


@router.post("/{content_id}/restart")
async def restart_job(
    content_id: str,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin", "editor")),
):
    """Restart a stopped/failed job from its last checkpoint."""
    result = await _proxy(request, "POST", f"/api/jobs/{content_id}/restart")
    await audit(actor=actor, action="job.restart", target_type="video",
                target_id=content_id, request=request)
    return result


# ── Job-level workflow control ─────────────────────────────


@router.post("/{content_id}/pause")
async def pause_job(
    content_id: str,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin", "editor")),
):
    """Pause a specific running job."""
    result = await _proxy(request, "POST", f"/api/jobs/{content_id}/pause")
    await audit(actor=actor, action="job.pause", target_type="video",
                target_id=content_id, request=request)
    return result


@router.post("/{content_id}/resume")
async def resume_job(
    content_id: str,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin", "editor")),
):
    """Resume a paused job."""
    result = await _proxy(request, "POST", f"/api/jobs/{content_id}/resume")
    await audit(actor=actor, action="job.resume", target_type="video",
                target_id=content_id, request=request)
    return result


@router.post("/{content_id}/stop")
async def stop_job(
    content_id: str,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin", "editor")),
):
    """Terminate a specific running job immediately."""
    result = await _proxy(request, "POST", f"/api/jobs/{content_id}/stop")
    await audit(actor=actor, action="job.stop", target_type="video",
                target_id=content_id, request=request)
    return result
