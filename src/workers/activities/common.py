from __future__ import annotations

from datetime import date, datetime

import structlog
from temporalio import activity

from src.db import get_pool
from src.redis_client import get_redis

logger = structlog.get_logger()


@activity.defn
async def update_video_status(content_id: str, status: str,
                               channel_id: str = "", title: str = "",
                               content_mode: str = "") -> None:
    """Update the status column for a video in PostgreSQL.
    
    Also saves the current phase as checkpoint so that stopped jobs
    can be resumed from the last active phase.
    """
    logger.info("activity.update_status", content_id=content_id, status=status,
                channel_id=channel_id or "N/A")
    try:
        env = "production"
        pool = await get_pool()

        terminal_statuses = {'delivered', 'test_delivered', 'failed', 'stopped', 'superseded', 'rejected'}
        is_active_phase = status not in terminal_statuses

        if is_active_phase:
            prev = await pool.fetchrow(
                "SELECT status FROM videos WHERE content_id = $1", content_id
            )
            if prev and prev["status"] in ("failed", "stopped"):
                await pool.execute(
                    "DELETE FROM job_events WHERE content_id = $1", content_id
                )
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
                content_id, channel_id, status, title, content_mode, env,
            )
            if channel_id and content_mode and status == "researching":
                await pool.execute(
                    "UPDATE videos SET status = 'superseded', updated_at = NOW() "
                    "WHERE channel_id = $1 AND content_mode = $2 "
                    "AND content_id != $3 "
                    "AND status IN ('failed', 'stopped')",
                    channel_id, content_mode, content_id,
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
                content_id, channel_id, status, title, content_mode, env,
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
                        ch, cm, content_id,
                    )
    except Exception as exc:
        logger.warning("activity.update_status.failed", error=str(exc))


@activity.defn
async def release_channel_lock(channel_id: str) -> None:
    """Release the Redis lock for a channel."""
    logger.info("activity.release_lock", channel_id=channel_id)
    try:
        r = await get_redis()
        await r.delete(f"lock:channel:{channel_id}")
    except Exception as exc:
        logger.warning("activity.release_lock.failed", error=str(exc))


@activity.defn
async def check_system_status() -> dict:
    """Read system_config and compute budget status."""
    logger.info("activity.check_system_status")
    try:
        pool = await get_pool()

        active_row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = 'system_active'"
        )
        emergency_row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = 'emergency_stop'"
        )
        budget_row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = 'daily_budget_limit'"
        )

        is_active = (active_row and active_row["config_value"] == "true")
        emergency = (emergency_row and emergency_row["config_value"] == "true")
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
                    r["channel_id"], mode, week_start,
                )
                if (used or 0) < (limit or 0):
                    picked_mode = mode
                    break
            if picked_mode:
                result.append({
                    "channel_id": r["channel_id"],
                    "channel_name": r["channel_name"],
                    "niche": r["niche"],
                    "content_mode": picked_mode,
                    "max_daily_api_spend": float(r["max_daily_api_spend"]) if r["max_daily_api_spend"] else 5.0,
                    "topic_candidates": [],
                })
        return result
    except Exception as exc:
        logger.error("activity.get_eligible_channels.failed", error=str(exc))
        return []


@activity.defn
async def acquire_channel_lock(channel_id: str) -> bool:
    """Try to acquire a Redis lock for a channel (prevents double runs)."""
    logger.info("activity.acquire_lock", channel_id=channel_id)
    try:
        r = await get_redis()
        acquired = await r.set(
            f"lock:channel:{channel_id}",
            "locked",
            nx=True,
            ex=3600,
        )
        return bool(acquired)
    except Exception as exc:
        logger.warning("activity.acquire_lock.failed", error=str(exc))
        return False


@activity.defn
async def emit_job_event(content_id: str, channel_id: str, phase: str,
                          status: str, detail: dict | None = None,
                          cost_usd: float = 0) -> None:
    """Insert a row into job_events for dashboard progress tracking."""
    logger.info("activity.emit_job_event", content_id=content_id, phase=phase, status=status)
    try:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO job_events (content_id, channel_id, phase, status, detail, cost_usd, environment) "
            "VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)",
            content_id, channel_id, phase, status,
            __import__("json").dumps(detail or {}), float(cost_usd), "production",
        )
    except Exception as exc:
        logger.warning("activity.emit_job_event.failed", error=str(exc))


@activity.defn
async def save_checkpoint_data(content_id: str, phase: str, data: dict) -> None:
    """Save phase output data to storage for resume-from-checkpoint support."""
    logger.info("activity.save_checkpoint", content_id=content_id, phase=phase)
    try:
        import json as _json
        from src.providers.registry import ProviderRegistry
        from src.providers.storage.base import StorageUpload

        storage = ProviderRegistry.get("storage")
        key = f"checkpoints/{content_id}/{phase}.json"
        payload_bytes = _json.dumps(data, default=str).encode("utf-8")
        await storage.upload(StorageUpload(
            key=key,
            data=payload_bytes,
            content_type="application/json",
        ))
        logger.info("activity.save_checkpoint.ok", key=key, size=len(payload_bytes))
    except Exception as exc:
        logger.warning("activity.save_checkpoint.failed", error=str(exc))


@activity.defn
async def load_checkpoint_data(content_id: str, phase: str) -> dict:
    """Load previously saved phase output data from storage."""
    logger.info("activity.load_checkpoint", content_id=content_id, phase=phase)
    try:
        import json as _json
        from src.providers.registry import ProviderRegistry

        storage = ProviderRegistry.get("storage")
        key = f"checkpoints/{content_id}/{phase}.json"
        if not await storage.exists(key):
            logger.warning("activity.load_checkpoint.not_found", key=key)
            return {}
        raw = await storage.download(key)
        data = _json.loads(raw.decode("utf-8"))
        logger.info("activity.load_checkpoint.ok", key=key, keys=list(data.keys())[:5])
        return data
    except Exception as exc:
        logger.warning("activity.load_checkpoint.failed", error=str(exc))
        return {}


@activity.defn
async def send_notification(payload: dict) -> None:
    """Send notification via Telegram (if configured) or log."""
    logger.info("activity.notification", type=payload.get("type"), channel=payload.get("channel_id"))
    try:
        pool = await get_pool()
        token_row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = 'telegram_bot_token'"
        )
        chat_row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = 'telegram_chat_id'"
        )
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
