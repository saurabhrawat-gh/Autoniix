"""Dashboard BFF — Backend-for-Frontend for the Admin Dashboard.

Single-user auth (password from system_config), channel management,
workflow control (trigger / pause / resume / stop), job progress,
video output & YouTube metadata, system configuration, and a
WebSocket endpoint for real-time progress updates.

Start with:  uvicorn src.services.dashboard.main:app --host 0.0.0.0 --port 8020
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta

import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from temporalio.client import Client as TemporalClient

from src.config import settings
from src.db import get_pool
from src.schemas.common import VideoParams

logger = structlog.get_logger()

app = FastAPI(title="Dashboard BFF", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ── Session store (in-memory, single user) ─────────────────
_sessions: dict[str, float] = {}  # token -> expiry_timestamp
SESSION_TTL_HOURS = 24


# ── Helpers ────────────────────────────────────────────────

async def _get_temporal_client() -> TemporalClient:
    return await TemporalClient.connect(
        settings.temporal_host,
        namespace=getattr(settings, "temporal_namespace", "default"),
    )


async def _get_admin_password() -> str:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'dashboard_admin_password'"
    )
    return row["config_value"] if row else "admin"


async def verify_token(creds: HTTPAuthorizationCredentials | None = Depends(security)) -> str:
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = creds.credentials
    expiry = _sessions.get(token)
    if expiry is None or expiry < time.time():
        _sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return token


# ── Pydantic Models ────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str

class LoginResponse(BaseModel):
    token: str
    expires_in: int

class ChannelCreateRequest(BaseModel):
    channel_id: str
    channel_name: str
    niche: str
    content_mode: str = "short"
    sub_niche: str = ""
    auto_upload: bool = False
    videos_per_week_short: int = 7
    videos_per_week_long: int = 1
    short_form_duration: int = 60
    long_form_duration: int = 600
    schedule_enabled: bool = True
    human_review_required: str = "first_10"
    max_daily_api_spend: float = 5.00

class ChannelUpdateRequest(BaseModel):
    channel_name: str | None = None
    niche: str | None = None
    content_mode: str | None = None
    status: str | None = None
    auto_upload: bool | None = None
    videos_per_week_short: int | None = None
    videos_per_week_long: int | None = None
    short_form_duration: int | None = None
    long_form_duration: int | None = None
    schedule_enabled: bool | None = None
    human_review_required: str | None = None
    max_daily_api_spend: float | None = None

class TriggerRequest(BaseModel):
    content_mode: str = "short"
    topic_candidates: list[str] = Field(default_factory=list)
    max_cost_usd: float = 2.50

class ConfigUpdateRequest(BaseModel):
    config_key: str
    config_value: str

class R(BaseModel):
    status: str = "ok"
    data: dict | list | None = None
    error: str | None = None


# ── Health ─────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "dashboard-bff"}


# ── Auth ───────────────────────────────────────────────────

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    correct = await _get_admin_password()
    if req.password != correct:
        raise HTTPException(status_code=401, detail="Invalid password")
    token = secrets.token_urlsafe(32)
    ttl = SESSION_TTL_HOURS * 3600
    _sessions[token] = time.time() + ttl
    return LoginResponse(token=token, expires_in=ttl)


@app.post("/api/auth/logout")
async def logout(token: str = Depends(verify_token)):
    _sessions.pop(token, None)
    return R(status="ok")


@app.get("/api/auth/me")
async def me(token: str = Depends(verify_token)):
    return R(status="ok", data={"user": "admin"})


# ── Channels ───────────────────────────────────────────────

@app.get("/api/channels")
async def list_channels(_: str = Depends(verify_token)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT channel_id, channel_name, niche, sub_niche, content_mode, "
        "auto_upload, status, videos_per_week_long, videos_per_week_short, "
        "short_form_duration, long_form_duration, schedule_config, "
        "human_review_required, max_daily_api_spend, "
        "created_at FROM channels ORDER BY channel_id"
    )
    channels = []
    for r in rows:
        # Get latest video for this channel
        last_video = await pool.fetchrow(
            "SELECT content_id, status, title, total_cost, created_at "
            "FROM videos WHERE channel_id = $1 ORDER BY created_at DESC LIMIT 1",
            r["channel_id"],
        )
        # Get counts
        counts = await pool.fetchrow(
            "SELECT COUNT(*) FILTER (WHERE status = 'delivered') as delivered, "
            "COUNT(*) FILTER (WHERE status NOT IN ('delivered','failed','rejected')) as in_progress, "
            "COUNT(*) as total "
            "FROM videos WHERE channel_id = $1",
            r["channel_id"],
        )
        # Weekly usage: how many videos produced this week per content mode
        weekly = await pool.fetchrow(
            "SELECT "
            "COUNT(*) FILTER (WHERE content_mode = 'short' AND status NOT IN ('failed','rejected')) as short_used, "
            "COUNT(*) FILTER (WHERE content_mode = 'long_form' AND status NOT IN ('failed','rejected')) as long_used, "
            "COUNT(*) FILTER (WHERE content_mode = 'short' AND status = 'delivered' AND approved_at IS NOT NULL) as short_approved, "
            "COUNT(*) FILTER (WHERE content_mode = 'long_form' AND status = 'delivered' AND approved_at IS NOT NULL) as long_approved "
            "FROM videos WHERE channel_id = $1 AND created_at >= date_trunc('week', NOW())",
            r["channel_id"],
        )
        # Check if any workflow is currently running or paused
        active_job = await pool.fetchrow(
            "SELECT content_id, status, content_mode FROM videos WHERE channel_id = $1 "
            "AND status NOT IN ('delivered', 'failed', 'rejected') "
            "ORDER BY created_at DESC LIMIT 1",
            r["channel_id"],
        )
        # Parse schedule_config
        sched_raw = r["schedule_config"]
        sched = json.loads(sched_raw) if isinstance(sched_raw, str) else (sched_raw or {})
        schedule_enabled = sched.get("enabled", True) if sched else True
        channels.append({
            "channel_id": r["channel_id"],
            "channel_name": r["channel_name"],
            "niche": r["niche"],
            "sub_niche": r["sub_niche"],
            "content_mode": r["content_mode"],
            "auto_upload": r["auto_upload"],
            "status": r["status"],
            "videos_per_week_long": r["videos_per_week_long"] or 1,
            "videos_per_week_short": r["videos_per_week_short"] or 7,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "last_video": {
                "content_id": last_video["content_id"],
                "status": last_video["status"],
                "title": last_video["title"],
                "cost": float(last_video["total_cost"]) if last_video["total_cost"] else 0,
                "created_at": last_video["created_at"].isoformat(),
            } if last_video else None,
            "stats": {
                "delivered": counts["delivered"] if counts else 0,
                "in_progress": counts["in_progress"] if counts else 0,
                "total": counts["total"] if counts else 0,
            },
            "weekly_usage": {
                "short": {"used": weekly["short_used"] if weekly else 0, "limit": r["videos_per_week_short"] or 7, "approved": weekly["short_approved"] if weekly else 0},
                "long_form": {"used": weekly["long_used"] if weekly else 0, "limit": r["videos_per_week_long"] or 1, "approved": weekly["long_approved"] if weekly else 0},
            },
            "schedule_enabled": schedule_enabled,
            "short_form_duration": r["short_form_duration"] or 60,
            "long_form_duration": r["long_form_duration"] or 600,
            "human_review_required": r["human_review_required"] or "first_10",
            "max_daily_api_spend": float(r["max_daily_api_spend"]) if r["max_daily_api_spend"] else 5.0,
            "active_job": {
                "content_id": active_job["content_id"],
                "status": active_job["status"],
                "content_mode": active_job["content_mode"],
            } if active_job else None,
        })
    return R(status="ok", data=channels)


@app.post("/api/channels")
async def create_channel(req: ChannelCreateRequest, _: str = Depends(verify_token)):
    pool = await get_pool()
    try:
        sched_json = json.dumps({"enabled": req.schedule_enabled})
        await pool.execute(
            "INSERT INTO channels (channel_id, channel_name, niche, sub_niche, "
            "content_mode, auto_upload, videos_per_week_short, videos_per_week_long, "
            "short_form_duration, long_form_duration, schedule_config, "
            "human_review_required, max_daily_api_spend) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13)",
            req.channel_id, req.channel_name, req.niche, req.sub_niche,
            req.content_mode, req.auto_upload, req.videos_per_week_short,
            req.videos_per_week_long, req.short_form_duration, req.long_form_duration,
            sched_json, req.human_review_required, req.max_daily_api_spend,
        )
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(status_code=409, detail="Channel already exists")
        raise HTTPException(status_code=500, detail=str(exc))
    return R(status="ok", data={"channel_id": req.channel_id})


@app.put("/api/channels/{channel_id}")
async def update_channel(channel_id: str, req: ChannelUpdateRequest, _: str = Depends(verify_token)):
    pool = await get_pool()
    sets, vals, idx = [], [], 1
    for field, col in [
        ("channel_name", "channel_name"), ("niche", "niche"),
        ("content_mode", "content_mode"), ("status", "status"),
        ("human_review_required", "human_review_required"),
    ]:
        val = getattr(req, field, None)
        if val is not None:
            sets.append(f"{col} = ${idx}")
            vals.append(val)
            idx += 1
    for field, col in [
        ("auto_upload", "auto_upload"),
    ]:
        val = getattr(req, field, None)
        if val is not None:
            sets.append(f"{col} = ${idx}")
            vals.append(val)
            idx += 1
    for field, col in [
        ("videos_per_week_short", "videos_per_week_short"),
        ("videos_per_week_long", "videos_per_week_long"),
        ("short_form_duration", "short_form_duration"),
        ("long_form_duration", "long_form_duration"),
    ]:
        val = getattr(req, field, None)
        if val is not None:
            sets.append(f"{col} = ${idx}")
            vals.append(val)
            idx += 1
    if req.max_daily_api_spend is not None:
        sets.append(f"max_daily_api_spend = ${idx}")
        vals.append(req.max_daily_api_spend)
        idx += 1
    if req.schedule_enabled is not None:
        sets.append(f"schedule_config = ${idx}::jsonb")
        vals.append(json.dumps({"enabled": req.schedule_enabled}))
        idx += 1
    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets.append("updated_at = NOW()")
    vals.append(channel_id)
    query = f"UPDATE channels SET {', '.join(sets)} WHERE channel_id = ${idx}"
    result = await pool.execute(query, *vals)
    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail="Channel not found")
    return R(status="ok", data={"channel_id": channel_id})


@app.put("/api/channels/{channel_id}/enable")
async def enable_channel(channel_id: str, _: str = Depends(verify_token)):
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE channels SET status = 'active', updated_at = NOW() WHERE channel_id = $1",
        channel_id,
    )
    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail="Channel not found")
    # Resume any paused workflows for this channel
    resumed = await _signal_running_workflows(channel_id, "resume_workflow", None)
    return R(status="ok", data={"channel_id": channel_id, "status": "active", "resumed_workflows": resumed})


@app.put("/api/channels/{channel_id}/disable")
async def disable_channel(channel_id: str, _: str = Depends(verify_token)):
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE channels SET status = 'disabled', updated_at = NOW() WHERE channel_id = $1",
        channel_id,
    )
    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail="Channel not found")
    # Pause any running workflows for this channel (don't kill)
    paused = await _signal_running_workflows(channel_id, "pause_workflow", None)
    return R(status="ok", data={"channel_id": channel_id, "status": "disabled", "paused_workflows": paused})


# ── Workflow Control ───────────────────────────────────────

@app.post("/api/channels/{channel_id}/trigger")
async def trigger_production(channel_id: str, req: TriggerRequest, _: str = Depends(verify_token)):
    """Manually trigger a VideoProductionWorkflow for a channel."""
    pool = await get_pool()
    ch = await pool.fetchrow("SELECT channel_id, content_mode, status FROM channels WHERE channel_id = $1", channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    if ch["status"] != "active":
        raise HTTPException(status_code=400, detail="Channel is disabled — enable it first")

    # Budget checks: global daily + per-channel daily
    global_limit_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'daily_budget_limit'"
    )
    global_limit = float(global_limit_row["config_value"]) if global_limit_row else 50.0
    global_spent = await pool.fetchval(
        "SELECT COALESCE(SUM(total_cost), 0) FROM videos WHERE created_at::date = CURRENT_DATE"
    )
    if float(global_spent) >= global_limit:
        raise HTTPException(status_code=400, detail=f"Global daily budget exhausted (${global_limit:.2f})")

    ch_full = await pool.fetchrow(
        "SELECT max_daily_api_spend FROM channels WHERE channel_id = $1", channel_id
    )
    ch_limit = float(ch_full["max_daily_api_spend"]) if ch_full and ch_full["max_daily_api_spend"] else 5.0
    ch_spent = await pool.fetchval(
        "SELECT COALESCE(SUM(total_cost), 0) FROM videos "
        "WHERE channel_id = $1 AND created_at::date = CURRENT_DATE",
        channel_id,
    )
    if float(ch_spent) >= ch_limit:
        raise HTTPException(status_code=400, detail=f"Channel daily budget exhausted (${ch_limit:.2f})")

    content_mode = req.content_mode or ch["content_mode"]
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    workflow_id = f"manual-{channel_id}-{ts}"

    try:
        client = await _get_temporal_client()
        await client.start_workflow(
            "VideoProductionWorkflow",
            VideoParams(
                channel_id=channel_id,
                content_mode=content_mode,
                topic_candidates=req.topic_candidates,
                max_cost_usd=req.max_cost_usd,
            ),
            id=workflow_id,
            task_queue="video-production",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {exc}")

    return R(status="ok", data={"workflow_id": workflow_id, "channel_id": channel_id})


@app.post("/api/channels/{channel_id}/pause")
async def pause_production(channel_id: str, _: str = Depends(verify_token)):
    """Send pause signal to all running workflows for a channel."""
    paused = await _signal_running_workflows(channel_id, "pause_workflow", None)
    return R(status="ok", data={"channel_id": channel_id, "paused_workflows": paused})


@app.post("/api/channels/{channel_id}/resume")
async def resume_production(channel_id: str, _: str = Depends(verify_token)):
    """Send resume signal to all running workflows for a channel."""
    resumed = await _signal_running_workflows(channel_id, "resume_workflow", None)
    return R(status="ok", data={"channel_id": channel_id, "resumed_workflows": resumed})


@app.post("/api/channels/{channel_id}/stop")
async def stop_production(channel_id: str, _: str = Depends(verify_token)):
    """Send emergency_stop signal to all running workflows for a channel."""
    stopped = await _signal_running_workflows(channel_id, "emergency_stop", None)
    return R(status="ok", data={"channel_id": channel_id, "stopped_workflows": stopped})


async def _signal_running_workflows(channel_id: str, signal_name: str, signal_arg) -> list[str]:
    """Find running workflows for a channel and send them a signal."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT content_id FROM videos WHERE channel_id = $1 "
        "AND status NOT IN ('delivered', 'failed', 'rejected') "
        "ORDER BY created_at DESC LIMIT 5",
        channel_id,
    )
    if not rows:
        return []

    client = await _get_temporal_client()
    signaled = []
    for row in rows:
        content_id = row["content_id"]
        # Try to find the Temporal workflow by content_id pattern
        try:
            # Workflows are named: manual-{channel_id}-{ts} or video-{channel_id}-{ts}
            # We query by listing workflows for this channel
            handle = client.get_workflow_handle_for(
                None, workflow_id=content_id,
            )
            # Fallback: try common ID patterns
        except Exception:
            pass

        # Search for workflows matching this channel
        try:
            query = f'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
            async for wf in client.list_workflows(query=query):
                wf_id = wf.id
                if channel_id in wf_id:
                    try:
                        handle = client.get_workflow_handle(wf_id)
                        if signal_arg is not None:
                            await handle.signal(signal_name, signal_arg)
                        else:
                            await handle.signal(signal_name)
                        signaled.append(wf_id)
                    except Exception as sig_exc:
                        logger.warning("signal.failed", workflow_id=wf_id, error=str(sig_exc))
        except Exception as list_exc:
            logger.warning("workflow.list.failed", error=str(list_exc))

    return signaled


