from __future__ import annotations

import hashlib
import json as _json
import os
import secrets
from datetime import date

import structlog
from temporalio import activity

from core.db import get_pool
from core.redis_client import get_redis

logger = structlog.get_logger()

# Tier 2 tunables
_LOCK_TTL_S = int(os.getenv("CHANNEL_LOCK_TTL_S", "3600"))
_CHECKPOINT_MAX_BYTES = int(os.getenv("CHECKPOINT_MAX_BYTES", str(1_048_576)))  # 1 MB
_EVENT_STREAM_MAXLEN = int(os.getenv("JOB_EVENT_STREAM_MAXLEN", "10000"))
_EVENT_DEDUP_TTL_S = int(os.getenv("JOB_EVENT_DEDUP_TTL_S", "3600"))
_DUAL_WRITE_LEGACY_EVENTS = os.getenv("JOB_EVENT_DUAL_WRITE_LEGACY", "true").lower() == "true"


def _event_stream_key(content_id: str) -> str:
    return f"stream:jobs:{content_id}"


def _event_dedup_key(content_id: str, phase: str, status: str, detail_hash: str) -> str:
    return f"dedup:jobevent:{content_id}:{phase}:{status}:{detail_hash}"


@activity.defn
async def update_video_status(
    content_id: str,
    status: str,
    channel_id: str = "",
    title: str = "",
    content_mode: str = "",
) -> None:
    """Update the status column for a video in PostgreSQL.

    Also saves the current phase as checkpoint so that stopped jobs
    can be resumed from the last active phase.
    """
    logger.info(
        "activity.update_status",
        content_id=content_id,
        status=status,
        channel_id=channel_id or "N/A",
    )
    try:
        env = "production"
        pool = await get_pool()

        terminal_statuses = {
            "delivered",
            "test_delivered",
            "failed",
            "stopped",
            "superseded",
            "rejected",
        }
        is_active_phase = status not in terminal_statuses

        if is_active_phase:
            prev = await pool.fetchrow("SELECT status FROM videos WHERE content_id = $1", content_id)
            if prev and prev["status"] in ("failed", "stopped"):
                await pool.execute("DELETE FROM job_events WHERE content_id = $1", content_id)
            await pool.execute(
                "INSERT INTO videos (content_id, channel_id, status, title, content_mode, environment, checkpoint, updated_at) "
                "VALUES ($1, NULLIF($2,''), $3, NULLIF($4,''), NULLIF($5,''), $6, $3, NOW()) "
                "ON CONFLICT (content_id) DO UPDATE SET "
                "status = $3, "
                "checkpoint = $3, "
                "channel_id = COALESCE(NULLIF($2,''), videos.channel_id), "
                "title = COALESCE(NULLIF($4,''), videos.title), "
                "content_mode = COALESCE(NULLIF($5,''), videos.content_mode), "
                "updated_at = NOW()",
                content_id,
                channel_id,
                status,
                title,
                content_mode,
                env,
            )
            if channel_id and content_mode and status == "researching":
                await pool.execute(
                    "UPDATE videos SET status = 'superseded', updated_at = NOW() "
                    "WHERE channel_id = $1 AND content_mode = $2 "
                    "AND content_id != $3 "
                    "AND status IN ('failed', 'stopped')",
                    channel_id,
                    content_mode,
                    content_id,
                )
        else:
            await pool.execute(
                "INSERT INTO videos (content_id, channel_id, status, title, content_mode, environment, updated_at) "
                "VALUES ($1, NULLIF($2,''), $3, NULLIF($4,''), NULLIF($5,''), $6, NOW()) "
                "ON CONFLICT (content_id) DO UPDATE SET "
                "status = $3, "
                "channel_id = COALESCE(NULLIF($2,''), videos.channel_id), "
                "title = COALESCE(NULLIF($4,''), videos.title), "
                "content_mode = COALESCE(NULLIF($5,''), videos.content_mode), "
                "updated_at = NOW()",
                content_id,
                channel_id,
                status,
                title,
                content_mode,
                env,
            )
            if status in ("failed", "stopped"):
                row = await pool.fetchrow(
                    "SELECT channel_id, content_mode FROM videos WHERE content_id = $1",
                    content_id,
                )
                ch = (row and row["channel_id"]) or channel_id
                cm = (row and row["content_mode"]) or content_mode
                if ch and cm:
                    await pool.execute(
                        "UPDATE videos SET status = 'superseded', updated_at = NOW() "
                        "WHERE channel_id = $1 AND content_mode = $2 "
                        "AND content_id != $3 "
                        "AND status IN ('failed', 'stopped')",
                        ch,
                        cm,
                        content_id,
                    )
    except Exception as exc:
        logger.warning("activity.update_status.failed", error=str(exc))


