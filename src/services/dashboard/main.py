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
import os
import secrets
import time
from datetime import datetime, timedelta

import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from temporalio.client import Client as TemporalClient

from src.config import settings
from src.db import get_pool
from src.environment import get_mode, set_db_mode_override, is_test
from src.schemas.common import VideoParams
from src.observability.metrics import instrument_app
from src.observability.sentry import init_sentry
from src.services.dashboard._limiter import limiter

# Initialize Sentry as early as possible. No-op when SENTRY_DSN is unset.
init_sentry("dashboard-bff")

logger = structlog.get_logger()


_minio_presign_client = None


def _get_minio_presign_client():
    """Cached MinIO client whose host matches the browser-reachable endpoint.

    Presigned URLs are signed against the host in the client config, so we must
    point it at the *public* host (e.g. ``localhost:9000``) — not the in-cluster
    ``minio:9000`` — for the signature to verify when the browser hits it.
    """
    global _minio_presign_client
    if _minio_presign_client is not None:
        return _minio_presign_client
    try:
        from minio import Minio  # type: ignore
        from urllib.parse import urlparse
    except Exception:
        return None

    public = settings.s3_public_base_url or settings.s3_endpoint
    parsed = urlparse(public if "://" in public else f"http://{public}")
    host = parsed.netloc or parsed.path
    secure = parsed.scheme == "https"
    _minio_presign_client = Minio(
        host,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        secure=secure,
    )
    return _minio_presign_client


def _extract_s3_key(video_url: str) -> str:
    """Strip scheme/host/bucket from a stored URL → returns the object key."""
    from urllib.parse import urlparse
    parsed = urlparse(video_url)
    path = parsed.path.lstrip("/")
    bucket = settings.s3_bucket
    if path.startswith(f"{bucket}/"):
        return path[len(bucket) + 1:]
    return path


def _public_url(video_url: str) -> str:
    """Convert an internal MinIO URL into a browser-reachable presigned URL.

    Uses the ``minio`` SDK (already a project dependency) to sign a 1-hour GET
    URL against the *public* MinIO host, so the browser can stream/download
    private objects without a public bucket policy.
    Falls back to plain host substitution if signing fails.
    """
    if not video_url:
        return ""
    # External URL (e.g. YouTube) → return as-is
    if "minio:9000" not in video_url and "://minio" not in video_url \
       and "localhost:9000" not in video_url:
        return video_url

    key = _extract_s3_key(video_url)
    client = _get_minio_presign_client()
    if client is not None:
        try:
            from datetime import timedelta as _td
            return client.presigned_get_object(
                settings.s3_bucket, key, expires=_td(hours=1)
            )
        except Exception as exc:
            logger.warning("dashboard.presign_failed", key=key, error=str(exc))

    # Fallback: best-effort host substitution (requires public bucket policy)
    if settings.s3_public_base_url:
        return f"{settings.s3_public_base_url.rstrip('/')}/{key}"
    return video_url.replace("minio:9000", "localhost:9000")


# Backwards-compat alias
_generate_download_url = _public_url


app = FastAPI(title="Dashboard BFF", version="1.0.0")
instrument_app(app, service_name="dashboard")

# Register all provider classes (openai, claude, gemini, fish-audio, …)
# at boot so the /providers/models endpoint and credential creation
# flow see the live registry instead of an empty one. Without this,
# the UI shows "PROVIDER NOT REGISTERED" badges and validation falls
# open. Lazy-imported in some endpoints, but doing it here removes
# the surprise.
import src.providers.boot  # noqa: E402, F401

# Rate limiter — uses client IP extracted by get_remote_address.
# In production behind Traefik, set X-Forwarded-For so the real
# client IP is used instead of the proxy IP.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount v2 router (Phase 0+ revamp). Strictly additive: every existing
# /api/... endpoint below keeps its contract.
#
# In non-prod we re-raise so import failures (missing deps, syntax errors,
# wrong port maps) fail the boot loudly — the previous silent ``warning``
# trap hid two real bugs in May 2026 and cost ~30 min of debugging each.
_v2_router_loaded = False
try:
    from src.services.dashboard.v2 import router as _v2_router
    app.include_router(_v2_router, prefix="/api/v2")
    _v2_router_loaded = True
except Exception as _exc:
    logger.warning("dashboard.v2_router_disabled", error=str(_exc))
    if os.getenv("ENVIRONMENT_MODE", "test").lower() != "production":
        raise

# CORS allowlist — never use wildcard with allow_credentials=True
# (browsers reject it and it's a real CSRF surface). Configure per-deploy
# via ALLOWED_ORIGINS="https://app.example.com,https://staging.example.com".
_allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ── Production secret guard ─────────────────────────────────
_INSECURE_SECRET_DEFAULTS: frozenset[str] = frozenset({
    "change_me_to_64_char_random_string_here_now",
    "dev-insecure-change-me",
    "admin",
    "minioadmin",
    "change_me_strong_random_64",
    "change_me_temporal_64",
    "",
})