# ── Jobs (Videos) ──────────────────────────────────────────

@app.get("/api/channels/{channel_id}/jobs")
async def list_jobs(
    channel_id: str,
    content_mode: str | None = None,
    limit: int = Query(default=50, le=200),
    _: str = Depends(verify_token),
):
    """List videos for a channel, optionally filtered by content_mode (long_form / short_form)."""
    pool = await get_pool()
    conditions = ["channel_id = $1"]
    params: list = [channel_id]
    idx = 2
    if content_mode:
        conditions.append(f"content_mode = ${idx}")
        params.append(content_mode)
        idx += 1
    params.append(limit)
    query = (
        f"SELECT content_id, channel_id, status, title, content_mode, total_cost, "
        f"youtube_video_id, rendered_video_url, thumbnail_variants_urls, "
        f"delivery_result, created_at, updated_at "
        f"FROM videos WHERE {' AND '.join(conditions)} "
        f"ORDER BY created_at DESC LIMIT ${idx}"
    )
    rows = await pool.fetch(query, *params)
    jobs = []
    for r in rows:
        jobs.append({
            "content_id": r["content_id"],
            "channel_id": r["channel_id"],
            "status": r["status"],
            "title": r["title"],
            "content_mode": r["content_mode"],
            "total_cost": float(r["total_cost"]) if r["total_cost"] else 0,
            "youtube_video_id": r["youtube_video_id"],
            "video_url": r["rendered_video_url"],
            "thumbnail_urls": json.loads(r["thumbnail_variants_urls"]) if r["thumbnail_variants_urls"] else [],
            "delivery_result": json.loads(r["delivery_result"]) if r["delivery_result"] else {},
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        })
    return R(status="ok", data=jobs)