@activity.defn
async def release_channel_lock(channel_id: str, fencing_token: str = "") -> None:
    """Release the Redis lock for a channel.

    Uses a fencing-token check-and-delete (Lua) so a stale worker whose
    lock has already expired and been re-acquired by someone else can't
    release the new holder's lock.
    """
    logger.info("activity.release_lock", channel_id=channel_id)
    try:
        r = await get_redis()
        key = f"lock:channel:{channel_id}"
        if fencing_token:
            # Only delete if the value still matches our token
            lua = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
            await r.eval(lua, 1, key, fencing_token)
        else:
            # Legacy path (no token) — best effort
            await r.delete(key)
    except Exception as exc:
        logger.warning("activity.release_lock.failed", error=str(exc))


@activity.defn
async def refresh_channel_lock(channel_id: str, fencing_token: str, ttl_s: int = 0) -> bool:
    """Extend the TTL on a held channel lock (heartbeat for long activities)."""
    ttl = ttl_s or _LOCK_TTL_S
    try:
        r = await get_redis()
        key = f"lock:channel:{channel_id}"
        lua = (
            "if redis.call('get', KEYS[1]) == ARGV[1] "
            "then return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end"
        )
        result = await r.eval(lua, 1, key, fencing_token, ttl)
        return bool(result)
    except Exception as exc:
        logger.warning("activity.refresh_lock.failed", error=str(exc))
        return False


@activity.defn
async def check_system_status() -> dict:
    """Read system_config and compute budget status."""
    logger.info("activity.check_system_status")
    try:
        pool = await get_pool()

        active_row = await pool.fetchrow("SELECT config_value FROM system_config WHERE config_key = 'system_active'")
        emergency_row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = 'emergency_stop'"
        )
        budget_row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = 'daily_budget_limit'"
        )

        is_active = active_row and active_row["config_value"] == "true"
        emergency = emergency_row and emergency_row["config_value"] == "true"
        daily_limit = float(budget_row["config_value"]) if budget_row else 50.0

        videos_today = await pool.fetchval(
            "SELECT COUNT(*) FROM videos WHERE created_at::date = $1 AND status NOT IN ('failed','superseded')",
            date.today(),
        )

        spent_row = await pool.fetchrow(
            "SELECT COALESCE(SUM(total_cost), 0) as spent FROM videos "
            "WHERE created_at::date = $1 AND status NOT IN ('failed','superseded')",
            date.today(),
        )
        daily_spent = float(spent_row["spent"]) if spent_row else 0.0

        return {
            "is_active": is_active and not emergency,
            "system_active": is_active,
            "emergency_stop": emergency,
            "daily_budget_limit": daily_limit,
            "daily_budget_used": daily_spent,
            "budget_remaining": daily_limit - daily_spent,
            "videos_today": videos_today or 0,
        }
    except Exception as exc:
        logger.error("activity.check_system_status.failed", error=str(exc))
        return {"is_active": False, "error": str(exc)}


