"""Notification dispatcher.

Used by ``notify()`` — a tiny helper any service can call to fan out an
event through the configured routes. Slack is the only external channel
implemented in-tree; webhook + email follow the same pattern.
"""
from __future__ import annotations

import fnmatch
import json
import os
from typing import Any

import structlog

from core.db import get_pool
from providers.secrets import get_secret_at

logger = structlog.get_logger()

_SEVERITY_RANK = {"info": 0, "warn": 1, "error": 2, "critical": 3}


async def notify(
    event_type: str,
    *,
    title: str,
    severity: str = "info",
    body: str | None = None,
    payload: dict[str, Any] | None = None,
    channel_id: str | None = None,
    video_id: str | None = None,
    dedupe_key: str | None = None,
) -> int | None:
    """Persist a notification and dispatch through matching routes.

    Returns the notification id on success or ``None`` on best-effort failure.
    """
    try:
        pool = await get_pool()
        if dedupe_key:
            dup = await pool.fetchval(
                "SELECT id FROM notifications WHERE dedupe_key=$1 "
                "AND created_at > NOW() - INTERVAL '60 seconds'",
                dedupe_key,
            )
            if dup:
                return dup
        nid = await pool.fetchval(
            """INSERT INTO notifications
                (event_type, severity, title, body, payload, channel_id, video_id, dedupe_key)
               VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8) RETURNING id""",
            event_type, severity, title, body or "",
            json.dumps(payload or {}), channel_id, video_id, dedupe_key,
        )
        await dispatch_routes(nid, {
            "event_type": event_type, "severity": severity, "title": title,
            "body": body, "payload": payload or {}, "channel_id": channel_id,
            "video_id": video_id,
        })
        try:
            from services_api.dashboard import main as _legacy
            await _legacy._event_broadcaster.broadcast({
                "type": "notification",
                "id": nid,
                "event_type": event_type,
                "severity": severity,
                "title": title,
                "body": body,
                "channel_id": channel_id,
                "video_id": video_id,
            })
        except Exception:
            pass
        return nid
    except Exception as exc:
        logger.warning("notify.failed", error=str(exc), event=event_type)
        return None


async def dispatch_routes(notification_id: int, n: dict) -> None:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, event_pattern, severity_min, channels, config, enabled "
        "FROM notification_routes WHERE enabled=TRUE"
    )
    sev_rank = _SEVERITY_RANK.get(n["severity"], 0)
    for r in rows:
        if not fnmatch.fnmatch(n["event_type"], r["event_pattern"]):
            continue
        if sev_rank < _SEVERITY_RANK.get(r["severity_min"], 0):
            continue
        for ch in r["channels"]:
            await _deliver(notification_id, r["id"], ch, n, r["config"] or {})


async def _deliver(notification_id: int, route_id: int, channel: str,
                   n: dict, config: dict) -> None:
    pool = await get_pool()
    delivery_id = await pool.fetchval(
        """INSERT INTO notification_deliveries (notification_id, route_id, channel, status)
           VALUES ($1,$2,$3,'queued') RETURNING id""",
        notification_id, route_id, channel,
    )
    ok, err, response = False, None, None
    try:
        if channel == "slack":
            ok, response, err = await _send_slack(n, config)
        elif channel == "webhook":
            ok, response, err = await _send_webhook(n, config)
        elif channel == "browser":
            ok, response = True, {"info": "via_notification_center"}
        elif channel == "email":
            ok, response, err = False, None, "email channel not configured"
        else:
            err = f"unknown channel {channel!r}"
    except Exception as exc:
        err = str(exc)
    await pool.execute(
        """UPDATE notification_deliveries
              SET status=$1, response=$2::jsonb, error=$3, sent_at=NOW(), attempts=attempts+1
            WHERE id=$4""",
        "sent" if ok else "failed",
        json.dumps(response) if response else None,
        err, delivery_id,
    )


async def _send_slack(n: dict, config: dict) -> tuple[bool, dict | None, str | None]:
    webhook = config.get("webhook_url") or get_secret_at("notifications/slack", "webhook_url")
    if not webhook:
        webhook = os.getenv("SLACK_WEBHOOK_URL", "")
    if not webhook:
        return False, None, "no slack webhook configured"
    sev = n.get("severity", "info")
    color = {"info": "#3aa3e3", "warn": "#f0b429",
             "error": "#e64980", "critical": "#c92a2a"}.get(sev, "#888")
    payload_json = n.get("payload") or {}
    fields = [{"title": k, "value": str(v)[:240], "short": True}
              for k, v in payload_json.items()][:8]
    body = {
        "attachments": [{
            "color": color,
            "title": n["title"],
            "text": n.get("body") or "",
            "fields": fields,
            "footer": f"event: {n['event_type']} · severity: {sev}",
        }]
    }
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(webhook, json=body)
        if r.status_code >= 400:
            return False, {"status": r.status_code}, r.text[:240]
        return True, {"status": r.status_code}, None


async def _send_webhook(n: dict, config: dict) -> tuple[bool, dict | None, str | None]:
    url = config.get("url")
    if not url:
        return False, None, "no webhook url configured"
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=n)
        if r.status_code >= 400:
            return False, {"status": r.status_code}, r.text[:240]
        return True, {"status": r.status_code}, None