@app.get("/api/jobs/{content_id}/progress")
async def job_progress(content_id: str, _: str = Depends(verify_token)):
    """Get step-by-step progress timeline for a specific video job."""
    pool = await get_pool()
    events = await pool.fetch(
        "SELECT phase, status, detail, cost_usd, duration_ms, created_at "
        "FROM job_events WHERE content_id = $1 ORDER BY created_at ASC",
        content_id,
    )
    # Also get current video status
    video = await pool.fetchrow(
        "SELECT status, total_cost FROM videos WHERE content_id = $1", content_id
    )

    # Try to get live status from Temporal
    live_status = None
    try:
        client = await _get_temporal_client()
        query = f'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
        async for wf in client.list_workflows(query=query):
            if content_id.replace("VID_", "") in wf.id or any(
                content_id in str(getattr(wf, attr, ""))
                for attr in ["id", "run_id"]
            ):
                handle = client.get_workflow_handle(wf.id)
                live_status = await handle.query("get_status")
                break
    except Exception:
        pass

    timeline = []
    for ev in events:
        timeline.append({
            "phase": ev["phase"],
            "status": ev["status"],
            "detail": json.loads(ev["detail"]) if isinstance(ev["detail"], str) else (ev["detail"] or {}),
            "cost_usd": float(ev["cost_usd"]) if ev["cost_usd"] else 0,
            "duration_ms": ev["duration_ms"] or 0,
            "timestamp": ev["created_at"].isoformat() if ev["created_at"] else None,
        })

    return R(status="ok", data={
        "content_id": content_id,
        "current_status": video["status"] if video else "unknown",
        "total_cost": float(video["total_cost"]) if video and video["total_cost"] else 0,
        "live": live_status,
        "timeline": timeline,
    })