@activity.defn
async def get_eligible_channels() -> list[dict]:
    """Get channels that are active, schedule-enabled, and due for video production."""
    logger.info("activity.get_eligible_channels")
    try:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT channel_id, channel_name, niche, content_mode, schedule_config, "
            "videos_per_week_short, videos_per_week_long, max_daily_api_spend "
            "FROM channels WHERE status = 'active'"
        )
        import json
        from datetime import datetime, timedelta

        week_start = (datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        result = []
        for r in rows:
            sched_raw = r["schedule_config"]
            sched = json.loads(sched_raw) if isinstance(sched_raw, str) else (sched_raw or {})
            if not sched.get("enabled", True):
                continue
            mode_raw = r["content_mode"] or "short"
            modes = ["short", "long_form"] if mode_raw == "both" else [m.strip() for m in mode_raw.split(",")]
            running = await pool.fetchval(
                "SELECT COUNT(*) FROM videos WHERE channel_id = $1 "
                "AND status NOT IN ('delivered', 'test_delivered', 'failed', 'stopped', 'superseded', 'rejected')",
                r["channel_id"],
            )
            if (running or 0) > 0:
                continue
            picked_mode = None
            for mode in modes:
                limit = r["videos_per_week_short"] if mode == "short" else r["videos_per_week_long"]
                used = await pool.fetchval(
                    "SELECT COUNT(*) FROM videos WHERE channel_id = $1 "
                    "AND content_mode = $2 AND created_at >= $3 "
                    "AND status NOT IN ('failed','stopped','superseded','rejected')",
                    r["channel_id"],
                    mode,
                    week_start,
                )
                if (used or 0) < (limit or 0):
                    picked_mode = mode
                    break
            if picked_mode:
                result.append(
                    {
                        "channel_id": r["channel_id"],
                        "channel_name": r["channel_name"],
                        "niche": r["niche"],
                        "content_mode": picked_mode,
                        "max_daily_api_spend": (float(r["max_daily_api_spend"]) if r["max_daily_api_spend"] else 5.0),
                        "topic_candidates": [],
                    }
                )
        return result
    except Exception as exc:
        logger.error("activity.get_eligible_channels.failed", error=str(exc))
        return []


@activity.defn
async def acquire_channel_lock(channel_id: str) -> bool:
    """Try to acquire a Redis lock for a channel (prevents double runs).

    Backward-compatible boolean return. Callers that need the fencing
    token (for safe release) should use ``acquire_channel_lock_v2``.
    """
    logger.info("activity.acquire_lock", channel_id=channel_id)
    try:
        r = await get_redis()
        token = secrets.token_hex(16)
        acquired = await r.set(
            f"lock:channel:{channel_id}",
            token,
            nx=True,
            ex=_LOCK_TTL_S,
        )
        return bool(acquired)
    except Exception as exc:
        logger.warning("activity.acquire_lock.failed", error=str(exc))
        return False


@activity.defn
async def acquire_channel_lock_v2(channel_id: str) -> dict:
    """Acquire a channel lock and return the fencing token.

    Returns ``{"acquired": bool, "token": str}``. Pass ``token`` to
    ``release_channel_lock`` / ``refresh_channel_lock`` so a stale
    holder can't accidentally release the new holder's lock.
    """
    logger.info("activity.acquire_lock_v2", channel_id=channel_id)
    try:
        r = await get_redis()
        token = secrets.token_hex(16)
        acquired = await r.set(
            f"lock:channel:{channel_id}",
            token,
            nx=True,
            ex=_LOCK_TTL_S,
        )
        return {"acquired": bool(acquired), "token": token if acquired else ""}
    except Exception as exc:
        logger.warning("activity.acquire_lock_v2.failed", error=str(exc))
        return {"acquired": False, "token": ""}


@activity.defn
async def emit_job_event(
    content_id: str,
    channel_id: str,
    phase: str,
    status: str,
    detail: dict | None = None,
    cost_usd: float = 0,
) -> None:
    """Emit a job progress event.

    Writes to (a) the ``job_events`` Postgres table for durable audit
    and dashboard queries, and (b) a Redis Stream ``stream:jobs:{content_id}``
    for real-time SSE/WS fan-out via streaming-hub. Both writes are
    dedup-guarded by a short-TTL Redis key so accidental double-emits
    from workflow retries don't spam the UI.
    """
    logger.info("activity.emit_job_event", content_id=content_id, phase=phase, status=status)
    detail_bytes = _json.dumps(detail or {}, sort_keys=True, default=str).encode("utf-8")
    detail_hash = hashlib.sha256(detail_bytes).hexdigest()[:16]

    # Dedup guard (idempotent emits within TTL window).
    try:
        r = await get_redis()
        dedup_key = _event_dedup_key(content_id, phase, status, detail_hash)
        first = await r.set(dedup_key, "1", nx=True, ex=_EVENT_DEDUP_TTL_S)
        if not first:
            logger.debug(
                "activity.emit_job_event.dedup_skip",
                content_id=content_id,
                phase=phase,
                status=status,
            )
            return
    except Exception as exc:
        # Dedup is best-effort; on Redis outage, fall through and still
        # emit — losing an event is worse than a rare duplicate.
        logger.debug("activity.emit_job_event.dedup_unavailable", error=str(exc))
        r = None

    # (a) Postgres row — source of truth for dashboards.
    try:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO job_events (content_id, channel_id, phase, status, detail, cost_usd, environment) "
            "VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)",
            content_id,
            channel_id,
            phase,
            status,
            detail_bytes.decode("utf-8"),
            float(cost_usd),
            "production",
        )
    except Exception as exc:
        logger.warning("activity.emit_job_event.pg_failed", error=str(exc))

    # (b) Redis Stream — real-time UI fan-out. Streaming-hub consumes
    # this via XREAD with per-connection Last-ID for resumable SSE/WS.
    if r is not None:
        try:
            event_id = hashlib.sha256(f"{content_id}:{phase}:{status}:{detail_hash}".encode()).hexdigest()[:24]
            await r.xadd(
                _event_stream_key(content_id),
                {
                    "event_id": event_id,
                    "content_id": content_id,
                    "channel_id": channel_id,
                    "phase": phase,
                    "status": status,
                    "detail": detail_bytes.decode("utf-8"),
                    "cost_usd": str(float(cost_usd)),
                },
                maxlen=_EVENT_STREAM_MAXLEN,
                approximate=True,
            )
            if _DUAL_WRITE_LEGACY_EVENTS:
                # Keep legacy pub/sub consumers alive during migration.
                await r.publish(
                    f"jobs:{content_id}",
                    _json.dumps(
                        {
                            "event_id": event_id,
                            "content_id": content_id,
                            "channel_id": channel_id,
                            "phase": phase,
                            "status": status,
                            "detail": detail or {},
                            "cost_usd": float(cost_usd),
                        },
                        default=str,
                    ),
                )
        except Exception as exc:
            logger.warning("activity.emit_job_event.stream_failed", error=str(exc))