_SECRET_ENV_KEYS: list[tuple[str, str]] = [
    ("ADMIN_JWT_SECRET",      "openssl rand -base64 48"),
    ("AUTH_JWT_SECRET",       "openssl rand -base64 48"),
    ("DB_PASSWORD",           "openssl rand -base64 32"),
    ("S3_ACCESS_KEY",         "openssl rand -hex 16"),
    ("S3_SECRET_KEY",         "openssl rand -base64 32"),
    ("GRAFANA_ADMIN_PASSWORD","openssl rand -base64 16"),
]


@app.on_event("startup")
async def _start_budget_gauge_refresh() -> None:
    from src.observability.budget_metrics import start_budget_gauge_refresh
    asyncio.create_task(start_budget_gauge_refresh(get_pool))


@app.on_event("startup")
async def _check_production_secrets() -> None:
    if os.getenv("ENVIRONMENT_MODE", "test").lower() != "production":
        return
    failures: list[str] = []
    for key, hint in _SECRET_ENV_KEYS:
        val = os.getenv(key, "")
        if val in _INSECURE_SECRET_DEFAULTS:
            failures.append(f"  {key}  (hint: {hint})")
    if failures:
        msg = (
            "FATAL: the following secrets are still set to insecure defaults "
            "while ENVIRONMENT_MODE=production. "
            "Rotate them before starting:\n" + "\n".join(failures)
        )
        logger.error("startup.insecure_secrets", keys=[k for k, _ in zip(_SECRET_ENV_KEYS, failures)])
        raise RuntimeError(msg)
    logger.info("startup.secrets_ok")


# ── Session store (in-memory, single user) ─────────────────
_sessions: dict[str, float] = {}  # token -> expiry_timestamp
SESSION_TTL_HOURS = 24


# ── Helpers ────────────────────────────────────────────────

_temporal_client_cache: TemporalClient | None = None
_temporal_client_lock = asyncio.Lock()


async def _get_temporal_client() -> TemporalClient:
    """Return a cached Temporal client. Reconnects on failure."""
    global _temporal_client_cache
    if _temporal_client_cache is not None:
        return _temporal_client_cache
    async with _temporal_client_lock:
        if _temporal_client_cache is None:
            _temporal_client_cache = await TemporalClient.connect(
                settings.temporal_host,
                namespace=getattr(settings, "temporal_namespace", "default"),
            )
    return _temporal_client_cache


async def _list_paused_workflows(timeout_s: float = 2.0) -> dict[str, bool]:
    """List paused state of all running VideoProductionWorkflow workflows.

    Bounded by ``timeout_s`` so a slow Temporal does not stall the dashboard.
    Returns an empty dict on any error or timeout.
    """
    async def _gather() -> dict[str, bool]:
        out: dict[str, bool] = {}
        client = await _get_temporal_client()
        query = 'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
        async for wf in client.list_workflows(query=query):
            try:
                handle = client.get_workflow_handle(wf.id)
                status = await handle.query("get_status")
                out[wf.id] = bool(status.get("paused", False))
            except Exception:
                out[wf.id] = False
        return out

    try:
        return await asyncio.wait_for(_gather(), timeout=timeout_s)
    except Exception:
        return {}


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
    # Phase 5 — niche-template wizard can seed a starter topics queue.
    # Stored as a comma-separated string in the legacy `topics_queue`
    # column (TEXT) to match the existing schema; downstream services
    # already split on commas.
    starter_topics: list[str] | None = None

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

async def _probe_db(timeout_s: float = 1.0) -> bool:
    try:
        pool = await asyncio.wait_for(get_pool(), timeout=timeout_s)
        async with pool.acquire() as conn:
            await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=timeout_s)
        return True
    except Exception:
        return False


async def _probe_redis(timeout_s: float = 1.0) -> bool:
    try:
        import redis.asyncio as _redis  # type: ignore
        client = _redis.from_url(settings.redis_url, socket_timeout=timeout_s)
        try:
            return bool(await asyncio.wait_for(client.ping(), timeout=timeout_s))
        finally:
            await client.aclose()
    except Exception:
        return False


async def _probe_temporal(timeout_s: float = 1.0) -> bool:
    try:
        client = await asyncio.wait_for(_get_temporal_client(), timeout=timeout_s)
        return client is not None
    except Exception:
        return False


async def _probe_minio(timeout_s: float = 1.0) -> bool:
    """Probe the in-cluster MinIO host (settings.s3_endpoint), not the
    browser-facing public host used for presigning. From inside the BFF
    container, the public host (e.g. localhost:9000) is unreachable."""
    try:
        from minio import Minio  # type: ignore
        from urllib.parse import urlparse
        parsed = urlparse(
            settings.s3_endpoint if "://" in settings.s3_endpoint
            else f"http://{settings.s3_endpoint}"
        )
        client = Minio(
            parsed.netloc or parsed.path,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=parsed.scheme == "https",
        )
        return await asyncio.wait_for(
            asyncio.to_thread(client.bucket_exists, settings.s3_bucket),
            timeout=timeout_s,
        )
    except Exception:
        return False