@app.get("/api/jobs/{content_id}/metadata")
async def job_metadata(content_id: str, _: str = Depends(verify_token)):
    """Get YouTube metadata (title, description, tags, SEO) for copy-paste."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT title, delivery_result, thumbnail_variants_urls, content_mode "
        "FROM videos WHERE content_id = $1",
        content_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    delivery = json.loads(row["delivery_result"]) if row["delivery_result"] else {}
    thumbnails = json.loads(row["thumbnail_variants_urls"]) if row["thumbnail_variants_urls"] else []

    return R(status="ok", data={
        "content_id": content_id,
        "content_mode": row["content_mode"],
        "title": row["title"] or delivery.get("title", ""),
        "description": delivery.get("description", ""),
        "tags": delivery.get("tags", []),
        "seo_score": delivery.get("seo_score"),
        "hashtags": delivery.get("hashtags", []),
        "category": delivery.get("category", ""),
        "privacy_status": delivery.get("privacy_status", "private"),
        "thumbnails": thumbnails,
    })


@app.get("/api/jobs/{content_id}/output")
async def job_output(content_id: str, _: str = Depends(verify_token)):
    """Get final video output: video URL, thumbnail, download link."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT title, rendered_video_url, thumbnail_variants_urls, "
        "youtube_video_id, total_cost, status "
        "FROM videos WHERE content_id = $1",
        content_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    thumbnails = json.loads(row["thumbnail_variants_urls"]) if row["thumbnail_variants_urls"] else []

    return R(status="ok", data={
        "content_id": content_id,
        "title": row["title"],
        "status": row["status"],
        "video_url": row["rendered_video_url"],
        "download_url": row["rendered_video_url"],  # MinIO direct URL
        "thumbnails": thumbnails,
        "youtube_video_id": row["youtube_video_id"],
        "youtube_url": f"https://youtu.be/{row['youtube_video_id']}" if row["youtube_video_id"] else None,
        "total_cost": float(row["total_cost"]) if row["total_cost"] else 0,
    })


