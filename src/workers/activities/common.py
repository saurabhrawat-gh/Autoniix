from __future__ import annotations

from datetime import date, datetime

import structlog
from temporalio import activity

from src.db import get_pool
from src.redis_client import get_redis

logger = structlog.get_logger()


@activity.defn
async def update_video_status(content_id: str, status: str) -> None:
    """Update the status column for a video in PostgreSQL."""
    logger.info("activity.update_status", content_id=content_id, status=status)
    try:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO videos (content_id, status, updated_at) VALUES ($1, $2, NOW()) "
            "ON CONFLICT (content_id) DO UPDATE SET status = $2, updated_at = NOW()",
            content_id,
            status,
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

        spent_row = await pool.fetchrow(
            "SELECT COALESCE(SUM(total_cost), 0) as spent FROM videos "
            "WHERE created_at::date = $1 AND status != 'failed'",
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
        }
    except Exception as exc:
        logger.error("activity.check_system_status.failed", error=str(exc))
        return {"is_active": False, "error": str(exc)}


@activity.defn
async def get_eligible_channels() -> list[dict]:
    """Get channels that are active and due for video production."""
    logger.info("activity.get_eligible_channels")
    try:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT channel_id, channel_name, niche, content_mode, schedule_config "
            "FROM channels WHERE status = 'active'"
        )
        return [
            {
                "channel_id": r["channel_id"],
                "channel_name": r["channel_name"],
                "niche": r["niche"],
                "content_mode": r["content_mode"],
                "topic_candidates": [],
            }
            for r in rows
        ]
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
            ex=3600,  # 1 hour TTL
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
            "INSERT INTO job_events (content_id, channel_id, phase, status, detail, cost_usd) "
            "VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
            content_id, channel_id, phase, status,
            __import__("json").dumps(detail or {}), float(cost_usd),
        )
    except Exception as exc:
        logger.warning("activity.emit_job_event.failed", error=str(exc))


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
