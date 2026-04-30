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
        from src.environment import get_mode_from_db
        env = await get_mode_from_db()
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO videos (content_id, status, environment, updated_at) VALUES ($1, $2, $3, NOW()) "
            "ON CONFLICT (content_id) DO UPDATE SET status = $2, updated_at = NOW()",
            content_id,
            status,
            env,
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

        # Environment mode
        env_row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = 'environment_mode'"
        )
        environment_mode = env_row["config_value"] if env_row else "test"
        is_test = environment_mode != "production"

        # Test mode: apply tighter budget limits
        if is_test:
            test_budget_row = await pool.fetchrow(
                "SELECT config_value FROM system_config WHERE config_key = 'test_daily_budget_limit'"
            )
            daily_limit = float(test_budget_row["config_value"]) if test_budget_row else 5.0

        # Test mode: apply max videos per day limit
        test_max_videos = 999
        if is_test:
            max_vid_row = await pool.fetchrow(
                "SELECT config_value FROM system_config WHERE config_key = 'test_max_videos_per_day'"
            )
            test_max_videos = int(max_vid_row["config_value"]) if max_vid_row else 10

        videos_today = await pool.fetchval(
            "SELECT COUNT(*) FROM videos WHERE created_at::date = $1 AND status != 'failed'",
            date.today(),
        )

        spent_row = await pool.fetchrow(
            "SELECT COALESCE(SUM(total_cost), 0) as spent FROM videos "
            "WHERE created_at::date = $1 AND status != 'failed'",
            date.today(),
        )
        daily_spent = float(spent_row["spent"]) if spent_row else 0.0

        # Test mode video count guard
        videos_at_limit = is_test and (videos_today or 0) >= test_max_videos

        return {
            "is_active": is_active and not emergency and not videos_at_limit,
            "system_active": is_active,
            "emergency_stop": emergency,
            "daily_budget_limit": daily_limit,
            "daily_budget_used": daily_spent,
            "budget_remaining": daily_limit - daily_spent,
            "environment_mode": environment_mode,
            "test_max_videos_per_day": test_max_videos if is_test else None,
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
            # Determine which modes this channel supports
            mode_raw = r["content_mode"] or "short"
            modes = ["short", "long_form"] if mode_raw == "both" else [m.strip() for m in mode_raw.split(",")]
            # Skip channels that already have a running job
            running = await pool.fetchval(
                "SELECT COUNT(*) FROM videos WHERE channel_id = $1 "
                "AND status NOT IN ('delivered', 'failed', 'rejected')",
                r["channel_id"],
            )
            if (running or 0) > 0:
                continue
            # Pick ONE eligible mode (short first — higher frequency)
            picked_mode = None
            for mode in modes:
                limit = r["videos_per_week_short"] if mode == "short" else r["videos_per_week_long"]
                used = await pool.fetchval(
                    "SELECT COUNT(*) FROM videos WHERE channel_id = $1 "
                    "AND content_mode = $2 AND created_at >= $3 "
                    "AND status NOT IN ('rejected')",
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
        from src.environment import get_mode_from_db
        env = await get_mode_from_db()
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO job_events (content_id, channel_id, phase, status, detail, cost_usd, environment) "
            "VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)",
            content_id, channel_id, phase, status,
            __import__("json").dumps(detail or {}), float(cost_usd), env,
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