@app.get("/health")
async def health():
    """Rich health probe: components individually checked, never raises.

    Used by load balancer + Alertmanager + the dashboard fleet panel.
    """
    db, redis_ok, temporal, minio = await asyncio.gather(
        _probe_db(), _probe_redis(), _probe_temporal(), _probe_minio(),
        return_exceptions=False,
    )
    components = {
        "db": bool(db),
        "redis": bool(redis_ok),
        "temporal": bool(temporal),
        "minio": bool(minio),
        "v2_router_loaded": _v2_router_loaded,
    }
    ok = all(components.values())
    return {
        "status": "healthy" if ok else "degraded",
        "service": "dashboard-bff",
        "version": app.version,
        "git_sha": os.getenv("GIT_SHA", "unknown"),
        "environment": os.getenv("ENVIRONMENT_MODE", "test"),
        "components": components,
    }


# ── Auth ───────────────────────────────────────────────────

@app.post("/api/auth/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest):
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

@app.get("/api/channels", deprecated=True)
async def list_channels(
    include_archived: bool = Query(default=False),
    _: str = Depends(verify_token),
):
    from src.environment import get_mode_from_db as _get_env
    pool = await get_pool()
    env_mode = await _get_env()
    conditions = [f"environment = '{env_mode}'"]
    if not include_archived:
        conditions.append("status != 'archived'")
    status_filter = "WHERE " + " AND ".join(conditions)
    rows = await pool.fetch(
        f"SELECT channel_id, channel_name, niche, sub_niche, content_mode, "
        f"auto_upload, status, videos_per_week_long, videos_per_week_short, "
        f"short_form_duration, long_form_duration, schedule_config, "
        f"human_review_required, max_daily_api_spend, environment, "
        f"created_at FROM channels {status_filter} ORDER BY channel_id"
    )
    # Batch-query Temporal for paused state — bounded so a slow Temporal
    # cluster cannot stall the channels list endpoint.
    _paused_wf_map = await _list_paused_workflows(timeout_s=2.0)

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


@app.post("/api/channels", deprecated=True)
async def create_channel(req: ChannelCreateRequest, _: str = Depends(verify_token)):
    pool = await get_pool()
    # Comma-join starter topics into the legacy topics_queue TEXT column.
    # Empty string when no starter topics — matches the existing
    # "no preset chosen" case so downstream code paths don't change.
    topics_queue = ",".join(t.strip() for t in (req.starter_topics or []) if t and t.strip())
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
            "primary_color, forbidden_words, topics_queue) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13, "
            "$14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26)",
            req.channel_id, req.channel_name, req.niche, req.sub_niche,
            req.content_mode, req.auto_upload, req.videos_per_week_short,
            req.videos_per_week_long, req.short_form_duration, req.long_form_duration,
            sched_json, req.human_review_required, req.max_daily_api_spend,
            req.belief_territory, req.intellectual_lens, req.topic_domain,
            req.brand_voice, req.narrative_rhythm, req.emotional_contract, req.target_audience,
            req.primary_format_long, req.primary_format_short, req.thumbnail_style,
            req.primary_color, req.forbidden_words, topics_queue,
        )
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(status_code=409, detail="Channel already exists")
        raise HTTPException(status_code=500, detail=str(exc))
    return R(status="ok", data={"channel_id": req.channel_id})


@app.post("/api/channels/generate-brand-dna", deprecated=True)
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


# ── Phase 5 — Niche templates & self-learning insights ───────


@app.get("/api/niche-templates", deprecated=True)
async def list_niche_templates(_: str = Depends(verify_token)):
    """Starter presets for the channel-creation wizard.

    Returns a static list (no DB hit) so the wizard can render instantly.
    Templates are defined in ``src/intelligence/niche_templates.json`` and
    can be edited without code changes.
    """
    from src.intelligence import list_templates
    return R(status="ok", data={"templates": list_templates()})