@activity.defn
async def save_checkpoint_data(content_id: str, phase: str, data: dict) -> None:
    """Save phase output data to storage for resume-from-checkpoint support.

    Enforces a hard size cap (CHECKPOINT_MAX_BYTES, default 1 MB) so a
    runaway payload can't blow up storage, and wraps the payload in a
    small envelope with a sha256 checksum for corruption detection at
    load time.
    """
    logger.info("activity.save_checkpoint", content_id=content_id, phase=phase)
    try:
        from providers.registry import ProviderRegistry
        from providers.storage.base import StorageUpload

        inner = _json.dumps(data, default=str, sort_keys=True).encode("utf-8")
        if len(inner) > _CHECKPOINT_MAX_BYTES:
            logger.warning(
                "activity.save_checkpoint.too_large",
                content_id=content_id,
                phase=phase,
                size=len(inner),
                cap=_CHECKPOINT_MAX_BYTES,
            )
            return
        envelope = {
            "v": 1,
            "content_id": content_id,
            "phase": phase,
            "sha256": hashlib.sha256(inner).hexdigest(),
            "size": len(inner),
            "data": data,
        }
        payload_bytes = _json.dumps(envelope, default=str).encode("utf-8")
        storage = ProviderRegistry.get("storage")
        key = f"checkpoints/{content_id}/{phase}.json"
        await storage.upload(
            StorageUpload(
                key=key,
                data=payload_bytes,
                content_type="application/json",
            )
        )
        logger.info("activity.save_checkpoint.ok", key=key, size=len(payload_bytes))
    except Exception as exc:
        logger.warning("activity.save_checkpoint.failed", error=str(exc))


