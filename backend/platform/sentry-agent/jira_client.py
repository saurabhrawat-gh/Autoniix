"""Jira REST API v3 client — creates bug tickets and posts comments."""

from __future__ import annotations

import base64

import httpx
import structlog
from config import JIRA_API_TOKEN, JIRA_CLOUD_ID, JIRA_EMAIL, JIRA_PROJECT_KEY
from triage import extract_stack_summary

logger = structlog.get_logger()

_BASE = f"https://api.atlassian.com/ex/jira/{JIRA_CLOUD_ID}/rest/api/3"


def _auth_header() -> str:
    creds = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()
    return "Basic " + base64.b64encode(creds).decode()


def _text_doc(text: str) -> dict:
    """Minimal ADF document wrapping plain text."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def _code_block_doc(heading: str, stack: str, sentry_url: str, culprit: str, occurrences: str, project: str) -> dict:
    """ADF document with structured Sentry context + code block."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Sentry issue: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": sentry_url, "marks": [{"type": "link", "attrs": {"href": sentry_url}}]},
                ],
            },
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": f"Project: {project}  |  Culprit: {culprit}  |  Occurrences: {occurrences}",
                    },
                ],
            },
            {"type": "rule"},
            {
                "type": "codeBlock",
                "attrs": {"language": "text"},
                "content": [{"type": "text", "text": stack or "No stack trace available"}],
            },
        ],
    }


class JiraClient:
    def __init__(self) -> None:
        self._headers = {
            "Authorization": _auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def create_bug(
        self,
        *,
        title: str,
        full_issue: dict,
        jira_priority: str,
        is_critical: bool,
        bug_label: str,
        sentry_url: str,
        layer: str,
    ) -> dict:
        """Create a Jira Bug in the AE project and return the created issue dict."""
        level = full_issue.get("level", "error")
        project_slug = full_issue.get("project", {}).get("slug", "unknown")
        culprit = full_issue.get("culprit", "unknown")
        count = str(full_issue.get("count", "?"))
        stack = extract_stack_summary(full_issue)

        env_prefix = "Prod" if is_critical else "QA"

        labels = ["sentry-agent", bug_label, "ready-for-dev"]
        if is_critical:
            labels.append("hotfix")

        payload = {
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": title,
                "issuetype": {"name": "Bug"},
                "priority": {"name": jira_priority},
                "labels": labels,
                "description": _code_block_doc(
                    heading=title,
                    stack=stack,
                    sentry_url=sentry_url,
                    culprit=culprit,
                    occurrences=count,
                    project=project_slug,
                ),
                "customfield_10073": env_prefix,  # Environment
                "customfield_10075": layer,  # Layer
            }
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{_BASE}/issue",
                headers=self._headers,
                json=payload,
            )
            r.raise_for_status()
            data: dict = r.json()
            logger.info("jira.ticket_created", key=data.get("key"), title=title)
            return data

    async def post_comment(self, issue_key: str, text: str) -> None:
        """Append a plain-text comment to an existing Jira issue."""
        payload = {"body": _text_doc(text)}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{_BASE}/issue/{issue_key}/comment",
                headers=self._headers,
                json=payload,
            )
            r.raise_for_status()
