from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class NotificationPayload:
    def __init__(
        self,
        event_type: str,
        severity: str,
        title: str,
        body: str,
        payload: dict[str, Any],
        channel_id: str = "",
        video_id: str = "",
    ):
        self.event_type = event_type
        self.severity = severity
        self.title = title
        self.body = body
        self.payload = payload
        self.channel_id = channel_id
        self.video_id = video_id


class Channel(ABC):
    @abstractmethod
    async def send(self, n: NotificationPayload, cfg: dict[str, Any]) -> dict[str, Any]:
        pass


class SlackChannel(Channel):
    SEVERITY_COLOR = {
        "info": "#3aa3e3",
        "warn": "#f0b429",
        "error": "#e64980",
        "critical": "#c92a2a",
    }

    def __init__(self, http_client: httpx.AsyncClient):
        self.http = http_client

    async def send(self, n: NotificationPayload, cfg: dict[str, Any]) -> dict[str, Any]:
        webhook = cfg.get("webhook_url") or os.getenv("SLACK_WEBHOOK_URL", "")
        if not webhook:
            raise ValueError("no slack webhook configured")

        color = self.SEVERITY_COLOR.get(n.severity, "#888")

        fields = []
        for k, v in list(n.payload.items())[:8]:
            val = str(v)
            if len(val) > 240:
                val = val[:240]
            fields.append({"title": k, "value": val, "short": True})

        body = {
            "attachments": [
                {
                    "color": color,
                    "title": n.title,
                    "text": n.body,
                    "fields": fields,
                    "footer": f"event: {n.event_type} · severity: {n.severity}",
                }
            ]
        }

        return await self._post_json(webhook, body)

    async def _post_json(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        resp = await self.http.post(url, json=body)
        if resp.status_code >= 400:
            text = resp.text[:240] if len(resp.text) > 240 else resp.text
            raise ValueError(f"http {resp.status_code}: {text}")
        return {"status": resp.status_code}


class WebhookChannel(Channel):
    def __init__(self, http_client: httpx.AsyncClient):
        self.http = http_client

    async def send(self, n: NotificationPayload, cfg: dict[str, Any]) -> dict[str, Any]:
        url = cfg.get("url")
        if not url:
            raise ValueError("no webhook url configured")

        body = {
            "event_type": n.event_type,
            "severity": n.severity,
            "title": n.title,
            "body": n.body,
            "payload": n.payload,
            "channel_id": n.channel_id,
            "video_id": n.video_id,
        }

        resp = await self.http.post(url, json=body)
        if resp.status_code >= 400:
            text = resp.text[:240] if len(resp.text) > 240 else resp.text
            raise ValueError(f"http {resp.status_code}: {text}")
        return {"status": resp.status_code}


class BrowserChannel(Channel):
    async def send(self, n: NotificationPayload, cfg: dict[str, Any]) -> dict[str, Any]:
        return {"info": "via_notification_center"}


class EmailChannel(Channel):
    async def send(self, n: NotificationPayload, cfg: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("email channel not configured")


def default_channels(http_client: httpx.AsyncClient) -> dict[str, Channel]:
    return {
        "slack": SlackChannel(http_client),
        "webhook": WebhookChannel(http_client),
        "browser": BrowserChannel(),
        "email": EmailChannel(),
    }