@app.get("/api/channels/{channel_id}/learning-insights", deprecated=True)
async def channel_learning_insights(channel_id: str, _: str = Depends(verify_token)):
    """Surface what the self-learning system has actually learned for one channel.

    Aggregates four signals so operators can audit the loop:

    * Performance memory (the same prompt context the LLMs see)
    * Bandit state — which hook style / pacing strategy is currently winning
    * Drift — has the script-success model degraded since last train?
    * Tier distribution — how many S/A/B/C/D videos in the last 30 days?
    """
    from src.intelligence import build_performance_context

    pool = await get_pool()

    # 1. Performance memory text — same string the LLMs receive.
    perf_text = await build_performance_context(channel_id)

    # 2. Bandit state — which arms are winning?
    try:
        niche_row = await pool.fetchrow(
            "SELECT niche FROM channels WHERE channel_id = $1", channel_id,
        )
        niche = niche_row["niche"] if niche_row else None
        bandits: list[dict] = []
        if niche:
            rows = await pool.fetch(
                "SELECT bandit_type, arm_name, alpha, beta, pulls, rewards "
                "FROM script_bandit_state WHERE niche = $1 "
                "ORDER BY bandit_type, (rewards / NULLIF(pulls, 0)) DESC NULLS LAST",
                niche,
            )
            for r in rows:
                pulls = r["pulls"] or 0
                rewards = float(r["rewards"] or 0)
                bandits.append({
                    "type": r["bandit_type"],
                    "arm": r["arm_name"],
                    "pulls": pulls,
                    "win_rate": round(rewards / pulls, 3) if pulls else None,
                    "alpha": float(r["alpha"] or 0),
                    "beta":  float(r["beta"] or 0),
                })
    except Exception as exc:
        logger.warning("learning_insights.bandit_failed", error=str(exc))
        bandits = []

    # 3. Drift status — best-effort; the table may not exist on fresh installs.
    try:
        drift_row = await pool.fetchrow(
            "SELECT model_name, last_trained_at, last_auc, current_auc, "
            "       needs_retrain, sample_count "
            "FROM ml_model_state WHERE channel_id = $1 "
            "ORDER BY last_trained_at DESC NULLS LAST LIMIT 1",
            channel_id,
        )
        drift = dict(drift_row) if drift_row else None
        if drift and drift.get("last_trained_at"):
            drift["last_trained_at"] = drift["last_trained_at"].isoformat()
    except Exception:
        drift = None

    # 4. Tier distribution over the last 30 days.
    tiers: dict[str, int] = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
    try:
        rows = await pool.fetch(
            "SELECT performance_tier, COUNT(*) AS n FROM feedback_loop "
            "WHERE channel_id = $1 AND updated_at > NOW() - INTERVAL '30 days' "
            "  AND performance_tier IS NOT NULL "
            "GROUP BY performance_tier",
            channel_id,
        )
        for r in rows:
            tiers[r["performance_tier"]] = int(r["n"])
    except Exception as exc:
        logger.warning("learning_insights.tier_failed", error=str(exc))

    return R(status="ok", data={
        "channel_id": channel_id,
        "performance_memory": perf_text,            # Plain text, ready for display.
        "performance_memory_attached": bool(perf_text),
        "bandits": bandits,
        "drift": drift,
        "tier_distribution_30d": tiers,
    })


@app.put("/api/channels/{channel_id}", deprecated=True)
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


@app.put("/api/channels/{channel_id}/enable", deprecated=True)
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


@app.put("/api/channels/{channel_id}/disable", deprecated=True)
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


@app.put("/api/channels/{channel_id}/archive", deprecated=True)
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


@app.put("/api/channels/{channel_id}/restore", deprecated=True)
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


@app.post("/api/channels/{channel_id}/clone", deprecated=True)
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
            "competitor_channels, forbidden_words, status, environment) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, "
            "$14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, "
            "$28, $29, $30, $31, $32, $33, 'disabled', $34)",
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
            ch.get("environment", "test"),  # $34 — inherit source channel's environment
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Clone failed: {exc}")
    logger.info("channel.cloned", source=channel_id, new_id=new_id)
    return R(status="ok", data={"source_channel_id": channel_id, "new_channel_id": new_id})


@app.get("/api/channels/{channel_id}/export", deprecated=True)
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

@app.post("/api/channels/{channel_id}/trigger", deprecated=True)
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


@app.post("/api/channels/{channel_id}/pause", deprecated=True)
async def pause_production(channel_id: str, _: str = Depends(verify_token)):
    """Send pause signal to all running workflows for a channel."""
    paused = await _signal_running_workflows(channel_id, "pause_workflow", None)
    return R(status="ok", data={"channel_id": channel_id, "paused_workflows": paused})


@app.post("/api/channels/{channel_id}/resume", deprecated=True)
async def resume_production(channel_id: str, _: str = Depends(verify_token)):
    """Send resume signal to all running workflows for a channel."""
    resumed = await _signal_running_workflows(channel_id, "resume_workflow", None)
    return R(status="ok", data={"channel_id": channel_id, "resumed_workflows": resumed})


@app.post("/api/channels/{channel_id}/stop", deprecated=True)
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

@app.get("/api/channels/{channel_id}/jobs", deprecated=True)
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


@app.get("/api/jobs/{content_id}/progress", deprecated=True)
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


@app.get("/api/jobs/{content_id}/metadata", deprecated=True)
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

    # Resolve category_id to name
    CATEGORY_NAMES = {
        "22": "People & Blogs", "26": "How-to & Style", "27": "Education",
        "28": "Science & Technology", "24": "Entertainment", "20": "Gaming",
        "10": "Music", "17": "Sports", "25": "News & Politics",
    }
    cat_id = delivery.get("category_id", "")
    category = delivery.get("category", "") or CATEGORY_NAMES.get(cat_id, cat_id)

    return R(status="ok", data={
        "content_id": content_id,
        "content_mode": row["content_mode"],
        "title": row["title"] or delivery.get("title", ""),
        "description": delivery.get("description", ""),
        "tags": delivery.get("tags", []),
        "seo_score": delivery.get("seo_score"),
        "hashtags": delivery.get("hashtags", []),
        "category": category,
        "privacy_status": delivery.get("privacy_status", "private"),
        "thumbnails": thumbnails,
        "seo_factors": delivery.get("seo_factors", []),
        "description_score": delivery.get("description_score"),
        "final_composite_score": delivery.get("final_composite_score"),
    })


