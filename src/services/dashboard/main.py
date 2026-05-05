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
from src.environment import get_mode, set_db_mode_override, is_test
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
    # Brand DNA (optional — generated via /generate-brand-dna or filled by user)
    belief_territory: str | None = None
    intellectual_lens: str | None = None
    topic_domain: str | None = None
    brand_voice: str | None = None
    narrative_rhythm: str | None = None
    emotional_contract: str | None = None
    target_audience: str | None = None
    primary_format_long: str | None = None
    primary_format_short: str | None = None
    thumbnail_style: str | None = None
    primary_color: str | None = None
    forbidden_words: str | None = None

class BrandDnaRequest(BaseModel):
    channel_name: str
    niche: str
    sub_niche: str = ""
    content_modes: list[str] = ["short"]

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
async def list_channels(
    include_archived: bool = Query(default=False),
    _: str = Depends(verify_token),
):
    pool = await get_pool()
    status_filter = "" if include_archived else "WHERE status != 'archived'"
    rows = await pool.fetch(
        f"SELECT channel_id, channel_name, niche, sub_niche, content_mode, "
        f"auto_upload, status, videos_per_week_long, videos_per_week_short, "
        f"short_form_duration, long_form_duration, schedule_config, "
        f"human_review_required, max_daily_api_spend, "
        f"created_at FROM channels {status_filter} ORDER BY channel_id"
    )
    # Batch-query Temporal for paused state of all running workflows (once)
    _paused_wf_map: dict[str, bool] = {}
    try:
        _tc = await _get_temporal_client()
        _q = 'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
        async for _wf in _tc.list_workflows(query=_q):
            try:
                _h = _tc.get_workflow_handle(_wf.id)
                _s = await _h.query("get_status")
                _paused_wf_map[_wf.id] = _s.get("paused", False)
            except Exception:
                pass
    except Exception:
        pass

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
            "SELECT COUNT(*) FILTER (WHERE status IN ('delivered','test_delivered')) as delivered, "
            "COUNT(*) FILTER (WHERE status NOT IN ('delivered','test_delivered','failed','stopped','superseded','rejected')) as in_progress, "
            "COUNT(*) as total "
            "FROM videos WHERE channel_id = $1",
            r["channel_id"],
        )
        # Weekly usage: how many videos produced this week per content mode
        weekly = await pool.fetchrow(
            "SELECT "
            "COUNT(*) FILTER (WHERE content_mode = 'short' AND status NOT IN ('failed','stopped','superseded','rejected')) as short_used, "
            "COUNT(*) FILTER (WHERE content_mode = 'long_form' AND status NOT IN ('failed','stopped','superseded','rejected')) as long_used, "
            "COUNT(*) FILTER (WHERE content_mode = 'short' AND status = 'delivered' AND approved_at IS NOT NULL) as short_approved, "
            "COUNT(*) FILTER (WHERE content_mode = 'long_form' AND status = 'delivered' AND approved_at IS NOT NULL) as long_approved "
            "FROM videos WHERE channel_id = $1 AND created_at >= date_trunc('week', NOW())",
            r["channel_id"],
        )
        # Check for all currently in-progress jobs (one per content_mode)
        active_job_rows = await pool.fetch(
            "SELECT DISTINCT ON (content_mode) content_id, status, content_mode "
            "FROM videos WHERE channel_id = $1 "
            "AND status NOT IN ('delivered', 'test_delivered', 'failed', 'stopped', 'superseded', 'rejected', 'retrying') "
            "ORDER BY content_mode, created_at DESC",
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
            "active_jobs": [
                {
                    "content_id": aj["content_id"],
                    "status": aj["status"],
                    "content_mode": aj["content_mode"],
                    "is_paused": any(
                        wp for wid, wp in _paused_wf_map.items()
                        if aj["content_id"] in wid
                    ),
                } for aj in active_job_rows
            ],
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
            "human_review_required, max_daily_api_spend, "
            "belief_territory, intellectual_lens, topic_domain, "
            "brand_voice, narrative_rhythm, emotional_contract, target_audience, "
            "primary_format_long, primary_format_short, thumbnail_style, "
            "primary_color, forbidden_words) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13, "
            "$14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25)",
            req.channel_id, req.channel_name, req.niche, req.sub_niche,
            req.content_mode, req.auto_upload, req.videos_per_week_short,
            req.videos_per_week_long, req.short_form_duration, req.long_form_duration,
            sched_json, req.human_review_required, req.max_daily_api_spend,
            req.belief_territory, req.intellectual_lens, req.topic_domain,
            req.brand_voice, req.narrative_rhythm, req.emotional_contract, req.target_audience,
            req.primary_format_long, req.primary_format_short, req.thumbnail_style,
            req.primary_color, req.forbidden_words,
        )
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(status_code=409, detail="Channel already exists")
        raise HTTPException(status_code=500, detail=str(exc))
    return R(status="ok", data={"channel_id": req.channel_id})


