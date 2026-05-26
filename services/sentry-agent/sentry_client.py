"""Sentry REST API client — fetches full issue details from an issue ID."""
from __future__ import annotations

import httpx
import structlog

from config import SENTRY_AUTH_TOKEN, SENTRY_BASE_URL

logger = structlog.get_logger()


class SentryClient:
    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {SENTRY_AUTH_TOKEN}",
            "Content-Type": "application/json",
        }

    async def get_issue(self, issue_id: str) -> dict:
        """Return the full issue object from Sentry API."""
        url = f"{SENTRY_BASE_URL}/issues/{issue_id}/"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=self._headers)
            r.raise_for_status()
            data: dict = r.json()
            logger.info("sentry.issue_fetched", issue_id=issue_id,
                        title=data.get("title", ""))
            return data

    async def get_latest_event(self, issue_id: str) -> dict | None:
        """Return the most recent event (with full stack trace) for the issue."""
        url = f"{SENTRY_BASE_URL}/issues/{issue_id}/events/"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                url,
                headers=self._headers,
                params={"limit": 1, "full": "true"},
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            events: list = r.json()
            return events[0] if events else None