@app.get("/api/jobs/{content_id}/output", deprecated=True)
async def job_output(content_id: str, _: str = Depends(verify_token)):
    """Get final video output: video URL, thumbnail, download link.

    The ``video_url``/``download_url`` point at the in-cluster proxy endpoint
    ``/api/jobs/{id}/video`` so the browser can stream/download the file
    regardless of MinIO bucket policy or external reachability.

    NOTE: a previous version of this payload exposed ``video_url_direct``
    (raw MinIO URL). That URL hosts ``minio:9000`` which is internal-only;
    clicking it returned an XML AccessDenied page that browsers rendered
    as text — the cause of the "download = page source" bug. Use the proxy
    for both inline playback and download; clients that need a short-lived
    signed URL can call ``GET /api/jobs/{id}/presigned`` explicitly.
    """
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
    raw_url = row["rendered_video_url"]
    proxy_url = f"/api/jobs/{content_id}/video" if raw_url else ""

    return R(status="ok", data={
        "content_id": content_id,
        "title": row["title"],
        "status": row["status"],
        "video_url": proxy_url,
        "download_url": proxy_url,
        "thumbnails": thumbnails,
        "youtube_video_id": row["youtube_video_id"],
        "youtube_url": f"https://youtu.be/{row['youtube_video_id']}" if row["youtube_video_id"] else None,
        "total_cost": float(row["total_cost"]) if row["total_cost"] else 0,
    })


@app.get("/api/jobs/{content_id}/video", deprecated=True)
async def stream_video(content_id: str, request: Request):
    """Stream the rendered video for a job, proxying MinIO with Range support.

    No auth header is required (browsers don't send custom headers on
    ``<video src>``). The endpoint is gated by knowing the ``content_id``,
    which is opaque to outsiders. Range requests are forwarded so the HTML5
    ``<video>`` element can seek/scrub.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT rendered_video_url, title FROM videos WHERE content_id = $1",
        content_id,
    )
    if not row or not row["rendered_video_url"]:
        raise HTTPException(status_code=404, detail="Video not available")

    key = _extract_s3_key(row["rendered_video_url"])
    safe_title = (row["title"] or content_id).replace('"', "").replace("\n", " ")[:80]

    # Forward Range header so seeking works in the browser.
    fwd_headers: dict[str, str] = {}
    rng = request.headers.get("range") or request.headers.get("Range")
    if rng:
        fwd_headers["Range"] = rng

    upstream_url = f"{settings.s3_endpoint.rstrip('/')}/{settings.s3_bucket}/{key}"

    # Sign the upstream request via boto3-style signing? Simpler: MinIO with
    # the default minioadmin creds requires auth for private objects. Use the
    # already-cached presign client to build a short-lived signed URL we can
    # GET in-cluster. We request *non-public* signing here intentionally.
    try:
        from minio import Minio  # type: ignore
        from datetime import timedelta as _td
        # In-cluster client signs against the internal host, which is what we
        # actually fetch — keeps the host:signature pair consistent.
        from urllib.parse import urlparse as _urlparse
        ep = settings.s3_endpoint
        ep_parsed = _urlparse(ep if "://" in ep else f"http://{ep}")
        in_client = Minio(
            ep_parsed.netloc or ep_parsed.path,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=ep_parsed.scheme == "https",
        )
        upstream_url = in_client.presigned_get_object(
            settings.s3_bucket, key, expires=_td(minutes=10)
        )
    except Exception as exc:
        logger.warning("dashboard.video_proxy_presign_failed",
                       content_id=content_id, error=str(exc))

    import httpx as _httpx

    # HEAD to capture status + length/range headers without downloading body.
    async with _httpx.AsyncClient(timeout=10.0) as probe:
        try:
            head = await probe.request("HEAD", upstream_url, headers=fwd_headers)
        except Exception as exc:
            logger.warning("dashboard.video_proxy_head_failed",
                           content_id=content_id, error=str(exc))
            raise HTTPException(status_code=502, detail="Storage unreachable")

    if head.status_code >= 400:
        raise HTTPException(status_code=head.status_code,
                            detail="Upstream storage error")

    status_code = 206 if head.status_code == 206 else 200
    out_headers: dict[str, str] = {
        "Content-Type": head.headers.get("content-type", "video/mp4"),
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=60",
        "Content-Disposition": f'inline; filename="{safe_title}.mp4"',
    }
    for h in ("content-length", "content-range", "etag", "last-modified"):
        if h in head.headers:
            out_headers[h.title()] = head.headers[h]

    async def _iter():
        async with _httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", upstream_url, headers=fwd_headers) as resp:
                if resp.status_code >= 400:
                    return
                async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                    yield chunk

    return StreamingResponse(_iter(), status_code=status_code, headers=out_headers)


@app.get("/api/jobs/{content_id}/presigned", deprecated=True)
async def job_presigned(content_id: str, _: str = Depends(verify_token)):
    """Return a short-lived (10-minute) presigned MinIO URL for power-users
    who explicitly need a direct link (e.g. external download tools that
    don't go through the proxy). Authenticated only — never embedded in the
    default UI payload to avoid the broken-direct-link footgun.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT rendered_video_url FROM videos WHERE content_id = $1",
        content_id,
    )
    if not row or not row["rendered_video_url"]:
        raise HTTPException(status_code=404, detail="Video not available")
    url = _public_url(row["rendered_video_url"])
    if not url:
        raise HTTPException(status_code=502, detail="Could not generate presigned URL")
    return R(status="ok", data={"presigned_url": url, "expires_in_seconds": 600})