@app.post("/api/channels/generate-brand-dna")
async def generate_brand_dna(req: BrandDnaRequest, _: str = Depends(verify_token)):
    """Use the configured LLM provider to draft Brand DNA fields from niche + name.

    Returns editable defaults the user can tweak before saving the channel.
    Falls back to deterministic defaults if no LLM is reachable.
    """
    from src.providers import boot as _provider_boot  # noqa: F401  ensure providers register
    from src.providers.llm.base import LLMRequest
    from src.providers.registry import ProviderRegistry

    fallback = {
        "belief_territory": f"{req.niche}_misconceptions",
        "intellectual_lens": f"{req.niche}_evidence_based",
        "topic_domain": f"{req.niche} / {req.sub_niche}".strip(" /") or req.niche,
        "brand_voice": "calm_authoritative",
        "narrative_rhythm": "hook_payoff_loop",
        "emotional_contract": "curiosity_to_clarity",
        "target_audience": f"25-45_{req.niche}_curious",
        "primary_format_long": "educational_explainer",
        "primary_format_short": "hook_fact_payoff",
        "thumbnail_style": "high_contrast_text_overlay",
        "primary_color": "#0EA5E9",
        "forbidden_words": "literally,actually,basically,obviously",
    }

    system_prompt = (
        "You are a brand strategist for AI-generated YouTube channels. "
        "Given a niche and channel name, produce a tight Brand DNA that downstream "
        "research/script/thumbnail services will anchor on. "
        "Each field must be a SHORT snake_case label (1-4 words) — NOT a sentence — "
        "except target_audience (e.g. '25-45_health_curious'), primary_color (hex), "
        "and forbidden_words (comma-separated list). "
        "Respond with ONLY a valid JSON object, no markdown, with these exact keys: "
        "belief_territory, intellectual_lens, topic_domain, brand_voice, narrative_rhythm, "
        "emotional_contract, target_audience, primary_format_long, primary_format_short, "
        "thumbnail_style, primary_color, forbidden_words."
    )
    user_prompt = (
        f"Channel name: {req.channel_name}\n"
        f"Niche: {req.niche}\n"
        f"Sub-niche: {req.sub_niche or '(none)'}\n"
        f"Content modes: {', '.join(req.content_modes)}\n\n"
        "Examples for inspiration:\n"
        "- belief_territory: 'sleep_is_just_rest', 'money_anxiety_myths', 'productivity_hustle_lies'\n"
        "- intellectual_lens: 'sleep_neuroscience', 'behavioral_economics', 'cognitive_psychology'\n"
        "- brand_voice: 'calm_authoritative', 'urgent_practical', 'witty_skeptical'\n"
        "- narrative_rhythm: 'hook_payoff_loop', 'problem_twist_solution', 'myth_evidence_action'\n"
        "- emotional_contract: 'curiosity_to_clarity', 'anxiety_to_control', 'confusion_to_confidence'\n"
        "- thumbnail_style: 'high_contrast_text_overlay', 'human_face_emotion', 'data_chart_callout'"
    )

    try:
        llm = ProviderRegistry.get("llm")
        result = await llm.complete(LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=600,
            response_format="json",
        ))
        try:
            parsed = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        # Merge: parsed values take precedence, fallback fills any missing keys
        dna = {k: (parsed.get(k) or v) for k, v in fallback.items()}
        return R(status="ok", data={
            "dna": dna,
            "source": "llm",
            "model": result.model,
            "cost_usd": round(result.cost_usd, 6),
        })
    except Exception as exc:
        # No LLM provider configured / network error — return fallback so UI still works
        return R(status="ok", data={
            "dna": fallback,
            "source": "fallback",
            "reason": str(exc)[:200],
        })


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