# ── Job Approval / Rejection ──────────────────────────────

@app.post("/api/jobs/{content_id}/approve")
async def approve_job(content_id: str, _: str = Depends(verify_token)):
    """Mark a delivered video as approved/completed."""
    pool = await get_pool()
    video = await pool.fetchrow("SELECT status FROM videos WHERE content_id = $1", content_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video["status"] != "delivered":
        raise HTTPException(status_code=400, detail=f"Cannot approve video with status '{video['status']}'")
    await pool.execute(
        "UPDATE videos SET approved_by = 'admin', approved_at = NOW(), updated_at = NOW() "
        "WHERE content_id = $1",
        content_id,
    )
    return R(status="ok", data={"content_id": content_id, "approved": True})


@app.post("/api/jobs/{content_id}/reject")
async def reject_job(content_id: str, _: str = Depends(verify_token)):
    """Reject a delivered video — frees up weekly limit for regeneration."""
    pool = await get_pool()
    video = await pool.fetchrow("SELECT status FROM videos WHERE content_id = $1", content_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video["status"] not in ("delivered", "pending_review"):
        raise HTTPException(status_code=400, detail=f"Cannot reject video with status '{video['status']}'")
    await pool.execute(
        "UPDATE videos SET status = 'rejected', updated_at = NOW() WHERE content_id = $1",
        content_id,
    )
    return R(status="ok", data={"content_id": content_id, "rejected": True})


@app.post("/api/jobs/{content_id}/retry")
async def retry_job(content_id: str, _: str = Depends(verify_token)):
    """Retry a failed job from its last checkpoint."""
    pool = await get_pool()
    video = await pool.fetchrow(
        "SELECT channel_id, content_mode, checkpoint, status "
        "FROM videos WHERE content_id = $1",
        content_id,
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video["status"] != "failed":
        raise HTTPException(status_code=400, detail=f"Can only retry failed jobs, current: '{video['status']}'")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    workflow_id = f"retry-{video['channel_id']}-{ts}"
    try:
        client = await _get_temporal_client()
        await client.start_workflow(
            "VideoProductionWorkflow",
            VideoParams(
                channel_id=video["channel_id"],
                content_mode=video["content_mode"] or "short",
                resume_from=video["checkpoint"],
                original_content_id=content_id,
            ),
            id=workflow_id,
            task_queue="video-production",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start retry workflow: {exc}")
    return R(status="ok", data={
        "workflow_id": workflow_id,
        "content_id": content_id,
        "resume_from": video["checkpoint"],
    })


# ── Active Jobs (all in-progress across channels) ────────

@app.get("/api/jobs/active")
async def active_jobs(_: str = Depends(verify_token)):
    """Get all currently in-progress + recently failed (24h) video jobs."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT v.content_id, v.channel_id, v.status, v.title, v.content_mode, "
        "v.total_cost, v.checkpoint, v.error_message, v.created_at, c.channel_name "
        "FROM videos v JOIN channels c ON v.channel_id = c.channel_id "
        "WHERE v.status NOT IN ('delivered', 'rejected') "
        "AND (v.status != 'failed' OR v.updated_at > NOW() - INTERVAL '24 hours') "
        "ORDER BY v.created_at DESC"
    )
    jobs = []
    for r in rows:
        # Get latest event for this job
        last_event = await pool.fetchrow(
            "SELECT phase, status, created_at FROM job_events "
            "WHERE content_id = $1 ORDER BY created_at DESC LIMIT 1",
            r["content_id"],
        )
        jobs.append({
            "content_id": r["content_id"],
            "channel_id": r["channel_id"],
            "channel_name": r["channel_name"],
            "status": r["status"],
            "title": r["title"],
            "content_mode": r["content_mode"],
            "total_cost": float(r["total_cost"]) if r["total_cost"] else 0,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "current_phase": last_event["phase"] if last_event else None,
            "phase_status": last_event["status"] if last_event else None,
            "last_event_at": last_event["created_at"].isoformat() if last_event and last_event["created_at"] else None,
            "checkpoint": r["checkpoint"],
            "error_message": r["error_message"],
        })
    return R(status="ok", data=jobs)


# ── Workflow Status (per channel) ─────────────────────────

@app.get("/api/channels/{channel_id}/workflow-status")
async def workflow_status(channel_id: str, _: str = Depends(verify_token)):
    """Get current workflow state for a channel."""
    pool = await get_pool()
    active = await pool.fetchrow(
        "SELECT content_id, status FROM videos WHERE channel_id = $1 "
        "AND status NOT IN ('delivered', 'failed', 'rejected') "
        "ORDER BY created_at DESC LIMIT 1",
        channel_id,
    )
    is_paused = False
    if active:
        try:
            client = await _get_temporal_client()
            query = f'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
            async for wf in client.list_workflows(query=query):
                if channel_id in wf.id:
                    handle = client.get_workflow_handle(wf.id)
                    status = await handle.query("get_status")
                    is_paused = status.get("paused", False)
                    break
        except Exception:
            pass
    return R(status="ok", data={
        "has_running": active is not None,
        "is_paused": is_paused,
        "active_content_id": active["content_id"] if active else None,
        "active_status": active["status"] if active else None,
    })


# ── System Config ──────────────────────────────────────────

@app.get("/api/config")
async def get_config(_: str = Depends(verify_token)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT config_key, config_value, description FROM system_config "
        "ORDER BY config_key"
    )
    configs = [
        {"key": r["config_key"], "value": r["config_value"], "description": r["description"]}
        for r in rows
    ]
    return R(status="ok", data=configs)


@app.put("/api/config")
async def update_config(req: ConfigUpdateRequest, _: str = Depends(verify_token)):
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE system_config SET config_value = $1, updated_at = NOW() "
        "WHERE config_key = $2",
        req.config_value, req.config_key,
    )
    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail="Config key not found")
    return R(status="ok", data={"key": req.config_key, "value": req.config_value})


@app.post("/api/emergency-stop")
async def emergency_stop(_: str = Depends(verify_token)):
    """Freeze the entire system: set flag + PAUSE all running workflows (not kill)."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE system_config SET config_value = 'true', updated_at = NOW() "
        "WHERE config_key = 'emergency_stop'"
    )
    # Pause (not kill) all running workflows to preserve progress and cost
    paused_count = 0
    try:
        client = await _get_temporal_client()
        query = 'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
        async for wf in client.list_workflows(query=query):
            try:
                handle = client.get_workflow_handle(wf.id)
                await handle.signal("pause_workflow")
                paused_count += 1
            except Exception:
                pass
    except Exception:
        pass
    return R(status="ok", data={"emergency_stop": True, "workflows_paused": paused_count})


@app.post("/api/emergency-resume")
async def emergency_resume(_: str = Depends(verify_token)):
    """Un-freeze the system: clear flag + RESUME all paused workflows."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE system_config SET config_value = 'false', updated_at = NOW() "
        "WHERE config_key = 'emergency_stop'"
    )
    # Resume all paused workflows
    resumed_count = 0
    try:
        client = await _get_temporal_client()
        query = 'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
        async for wf in client.list_workflows(query=query):
            try:
                handle = client.get_workflow_handle(wf.id)
                await handle.signal("resume_workflow")
                resumed_count += 1
            except Exception:
                pass
    except Exception:
        pass
    return R(status="ok", data={"emergency_stop": False, "workflows_resumed": resumed_count})


# ── Dashboard Stats ────────────────────────────────────────

@app.get("/api/stats")
async def dashboard_stats(_: str = Depends(verify_token)):
    pool = await get_pool()
    channels = await pool.fetchrow(
        "SELECT COUNT(*) as total, "
        "COUNT(*) FILTER (WHERE status = 'active') as active, "
        "COUNT(*) FILTER (WHERE status = 'disabled') as disabled "
        "FROM channels"
    )
    videos_today = await pool.fetchrow(
        "SELECT COUNT(*) as total, "
        "COUNT(*) FILTER (WHERE status = 'delivered') as delivered, "
        "COUNT(*) FILTER (WHERE status = 'failed') as failed, "
        "COUNT(*) FILTER (WHERE status NOT IN ('delivered','failed','rejected')) as in_progress, "
        "COALESCE(SUM(total_cost), 0) as total_cost "
        "FROM videos WHERE created_at::date = CURRENT_DATE"
    )
    budget_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'daily_budget_limit'"
    )
    emergency_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'emergency_stop'"
    )
    return R(status="ok", data={
        "channels": {
            "total": channels["total"],
            "active": channels["active"],
            "disabled": channels["disabled"],
        },
        "today": {
            "videos_total": videos_today["total"],
            "delivered": videos_today["delivered"],
            "failed": videos_today["failed"],
            "in_progress": videos_today["in_progress"],
            "cost": float(videos_today["total_cost"]),
        },
        "budget": {
            "daily_limit": float(budget_row["config_value"]) if budget_row else 50.0,
            "used_today": float(videos_today["total_cost"]),
        },
        "emergency_stop": emergency_row["config_value"] == "true" if emergency_row else False,
    })


# ── WebSocket: Real-time Progress ─────────────────────────

@app.websocket("/api/ws/progress/{content_id}")
async def ws_progress(websocket: WebSocket, content_id: str):
    """Stream real-time progress updates for a video job."""
    await websocket.accept()
    pool = await get_pool()
    last_event_id = 0

    try:
        while True:
            # Fetch new events since last check
            events = await pool.fetch(
                "SELECT id, phase, status, detail, cost_usd, created_at "
                "FROM job_events WHERE content_id = $1 AND id > $2 "
                "ORDER BY id ASC",
                content_id, last_event_id,
            )
            for ev in events:
                last_event_id = ev["id"]
                await websocket.send_json({
                    "type": "event",
                    "phase": ev["phase"],
                    "status": ev["status"],
                    "detail": json.loads(ev["detail"]) if isinstance(ev["detail"], str) else (ev["detail"] or {}),
                    "cost_usd": float(ev["cost_usd"]) if ev["cost_usd"] else 0,
                    "timestamp": ev["created_at"].isoformat() if ev["created_at"] else None,
                })

            # Check if job is done
            video = await pool.fetchrow(
                "SELECT status FROM videos WHERE content_id = $1", content_id
            )
            if video and video["status"] in ("delivered", "failed", "rejected"):
                await websocket.send_json({
                    "type": "done",
                    "final_status": video["status"],
                })
                break

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws.progress.error", content_id=content_id, error=str(exc))
        try:
            await websocket.close()
        except Exception:
            pass


# ── Startup ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8020)