# ── Job Approval / Rejection ──────────────────────────────

@app.post("/api/jobs/{content_id}/approve", deprecated=True)
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


@app.post("/api/jobs/{content_id}/reject", deprecated=True)
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


@app.post("/api/jobs/{content_id}/retry", deprecated=True)
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


@app.post("/api/jobs/{content_id}/restart", deprecated=True)
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


@app.post("/api/jobs/{content_id}/pause", deprecated=True)
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


@app.post("/api/jobs/{content_id}/resume", deprecated=True)
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


@app.post("/api/jobs/{content_id}/stop", deprecated=True)
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

@app.get("/api/jobs/active", deprecated=True)
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

    # Batch-query Temporal for paused state — bounded by timeout so a slow
    # Temporal cluster cannot stall the Progress page.
    paused_workflows = await _list_paused_workflows(timeout_s=2.0)

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

@app.get("/api/channels/{channel_id}/workflow-status", deprecated=True)
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
        async def _probe() -> bool:
            client = await _get_temporal_client()
            query = 'WorkflowType = "VideoProductionWorkflow" AND ExecutionStatus = "Running"'
            async for wf in client.list_workflows(query=query):
                if channel_id in wf.id:
                    handle = client.get_workflow_handle(wf.id)
                    status = await handle.query("get_status")
                    return bool(status.get("paused", False))
            return False
        try:
            is_paused = await asyncio.wait_for(_probe(), timeout=2.0)
        except Exception:
            is_paused = False
    return R(status="ok", data={
        "has_running": active is not None,
        "is_paused": is_paused,
        "active_content_id": active["content_id"] if active else None,
        "active_status": active["status"] if active else None,
    })


# ── System Config ──────────────────────────────────────────

@app.get("/api/config", deprecated=True)
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


@app.put("/api/config", deprecated=True)
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


@app.post("/api/emergency-stop", deprecated=True)
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


@app.post("/api/emergency-resume", deprecated=True)
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


@app.get("/api/environment", deprecated=True)
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


@app.put("/api/environment", deprecated=True)
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


@app.get("/api/test-data/stats", deprecated=True)
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


@app.delete("/api/test-data", deprecated=True)
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


@app.post("/api/admin/clean-slate", deprecated=True)
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


# ── Phase 6 — Fleet health ─────────────────────────────────


# Service hosts — kept here (not in config) because the dashboard BFF is
# already the only place that needs the full topology. Each entry maps a
# friendly name to its in-cluster /health URL.
# Ports must match docker-compose.yml. Prometheus has the same map in
# observability/prometheus.yml — keep the two in sync. ``music`` is NOT a
# real service (functionality lives inside ``assets``), so it is omitted.
_FLEET_SERVICES: dict[str, str] = {
    "research":   "http://research:8001/health",
    "script":     "http://script:8002/health",
    "voice":      "http://voice:8003/health",
    "assets":     "http://assets:8004/health",
    "thumbnail":  "http://thumbnail:8005/health",
    "assembly":   "http://assembly:8006/health",
    "delivery":   "http://delivery:8007/health",
    "analytics":  "http://analytics:8008/health",
    "admin":      "http://admin:8009/health",
    "direction":  "http://direction:8010/health",
    "brand":      "http://brand:8012/health",
    "editor":     "http://editor:8013/health",
}


async def _probe_service(name: str, url: str, timeout_s: float) -> dict:
    """One-shot health probe. Never raises; classifies the failure."""
    import httpx as _httpx
    import time as _time
    start = _time.monotonic()
    try:
        async with _httpx.AsyncClient(timeout=timeout_s) as cli:
            r = await cli.get(url)
        latency_ms = int((_time.monotonic() - start) * 1000)
        return {
            "name": name,
            "ok": r.status_code == 200,
            "status_code": r.status_code,
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "status_code": 0,
            "error": type(exc).__name__,
            "latency_ms": int((_time.monotonic() - start) * 1000),
        }