@app.put("/api/channels/{channel_id}/archive")
async def archive_channel(channel_id: str, _: str = Depends(verify_token)):
    """Archive a channel — removes from active list but keeps all data."""
    pool = await get_pool()
    ch = await pool.fetchrow("SELECT status FROM channels WHERE channel_id = $1", channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    if ch["status"] == "archived":
        raise HTTPException(status_code=400, detail="Channel is already archived")
    # Pause running workflows first
    paused = await _signal_running_workflows(channel_id, "pause_workflow", None)
    await pool.execute(
        "UPDATE channels SET status = 'archived', updated_at = NOW() WHERE channel_id = $1",
        channel_id,
    )
    logger.info("channel.archived", channel_id=channel_id)
    return R(status="ok", data={"channel_id": channel_id, "status": "archived", "paused_workflows": paused})


@app.put("/api/channels/{channel_id}/restore")
async def restore_channel(channel_id: str, _: str = Depends(verify_token)):
    """Restore an archived channel — sets status to 'disabled' (user must explicitly enable)."""
    pool = await get_pool()
    ch = await pool.fetchrow("SELECT status FROM channels WHERE channel_id = $1", channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    if ch["status"] != "archived":
        raise HTTPException(status_code=400, detail="Channel is not archived")
    await pool.execute(
        "UPDATE channels SET status = 'disabled', updated_at = NOW() WHERE channel_id = $1",
        channel_id,
    )
    logger.info("channel.restored", channel_id=channel_id)
    return R(status="ok", data={"channel_id": channel_id, "status": "disabled"})


@app.post("/api/channels/{channel_id}/clone")
async def clone_channel(channel_id: str, _: str = Depends(verify_token)):
    """Clone a channel's config into a new channel with '_copy' suffix."""
    pool = await get_pool()
    ch = await pool.fetchrow(
        "SELECT * FROM channels WHERE channel_id = $1", channel_id
    )
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    # Generate new ID
    ts = datetime.utcnow().strftime("%m%d%H%M")
    new_id = f"{channel_id[:12]}_C{ts}"
    try:
        await pool.execute(
            "INSERT INTO channels (channel_id, channel_name, niche, sub_niche, "
            "content_mode, auto_upload, videos_per_week_short, videos_per_week_long, "
            "short_form_duration, long_form_duration, schedule_config, "
            "human_review_required, max_daily_api_spend, "
            "belief_territory, intellectual_lens, topic_domain, brand_voice, "
            "narrative_rhythm, emotional_contract, content_style, "
            "target_audience, thumbnail_style, primary_color, secondary_color, "
            "font_family, caption_style, pacing_style, elevenlabs_voice_id, "
            "voice_stability, voice_similarity, voice_style, "
            "competitor_channels, forbidden_words, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, "
            "$14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, "
            "$28, $29, $30, $31, $32, $33, 'disabled')",
            new_id, f"{ch['channel_name']} (Copy)", ch["niche"], ch["sub_niche"],
            ch["content_mode"], ch["auto_upload"],
            ch["videos_per_week_short"], ch["videos_per_week_long"],
            ch["short_form_duration"], ch["long_form_duration"],
            json.dumps(json.loads(ch["schedule_config"]) if isinstance(ch["schedule_config"], str) else (ch["schedule_config"] or {})),
            ch["human_review_required"], ch["max_daily_api_spend"],
            ch["belief_territory"], ch["intellectual_lens"], ch["topic_domain"],
            ch["brand_voice"], ch["narrative_rhythm"], ch["emotional_contract"],
            ch["content_style"], ch["target_audience"], ch["thumbnail_style"],
            ch["primary_color"], ch["secondary_color"], ch["font_family"],
            ch["caption_style"], ch["pacing_style"], ch["elevenlabs_voice_id"],
            ch["voice_stability"], ch["voice_similarity"], ch["voice_style"],
            ch["competitor_channels"], ch["forbidden_words"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Clone failed: {exc}")
    logger.info("channel.cloned", source=channel_id, new_id=new_id)
    return R(status="ok", data={"source_channel_id": channel_id, "new_channel_id": new_id})


@app.get("/api/channels/{channel_id}/export")
async def export_channel(channel_id: str, _: str = Depends(verify_token)):
    """Export full channel configuration as JSON."""
    pool = await get_pool()
    ch = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    export_data = {}
    for key in ch.keys():
        val = ch[key]
        if hasattr(val, 'isoformat'):
            val = val.isoformat()
        elif isinstance(val, (float, int, bool, str, type(None))):
            pass
        else:
            try:
                val = json.loads(val) if isinstance(val, str) else str(val)
            except Exception:
                val = str(val)
        export_data[key] = val
    return R(status="ok", data=export_data)


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

    # Prevent duplicate: check for already-running jobs for this channel + mode
    running_count = await pool.fetchval(
        "SELECT COUNT(*) FROM videos WHERE channel_id = $1 AND content_mode = $2 "
        "AND status NOT IN ('delivered', 'test_delivered', 'failed', 'stopped', 'superseded', 'rejected', 'retrying')",
        channel_id, content_mode,
    )
    if running_count and int(running_count) > 0:
        raise HTTPException(status_code=409, detail=f"Channel already has an in-progress {content_mode} job")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Resolve environment mode from DB
    env_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'environment_mode'"
    )
    env_mode = env_row["config_value"] if env_row else get_mode()

    # Pre-create video record so the UI sees it immediately
    is_test = env_mode != "production"
    prefix = "TEST_VID" if is_test else "VID"
    content_id = f"{prefix}_{channel_id}_{ts}"
    workflow_id = f"manual-{content_id}"

    # Mark all older failed/stopped jobs for this channel+mode as superseded
    await pool.execute(
        "UPDATE videos SET status = 'superseded', updated_at = NOW() "
        "WHERE channel_id = $1 AND content_mode = $2 AND status IN ('failed', 'stopped')",
        channel_id, content_mode,
    )

    await pool.execute(
        "INSERT INTO videos (content_id, channel_id, status, content_mode, environment, updated_at) "
        "VALUES ($1, $2, 'researching', $3, $4, NOW()) "
        "ON CONFLICT (content_id) DO NOTHING",
        content_id, channel_id, content_mode, env_mode,
    )

    try:
        client = await _get_temporal_client()
        await client.start_workflow(
            "VideoProductionWorkflow",
            VideoParams(
                channel_id=channel_id,
                content_mode=content_mode,
                topic_candidates=req.topic_candidates,
                max_cost_usd=req.max_cost_usd,
                content_id=content_id,
                environment=env_mode,
            ),
            id=workflow_id,
            task_queue="video-production",
        )
    except Exception as exc:
        # Clean up the pre-created video record on failure
        await pool.execute("DELETE FROM videos WHERE content_id = $1", content_id)
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {exc}")

    await _broadcast_job_event(content_id, "researching", channel_id)
    return R(status="ok", data={"workflow_id": workflow_id, "channel_id": channel_id, "content_id": content_id})


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
    """Terminate all running workflows for a channel immediately."""
    stopped = await _terminate_channel_workflows(channel_id)
    return R(status="ok", data={"channel_id": channel_id, "stopped_workflows": stopped})


async def _signal_running_workflows(channel_id: str, signal_name: str, signal_arg) -> list[str]:
    """Find running workflows for a channel and send them a signal."""
    client = await _get_temporal_client()
    signaled = []
    seen = set()
    try:
        query = 'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
        async for wf in client.list_workflows(query=query):
            wf_id = wf.id
            if channel_id in wf_id and wf_id not in seen:
                seen.add(wf_id)
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


async def _terminate_channel_workflows(channel_id: str) -> list[str]:
    """Terminate all running workflows for a channel and mark videos as failed."""
    pool = await get_pool()
    client = await _get_temporal_client()
    terminated = []
    try:
        query = 'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
        async for wf in client.list_workflows(query=query):
            wf_id = wf.id
            if channel_id in wf_id:
                try:
                    handle = client.get_workflow_handle(wf_id)
                    await handle.terminate("Stopped by user")
                    terminated.append(wf_id)
                except Exception as t_exc:
                    logger.warning("terminate.failed", workflow_id=wf_id, error=str(t_exc))
    except Exception as list_exc:
        logger.warning("workflow.list.failed", error=str(list_exc))

    # Mark all in-progress videos for this channel as stopped (not failed)
    if terminated:
        await pool.execute(
            "UPDATE videos SET status = 'stopped', error_message = 'Stopped by user', updated_at = NOW() "
            "WHERE channel_id = $1 AND status NOT IN ('delivered', 'test_delivered', 'failed', 'stopped', 'superseded', 'rejected', 'retrying')",
            channel_id,
        )
    return terminated


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
        "SELECT status, total_cost, checkpoint, error_message, channel_id FROM videos WHERE content_id = $1", content_id
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
        "checkpoint": video["checkpoint"] if video else None,
        "error_message": video["error_message"] if video else None,
        "channel_id": video["channel_id"] if video else None,
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
    """Retry a failed job — creates a brand new video from scratch."""
    pool = await get_pool()
    video = await pool.fetchrow(
        "SELECT channel_id, content_mode, status "
        "FROM videos WHERE content_id = $1",
        content_id,
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video["status"] not in ("failed", "stopped"):
        raise HTTPException(status_code=400, detail=f"Can only retry failed/stopped jobs, current: '{video['status']}'")

    content_mode = video["content_mode"] or "short"

    # Prevent duplicate: check for in-progress jobs for this channel + mode
    running = await pool.fetchval(
        "SELECT COUNT(*) FROM videos WHERE channel_id = $1 AND content_mode = $2 "
        "AND status NOT IN ('delivered', 'test_delivered', 'failed', 'stopped', 'superseded', 'rejected', 'retrying')",
        video["channel_id"], content_mode,
    )
    if running and int(running) > 0:
        raise HTTPException(status_code=409, detail=f"Channel already has an in-progress {content_mode} job")

    # Mark ALL older failed/stopped jobs for this channel+mode as superseded
    await pool.execute(
        "UPDATE videos SET status = 'superseded', updated_at = NOW() "
        "WHERE channel_id = $1 AND content_mode = $2 AND status IN ('failed', 'stopped')",
        video["channel_id"], content_mode,
    )

    # Resolve environment
    env_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'environment_mode'"
    )
    env_mode = env_row["config_value"] if env_row else get_mode()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    is_test_env = env_mode != "production"
    prefix = "TEST_VID" if is_test_env else "VID"
    new_content_id = f"{prefix}_{video['channel_id']}_{ts}"
    workflow_id = f"retry-{new_content_id}"

    # Create new video row (fresh start); original is now 'superseded'
    await pool.execute(
        "INSERT INTO videos (content_id, channel_id, status, content_mode, environment, updated_at) "
        "VALUES ($1, $2, 'researching', $3, $4, NOW()) "
        "ON CONFLICT (content_id) DO NOTHING",
        new_content_id, video["channel_id"], content_mode, env_mode,
    )

    try:
        client = await _get_temporal_client()
        await client.start_workflow(
            "VideoProductionWorkflow",
            VideoParams(
                channel_id=video["channel_id"],
                content_mode=content_mode,
                content_id=new_content_id,
                environment=env_mode,
            ),
            id=workflow_id,
            task_queue="video-production",
        )
    except Exception as exc:
        # Clean up the new video record on failure
        await pool.execute("DELETE FROM videos WHERE content_id = $1", new_content_id)
        raise HTTPException(status_code=500, detail=f"Failed to start retry workflow: {exc}")
    await _broadcast_job_event(new_content_id, "researching", video["channel_id"])
    return R(status="ok", data={
        "workflow_id": workflow_id,
        "new_content_id": new_content_id,
        "original_content_id": content_id,
    })


@app.post("/api/jobs/{content_id}/restart")
async def restart_job(content_id: str, _: str = Depends(verify_token)):
    """Restart a stopped/failed job from its last checkpoint (same video, same content_id)."""
    pool = await get_pool()
    video = await pool.fetchrow(
        "SELECT channel_id, content_mode, checkpoint, status "
        "FROM videos WHERE content_id = $1",
        content_id,
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video["status"] not in ("failed", "stopped"):
        raise HTTPException(status_code=400, detail=f"Can only restart failed/stopped jobs, current: '{video['status']}'")
    if not video["checkpoint"]:
        raise HTTPException(status_code=400, detail="No checkpoint available — use retry for a fresh start")

    content_mode = video["content_mode"] or "short"

    # Prevent duplicate: check for in-progress jobs for this channel + mode (excluding self)
    running = await pool.fetchval(
        "SELECT COUNT(*) FROM videos WHERE channel_id = $1 AND content_mode = $2 "
        "AND content_id != $3 "
        "AND status NOT IN ('delivered', 'test_delivered', 'failed', 'stopped', 'superseded', 'rejected', 'retrying')",
        video["channel_id"], content_mode, content_id,
    )
    if running and int(running) > 0:
        raise HTTPException(status_code=409, detail=f"Channel already has an in-progress {content_mode} job")

    # Resolve environment
    env_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'environment_mode'"
    )
    env_mode = env_row["config_value"] if env_row else get_mode()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    workflow_id = f"restart-{content_id}-{ts}"

    # Reset video status to the checkpoint phase
    await pool.execute(
        "UPDATE videos SET status = $1, error_message = NULL, updated_at = NOW() "
        "WHERE content_id = $2",
        video["checkpoint"], content_id,
    )

    try:
        client = await _get_temporal_client()
        await client.start_workflow(
            "VideoProductionWorkflow",
            VideoParams(
                channel_id=video["channel_id"],
                content_mode=content_mode,
                content_id=content_id,
                resume_from=video["checkpoint"],
                original_content_id=content_id,
                environment=env_mode,
            ),
            id=workflow_id,
            task_queue="video-production",
        )
    except Exception as exc:
        # Revert status on failure
        await pool.execute(
            "UPDATE videos SET status = 'stopped', error_message = 'Restart failed', updated_at = NOW() "
            "WHERE content_id = $1",
            content_id,
        )
        raise HTTPException(status_code=500, detail=f"Failed to start restart workflow: {exc}")
    await _broadcast_job_event(content_id, video["checkpoint"], video["channel_id"])
    return R(status="ok", data={
        "workflow_id": workflow_id,
        "content_id": content_id,
        "resume_from": video["checkpoint"],
    })


# ── Per-Job Control (pause / resume / stop by content_id) ─

async def _find_workflow_for_job(content_id: str) -> str | None:
    """Find the Temporal workflow ID for a given content_id."""
    try:
        client = await _get_temporal_client()
        query = 'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
        async for wf in client.list_workflows(query=query):
            if content_id in wf.id:
                return wf.id
    except Exception:
        pass
    return None


async def _mark_job_failed(content_id: str, reason: str) -> bool:
    """Mark a video as failed in DB if not already terminal. Returns True if updated."""
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE videos SET status = 'failed', error_message = $2, updated_at = NOW() "
        "WHERE content_id = $1 AND status NOT IN ('delivered', 'test_delivered', 'failed', 'stopped', 'superseded', 'rejected')",
        content_id, reason,
    )
    return "UPDATE 0" not in result


@app.post("/api/jobs/{content_id}/pause")
async def pause_job(content_id: str, _: str = Depends(verify_token)):
    """Pause a specific running job."""
    wf_id = await _find_workflow_for_job(content_id)
    if not wf_id:
        # Phantom job: DB still says in-progress but the workflow has been
        # terminated / garbage-collected. Pause is meaningless — tell the
        # caller they should Stop it instead so it gets cleaned up.
        raise HTTPException(
            status_code=409,
            detail="This job has no running workflow (orphaned state). Click Stop to clean it up.",
        )
    try:
        client = await _get_temporal_client()
        handle = client.get_workflow_handle(wf_id)
        await handle.signal("pause_workflow")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to pause: {exc}")
    await _broadcast_job_event(content_id, "paused", "")
    return R(status="ok", data={"content_id": content_id, "workflow_id": wf_id, "paused": True})


@app.post("/api/jobs/{content_id}/resume")
async def resume_job(content_id: str, _: str = Depends(verify_token)):
    """Resume a specific paused job."""
    wf_id = await _find_workflow_for_job(content_id)
    if not wf_id:
        raise HTTPException(
            status_code=409,
            detail="This job has no running workflow (orphaned state). Click Stop to clean it up.",
        )
    try:
        client = await _get_temporal_client()
        handle = client.get_workflow_handle(wf_id)
        await handle.signal("resume_workflow")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to resume: {exc}")
    await _broadcast_job_event(content_id, "resumed", "")
    return R(status="ok", data={"content_id": content_id, "workflow_id": wf_id, "resumed": True})


@app.post("/api/jobs/{content_id}/stop")
async def stop_job(content_id: str, _: str = Depends(verify_token)):
    """Terminate a specific running job immediately.

    Self-healing: even if the Temporal workflow has already been terminated
    or garbage-collected (orphaned phantom), this will still mark the video
    as failed in the DB so it disappears from the active jobs list.
    """
    wf_id = await _find_workflow_for_job(content_id)
    terminated = False
    if wf_id:
        try:
            client = await _get_temporal_client()
            handle = client.get_workflow_handle(wf_id)
            await handle.terminate("Stopped by user")
            terminated = True
        except Exception as exc:
            # Workflow exists but terminate failed — still update DB
            logger.warning("stop_job.terminate_failed", content_id=content_id, error=str(exc))
    # Update DB immediately — mark as stopped, not failed
    pool = await get_pool()
    await pool.execute(
        "UPDATE videos SET status = 'stopped', error_message = 'Stopped by user', updated_at = NOW() "
        "WHERE content_id = $1 AND status NOT IN ('delivered', 'test_delivered', 'failed', 'stopped', 'superseded', 'rejected')",
        content_id,
    )
    await _broadcast_job_event(content_id, "stopped", "")
    return R(status="ok", data={
        "content_id": content_id,
        "workflow_id": wf_id,
        "stopped": True,
        "terminated_workflow": terminated,
        "cleaned_orphan": not terminated,
    })


# ── Active Jobs (all in-progress across channels) ────────

@app.get("/api/jobs/active")
async def active_jobs(_: str = Depends(verify_token)):
    """Get all currently in-progress + recently stopped/failed (24h) video jobs."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT v.content_id, v.channel_id, v.status, v.title, v.content_mode, "
        "v.total_cost, v.checkpoint, v.error_message, v.created_at, v.updated_at, "
        "c.channel_name, "
        "je.phase AS last_phase, je.status AS last_phase_status, je.created_at AS last_event_at "
        "FROM videos v "
        "LEFT JOIN channels c ON v.channel_id = c.channel_id "
        "LEFT JOIN LATERAL ("
        "  SELECT phase, status, created_at FROM job_events "
        "  WHERE content_id = v.content_id ORDER BY created_at DESC LIMIT 1"
        ") je ON true "
        "WHERE v.status NOT IN ('delivered', 'test_delivered', 'rejected', 'retrying', 'superseded') "
        "AND (v.status NOT IN ('failed', 'stopped') OR v.updated_at > NOW() - INTERVAL '24 hours') "
        "ORDER BY v.created_at DESC"
    )

    # Batch-query Temporal for paused state of all running workflows
    paused_workflows: dict[str, bool] = {}
    try:
        client = await _get_temporal_client()
        query = 'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
        async for wf in client.list_workflows(query=query):
            try:
                handle = client.get_workflow_handle(wf.id)
                status = await handle.query("get_status")
                paused_workflows[wf.id] = status.get("paused", False)
            except Exception:
                pass
    except Exception:
        pass

    jobs = []
    for r in rows:
        cid = r["content_id"]
        ch_id = r["channel_id"] or ""
        mode = r["content_mode"] or "short"

        # Determine paused state: check if workflow for this content_id is paused
        is_paused = False
        for wf_id, wf_paused in paused_workflows.items():
            if cid in wf_id:
                is_paused = wf_paused
                break

        jobs.append({
            "content_id": cid,
            "channel_id": ch_id,
            "channel_name": r["channel_name"] or ch_id or "Unknown",
            "status": r["status"],
            "title": r["title"],
            "content_mode": mode,
            "total_cost": float(r["total_cost"]) if r["total_cost"] else 0,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "current_phase": r["last_phase"],
            "phase_status": r["last_phase_status"],
            "last_event_at": r["last_event_at"].isoformat() if r["last_event_at"] else None,
            "checkpoint": r["checkpoint"],
            "error_message": r["error_message"],
            "is_paused": is_paused,
        })
    return R(status="ok", data=jobs)


# ── Workflow Status (per channel) ─────────────────────────

@app.get("/api/channels/{channel_id}/workflow-status")
async def workflow_status(channel_id: str, _: str = Depends(verify_token)):
    """Get current workflow state for a channel."""
    pool = await get_pool()
    active = await pool.fetchrow(
        "SELECT content_id, status FROM videos WHERE channel_id = $1 "
        "AND status NOT IN ('delivered', 'test_delivered', 'failed', 'stopped', 'superseded', 'rejected') "
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


# ── Environment Mode ──────────────────────────────────────

class EnvironmentSwitchRequest(BaseModel):
    mode: str  # "test" or "production"
    confirm: bool = False


@app.get("/api/environment")
async def get_environment(_: str = Depends(verify_token)):
    """Get current environment mode."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'environment_mode'"
    )
    mode = row["config_value"] if row else "test"
    switched_at_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'environment_switched_at'"
    )
    switched_by_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'environment_switched_by'"
    )

    # Cost estimate per video in production
    cost_estimate = {
        "llm": "$0.05-0.15",
        "tts": "$0.01-0.03",
        "image": "$0.04-0.12",
        "search": "$0.02-0.05",
        "total_per_video": "$0.12-0.35",
    }

    return R(status="ok", data={
        "mode": mode,
        "switched_at": switched_at_row["config_value"] if switched_at_row else None,
        "switched_by": switched_by_row["config_value"] if switched_by_row else None,
        "cost_estimate_production": cost_estimate,
    })