@activity.defn
async def load_checkpoint_data(content_id: str, phase: str) -> dict:
    """Load previously saved phase output data from storage.

    Supports both the new envelope format (with checksum) and the legacy
    bare-dict format for backward compatibility. Corrupted envelopes are
    dropped with a warning rather than raising, so a bad checkpoint
    never wedges resume.
    """
    logger.info("activity.load_checkpoint", content_id=content_id, phase=phase)
    try:
        from providers.registry import ProviderRegistry

        storage = ProviderRegistry.get("storage")
        key = f"checkpoints/{content_id}/{phase}.json"
        if not await storage.exists(key):
            logger.warning("activity.load_checkpoint.not_found", key=key)
            return {}
        raw = await storage.download(key)
        try:
            parsed = _json.loads(raw.decode("utf-8"))
        except Exception as exc:
            logger.warning("activity.load_checkpoint.decode_failed", key=key, error=str(exc))
            return {}

        # Envelope format
        if isinstance(parsed, dict) and parsed.get("v") == 1 and "data" in parsed and "sha256" in parsed:
            expected = parsed["sha256"]
            inner = _json.dumps(parsed["data"], default=str, sort_keys=True).encode("utf-8")
            actual = hashlib.sha256(inner).hexdigest()
            if expected != actual:
                logger.warning(
                    "activity.load_checkpoint.checksum_mismatch",
                    key=key,
                    expected=expected,
                    actual=actual,
                )
                return {}
            data = parsed["data"]
        else:
            # Legacy bare-dict format
            data = parsed

        if not isinstance(data, dict):
            logger.warning("activity.load_checkpoint.not_a_dict", key=key)
            return {}
        logger.info("activity.load_checkpoint.ok", key=key, keys=list(data.keys())[:5])
        return data
    except Exception as exc:
        logger.warning("activity.load_checkpoint.failed", error=str(exc))
        return {}


@activity.defn
async def send_notification(payload: dict) -> None:
    """Send notification via Telegram (if configured) or log."""
    logger.info(
        "activity.notification",
        type=payload.get("type"),
        channel=payload.get("channel_id"),
    )
    try:
        pool = await get_pool()
        token_row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = 'telegram_bot_token'"
        )
        chat_row = await pool.fetchrow("SELECT config_value FROM system_config WHERE config_key = 'telegram_chat_id'")
        token = token_row["config_value"] if token_row else ""
        chat_id = chat_row["config_value"] if chat_row else ""

        if not token or not chat_id:
            logger.info("activity.notification.skip", reason="telegram not configured")
            return

        import httpx

        notif_type = payload.get("type", "info")
        channel_id = payload.get("channel_id", "")
        content_id = payload.get("content_id", "")

        if notif_type == "human_review_required":
            text = (
                f"\u26a0\ufe0f *Review Needed*\n"
                f"Channel: `{channel_id}`\n"
                f"Video: `{content_id}`\n"
                f"Topic: {payload.get('topic', 'N/A')}\n"
                f"Score: {payload.get('composite_score', 'N/A')}"
            )
        elif notif_type == "video_completed":
            text = (
                f"\u2705 *Video Completed*\n"
                f"Channel: `{channel_id}`\n"
                f"Video: `{content_id}`\n"
                f"Cost: ${payload.get('cost', 0):.2f}"
            )
        elif notif_type == "video_failed":
            text = (
                f"\u274c *Video Failed*\n"
                f"Channel: `{channel_id}`\n"
                f"Video: `{content_id}`\n"
                f"Error: {payload.get('error', 'Unknown')}"
            )
        else:
            text = f"\u2139\ufe0f *{notif_type}*\n{payload}"

        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=10,
            )
    except Exception as exc:
        logger.warning("activity.notification.failed", error=str(exc))