@app.get("/api/fleet-health", deprecated=True)
async def fleet_health(_: str = Depends(verify_token)):
    """Aggregate live health across the fleet.

    Goals:
    * One request → full picture for the ops dashboard.
    * Per-service probe is bounded (3s each) and parallel, so a single
      slow service can't push total latency above ~3.5s.
    * Failure-tolerant: if any subsystem is unreachable, its block is
      replaced with an error marker; the rest of the response is intact.
    """
    import asyncio as _asyncio
    import httpx as _httpx
    from src.db import get_pool_stats

    # 1. Fan-out service probes in parallel, bounded per-call timeout.
    probes = await _asyncio.gather(*[
        _probe_service(name, url, timeout_s=3.0)
        for name, url in _FLEET_SERVICES.items()
    ])
    services_ok = sum(1 for p in probes if p["ok"])
    services_total = len(probes)

    # 2. DB pool snapshot — local to this process; useful as a sanity gauge.
    db_stats = get_pool_stats()
    pool_pressure = (
        round(db_stats["size"] / db_stats["max_size"], 2)
        if db_stats.get("max_size") else None
    )

    # 3. Remotion queue (single source of truth for render capacity).
    remotion: dict
    try:
        async with _httpx.AsyncClient(timeout=3.0) as cli:
            r = await cli.get(f"{settings.remotion_base_url}/api/health")
        if r.status_code == 200:
            d = r.json()
            remotion = {
                "ok": True,
                "active":   d.get("activeRenders", 0),
                "waiting":  d.get("waiting", 0),
                "max":      d.get("maxConcurrent", 0),
                "memory_mb": int((d.get("memoryUsage", {}).get("rss", 0)) / 1_048_576),
            }
        else:
            remotion = {"ok": False, "status_code": r.status_code}
    except Exception as exc:
        remotion = {"ok": False, "error": type(exc).__name__}

    # 4. Recent quality-gate blocks + LLM router-budget exhaustions —
    #    stored in our own DB as audit rows, so a quick count is enough
    #    to show "system pushing back" pressure on the dashboard.
    pool = await get_pool()
    try:
        gate_blocks_24h = await pool.fetchval(
            "SELECT COUNT(*) FROM quality_gate_decisions "
            "WHERE decision = 'block' AND created_at > NOW() - INTERVAL '24 hours'"
        )
    except Exception:
        gate_blocks_24h = None
    try:
        recent_failures = await pool.fetchval(
            "SELECT COUNT(*) FROM videos "
            "WHERE status = 'failed' AND updated_at > NOW() - INTERVAL '24 hours'"
        )
    except Exception:
        recent_failures = None

    # 6. Phase 8 — niche-pulse freshness. How recently has the
    #    saturation scorer's input been refreshed, across how many niches.
    pulse: dict
    try:
        from src.services.research.saturation import get_pulse_freshness
        pulse_data = await get_pulse_freshness()
        pulse = {"ok": True, **pulse_data}
    except Exception as exc:
        pulse = {"ok": False, "error": type(exc).__name__}

    # 8. Phase 10 — diversity-floor activity. Surface how many forced
    #    explorations the floor has triggered in the last 7 days and
    #    the lowest current per-channel entropy across active bandits.
    #    Persistent low entropy without any forces means the bandits
    #    are exploring naturally; persistent high force-rate means
    #    we're fighting collapse — both are operator-relevant.
    diversity_health: dict
    try:
        forced_row = await pool.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE picked_at > NOW() - INTERVAL '7 days')::int
                                                                       AS picks_7d,
                COUNT(*) FILTER (WHERE picked_at > NOW() - INTERVAL '7 days'
                                   AND forced_exploration)::int        AS forced_7d
            FROM bandit_picks
            """
        )
        picks_7d = int(forced_row["picks_7d"] or 0)
        forced_7d = int(forced_row["forced_7d"] or 0)
        force_rate = round(forced_7d / picks_7d, 3) if picks_7d else None
        diversity_health = {
            "ok":          True,
            "picks_7d":    picks_7d,
            "forced_7d":   forced_7d,
            "force_rate":  force_rate,
        }
    except Exception as exc:
        diversity_health = {"ok": False, "error": type(exc).__name__}

    # 9. Phase 11 — prediction calibration health. Brier score and
    #    Expected Calibration Error over the last 30 days of scored
    #    predictions. Brier ~0.21 is the random-baseline floor for a
    #    balanced binary problem; lower is better. ECE > 0.15 means
    #    the model's confidence is meaningfully miscalibrated.
    calibration_health: dict
    try:
        from src.intelligence.prediction_calibration import get_calibration_metrics
        cal_metrics = await get_calibration_metrics(model_kind="topic_success")
        calibration_health = {"ok": True, **cal_metrics}
        # Surface how aggressively the loop is steering training too.
        # The mean_sample_weight on the latest active model is the
        # most direct read on "is the calibration loop actually doing
        # anything yet."
        try:
            ml_row = await pool.fetchrow(
                """
                SELECT metrics FROM ml_models
                WHERE model_name = 'topic_success_predictor' AND is_active = TRUE
                ORDER BY created_at DESC NULLS LAST, model_version DESC
                LIMIT 1
                """
            )
            if ml_row and ml_row["metrics"]:
                import json as _json
                m = ml_row["metrics"]
                m = _json.loads(m) if isinstance(m, str) else m
                calibration_health["weighted_fraction"] = m.get("weighted_fraction")
                calibration_health["mean_sample_weight"] = m.get("mean_sample_weight")
        except Exception:
            pass
    except Exception as exc:
        calibration_health = {"ok": False, "error": type(exc).__name__}

    # 7. Phase 9 — retention-curve coverage. Of delivered videos in
    #    the curve-stable window (7-30 days old), what fraction have
    #    a fetched curve? Low coverage means the calibrator is mostly
    #    falling back to tier labels — surfacing this lets the
    #    operator notice when the daily fetch workflow is wedged.
    retention_cov: dict
    try:
        cov_row = await pool.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE v.status = 'delivered'
                      AND v.youtube_video_id IS NOT NULL
                      AND v.created_at <  NOW() - INTERVAL '7 days'
                      AND v.created_at >= NOW() - INTERVAL '30 days'
                )::int                                            AS eligible,
                COUNT(*) FILTER (
                    WHERE v.status = 'delivered'
                      AND v.youtube_video_id IS NOT NULL
                      AND v.created_at <  NOW() - INTERVAL '7 days'
                      AND v.created_at >= NOW() - INTERVAL '30 days'
                      AND rc.video_id IS NOT NULL
                )::int                                            AS with_curve,
                MAX(rc.fetched_at)                                AS last_fetch
            FROM videos v
            LEFT JOIN retention_curves rc ON rc.video_id = v.content_id
            """
        )
        eligible = int(cov_row["eligible"] or 0)
        with_curve = int(cov_row["with_curve"] or 0)
        retention_cov = {
            "ok":         True,
            "eligible":   eligible,
            "with_curve": with_curve,
            "coverage":   round(with_curve / eligible, 3) if eligible else None,
            "last_fetch": cov_row["last_fetch"].isoformat() if cov_row["last_fetch"] else None,
        }
    except Exception as exc:
        retention_cov = {"ok": False, "error": type(exc).__name__}

    # 5. Phase 7 — gate calibration status. Aggregate counts are enough
    #    for the dashboard pill; per-niche detail lives in a separate
    #    endpoint for the gate-thresholds drawer.
    gate_calib: dict
    try:
        row = await pool.fetchrow(
            """
            SELECT COUNT(DISTINCT niche)                                   AS niches_calibrated,
                   COUNT(*) FILTER (WHERE source = 'auto')                 AS dims_auto,
                   COUNT(*) FILTER (WHERE source = 'default')              AS dims_default,
                   MAX(last_calibrated_at)                                 AS last_run
            FROM gate_thresholds
            """
        )
        gate_calib = {
            "ok": True,
            "niches_calibrated": int(row["niches_calibrated"] or 0),
            "dims_auto":         int(row["dims_auto"] or 0),
            "dims_default":      int(row["dims_default"] or 0),
            "last_run":          row["last_run"].isoformat() if row["last_run"] else None,
        }
    except Exception as exc:
        # Table may not exist on a fresh install yet — that's fine,
        # surface a clear "not yet" rather than a hard error.
        gate_calib = {"ok": False, "error": type(exc).__name__}

    # Overall status — green if every probe and Remotion succeeded.
    overall_ok = (services_ok == services_total) and remotion.get("ok") is True

    payload: dict = {
        "overall_ok": overall_ok,
        "services": {
            "ok_count": services_ok,
            "total":    services_total,
            "probes":   probes,
        },
        "db_pool": {
            "size":     db_stats.get("size"),
            "idle":     db_stats.get("idle"),
            "min_size": db_stats.get("min_size"),
            "max_size": db_stats.get("max_size"),
            "pressure": pool_pressure,        # 0..1, where 1 == saturated
        },
        "remotion": remotion,
        "scale_config": {
            "temporal_production_max_activities": settings.temporal_production_max_activities,
            "temporal_scheduler_max_activities":  settings.temporal_scheduler_max_activities,
            "db_statement_timeout_ms":            settings.db_statement_timeout_ms,
        },
        "pressure_24h": {
            "quality_gate_blocks": gate_blocks_24h,
            "video_failures":      recent_failures,
        },
        "gate_calibration":   gate_calib,
        "niche_pulse":        pulse,
        "retention_coverage": retention_cov,
        "diversity_floor":    diversity_health,
        "calibration":        calibration_health,
    }

    # Phase 12 — collapse the 8 subsystem cards into one weighted
    # health score with traffic-light band + per-subsystem breakdown.
    # Pure-function aggregation off the existing payload; no new I/O.
    try:
        from src.intelligence.system_health import aggregate_health
        payload["health"] = aggregate_health(payload)
    except Exception as exc:
        payload["health"] = {"score": None, "band": "unknown",
                             "error": type(exc).__name__}

    return R(status="ok", data=payload)


# ── Dashboard Stats ────────────────────────────────────────

@app.get("/api/stats", deprecated=True)
async def dashboard_stats(_: str = Depends(verify_token)):
    from src.environment import get_mode_from_db as _get_env
    pool = await get_pool()
    _env = await _get_env()
    channels = await pool.fetchrow(
        "SELECT COUNT(*) as total, "
        "COUNT(*) FILTER (WHERE status = 'active') as active, "
        "COUNT(*) FILTER (WHERE status = 'disabled') as disabled, "
        "COUNT(*) FILTER (WHERE status = 'archived') as archived "
        f"FROM channels WHERE environment = '{_env}'"
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