@app.put("/api/environment")
async def switch_environment(req: EnvironmentSwitchRequest, _: str = Depends(verify_token)):
    """Switch environment mode. Requires confirm=true for production."""
    if req.mode not in ("test", "production"):
        raise HTTPException(status_code=400, detail="Mode must be 'test' or 'production'")

    if req.mode == "production" and not req.confirm:
        raise HTTPException(
            status_code=400,
            detail="Switching to production requires confirm=true. "
                   "This will use paid APIs. Estimated cost: $0.12-0.35 per video."
        )

    pool = await get_pool()
    now = datetime.utcnow().isoformat()
    await pool.execute(
        "UPDATE system_config SET config_value = $1, updated_at = NOW() "
        "WHERE config_key = 'environment_mode'",
        req.mode,
    )
    await pool.execute(
        "UPDATE system_config SET config_value = $1, updated_at = NOW() "
        "WHERE config_key = 'environment_switched_at'",
        now,
    )
    await pool.execute(
        "UPDATE system_config SET config_value = $1, updated_at = NOW() "
        "WHERE config_key = 'environment_switched_by'",
        "admin",
    )

    # Update in-memory override for all services in this process
    set_db_mode_override(req.mode)

    # Clear provider cache so next request uses correct providers
    from src.providers.registry import ProviderRegistry
    ProviderRegistry.reset()

    logger.info("environment.switched", mode=req.mode)
    return R(status="ok", data={"mode": req.mode, "switched_at": now})


@app.get("/api/test-data/stats")
async def test_data_stats(_: str = Depends(verify_token)):
    """Get stats about test data (videos, storage, cost)."""
    pool = await get_pool()
    video_stats = await pool.fetchrow(
        "SELECT COUNT(*) as count, COALESCE(SUM(total_cost), 0) as total_cost "
        "FROM videos WHERE environment = 'test'"
    )
    job_count = await pool.fetchval(
        "SELECT COUNT(*) FROM job_events WHERE environment = 'test'"
    )
    return R(status="ok", data={
        "test_videos": video_stats["count"] if video_stats else 0,
        "test_cost_total": float(video_stats["total_cost"]) if video_stats else 0,
        "test_job_events": job_count or 0,
    })


@app.delete("/api/test-data")
async def cleanup_test_data(_: str = Depends(verify_token)):
    """Delete all test data from DB and storage."""
    pool = await get_pool()

    # Delete in correct FK order
    feedback_del = await pool.execute(
        "DELETE FROM feedback_loop WHERE environment = 'test'"
    )
    events_del = await pool.execute(
        "DELETE FROM job_events WHERE environment = 'test'"
    )
    videos_del = await pool.execute(
        "DELETE FROM videos WHERE environment = 'test'"
    )

    # Clean up MinIO test/ prefix
    storage_deleted = 0
    try:
        from src.providers.storage.minio_provider import MinIOStorage
        storage = MinIOStorage()
        storage_deleted = storage.delete_prefix("test/")
    except Exception as exc:
        logger.warning("test_data.storage_cleanup_failed", error=str(exc))

    logger.info("test_data.cleaned",
                videos=videos_del, events=events_del,
                feedback=feedback_del, storage_objects=storage_deleted)

    return R(status="ok", data={
        "deleted_videos": videos_del,
        "deleted_events": events_del,
        "deleted_feedback": feedback_del,
        "deleted_storage_objects": storage_deleted,
    })


class CleanSlateRequest(BaseModel):
    confirm: str = Field(..., description="Must be the literal string 'RESET' to proceed")


@app.post("/api/admin/clean-slate")
async def clean_slate(req: CleanSlateRequest, _: str = Depends(verify_token)):
    """Full reset: cancel running workflows, truncate job tables, wipe MinIO blobs, clear Redis locks.
    Preserves: channels, brand_profiles, system_config, prompt_registry, ML models, bandit state.
    """
    if req.confirm != "RESET":
        raise HTTPException(status_code=400, detail="Must pass confirm='RESET' to proceed")

    results: dict = {
        "workflows_terminated": 0,
        "tables_truncated": [],
        "storage_objects_deleted": 0,
        "redis_keys_deleted": 0,
    }

    # 1. Cancel / terminate all running Temporal workflows (VideoProduction + DailyScheduler)
    try:
        client = await _get_temporal_client()
        for wf_type in ("VideoProductionWorkflow", "DailySchedulerWorkflow"):
            query = f'WorkflowType = "{wf_type}" AND ExecutionStatus = "Running"'
            async for wf in client.list_workflows(query=query):
                try:
                    handle = client.get_workflow_handle(wf.id)
                    await handle.terminate("Clean slate requested")
                    results["workflows_terminated"] += 1
                except Exception as exc:
                    logger.warning("clean_slate.terminate_failed", workflow_id=wf.id, error=str(exc))
    except Exception as exc:
        logger.warning("clean_slate.temporal_scan_failed", error=str(exc))

    # 2. Truncate job tables (CASCADE handles FK deps). Order-independent with TRUNCATE CASCADE.
    pool = await get_pool()
    tables = [
        "videos", "job_events", "analytics_records", "feedback_loop",
        "experiment_assignments", "experiment_outcomes",
        "performance_outcomes", "script_outcomes",
    ]
    for t in tables:
        try:
            await pool.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
            results["tables_truncated"].append(t)
        except Exception as exc:
            # Table may not exist in all environments
            logger.warning("clean_slate.truncate_failed", table=t, error=str(exc))

    # 3. Wipe MinIO test/ and prod/ prefixes
    try:
        from src.providers.storage.minio_provider import MinIOStorage
        storage = MinIOStorage()
        for prefix in ("test/", "prod/"):
            try:
                results["storage_objects_deleted"] += storage.delete_prefix(prefix)
            except Exception as exc:
                logger.warning("clean_slate.storage_prefix_failed", prefix=prefix, error=str(exc))
    except Exception as exc:
        logger.warning("clean_slate.storage_init_failed", error=str(exc))

    # 4. Clear Redis locks and progress keys
    try:
        from src.redis_client import get_redis
        r = await get_redis()
        for pattern in ("lock:channel:*", "progress:*"):
            try:
                cursor = 0
                while True:
                    cursor, keys = await r.scan(cursor=cursor, match=pattern, count=100)
                    if keys:
                        await r.delete(*keys)
                        results["redis_keys_deleted"] += len(keys)
                    if cursor == 0:
                        break
            except Exception as exc:
                logger.warning("clean_slate.redis_scan_failed", pattern=pattern, error=str(exc))
    except Exception as exc:
        logger.warning("clean_slate.redis_init_failed", error=str(exc))

    # 5. Broadcast to connected dashboards so open tabs refresh to zero state
    try:
        await _event_broadcaster.broadcast({
            "type": "clean_slate",
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception:
        pass

    logger.info("clean_slate.done", **results)
    return R(status="ok", data=results)


# ── Dashboard Stats ────────────────────────────────────────

@app.get("/api/stats")
async def dashboard_stats(_: str = Depends(verify_token)):
    pool = await get_pool()
    channels = await pool.fetchrow(
        "SELECT COUNT(*) as total, "
        "COUNT(*) FILTER (WHERE status = 'active') as active, "
        "COUNT(*) FILTER (WHERE status = 'disabled') as disabled, "
        "COUNT(*) FILTER (WHERE status = 'archived') as archived "
        "FROM channels"
    )
    videos_today = await pool.fetchrow(
        "SELECT COUNT(*) as total, "
        "COUNT(*) FILTER (WHERE status IN ('delivered','test_delivered')) as delivered, "
        "COUNT(*) FILTER (WHERE status = 'failed') as failed, "
        "COUNT(*) FILTER (WHERE status NOT IN ('delivered','test_delivered','failed','stopped','superseded','rejected')) as in_progress, "
        "COALESCE(SUM(total_cost), 0) as total_cost "
        "FROM videos WHERE created_at::date = CURRENT_DATE"
    )
    budget_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'daily_budget_limit'"
    )
    emergency_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'emergency_stop'"
    )
    # Environment mode
    env_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'environment_mode'"
    )
    env_mode = env_row["config_value"] if env_row else "test"

    return R(status="ok", data={
        "channels": {
            "total": channels["total"],
            "active": channels["active"],
            "disabled": channels["disabled"],
            "archived": channels["archived"],
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
        "environment_mode": env_mode,
    })


# ── WebSocket: Global Event Broadcast (cross-tab sync) ────

class EventBroadcaster:
    """Manages global WebSocket connections for cross-tab sync."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, event: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)


_event_broadcaster = EventBroadcaster()


async def _broadcast_job_event(content_id: str, status: str, channel_id: str = "") -> None:
    """Fire-and-forget broadcast to all connected dashboards."""
    try:
        await _event_broadcaster.broadcast({
            "type": "job_update",
            "content_id": content_id,
            "status": status,
            "channel_id": channel_id,
        })
    except Exception:
        pass


@app.websocket("/api/ws/events")
async def ws_events(websocket: WebSocket):
    """Global event stream for cross-tab sync. No auth required (read-only)."""
    await _event_broadcaster.connect(websocket)
    try:
        while True:
            # Keep connection alive by waiting for client pings/messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _event_broadcaster.disconnect(websocket)


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
            if video and video["status"] in ("delivered", "test_delivered", "failed", "stopped", "superseded", "rejected"):
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
