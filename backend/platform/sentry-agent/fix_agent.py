"""Fix Agent — LLM-powered code fix, branch creation, and PR opening."""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
import redis.asyncio as aioredis
import structlog
from config import (
    AUTOFIX_MAX_PER_DAY,
    AUTOFIX_REQUIRE_APPROVAL,
    LLM_MODEL,
    OPENAI_API_KEY,
    REDIS_URL,
)
from github_client import GitHubClient
from triage import extract_stack_summary, find_culprit_file

logger = structlog.get_logger()


async def _check_and_bump_daily_quota() -> tuple[bool, int]:
    """Atomically increment today's auto-fix counter and check the cap.

    Returns ``(allowed, current_count)``. Uses a UTC-day-scoped key so
    the budget resets at midnight UTC without a background job.
    """
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    key = f"sentry:autofix:count:{day}"
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        count = await r.incr(key)
        if count == 1:
            # First bump today — set TTL so the key auto-expires.
            await r.expire(key, 26 * 3600)  # 26h — belt-and-braces past midnight
        allowed = count <= AUTOFIX_MAX_PER_DAY
        return allowed, int(count)
    finally:
        await r.aclose()


_SYSTEM_PROMPT = """\
You are a senior software engineer performing surgical bug fixes.
You will receive:
1. A Sentry error report (title, level, stack trace)
2. The full content of the culprit source file

Your job: produce the minimal, correct fix — one or two lines changed at most.

Respond with ONLY a JSON object, no markdown fences:
{
  "can_fix": true,
  "confidence": "high" | "medium" | "low",
  "explanation": "one-line summary of what changed and why",
  "fixed_content": "<complete corrected file content>"
}

If you cannot fix it confidently, respond with:
{
  "can_fix": false,
  "confidence": "low",
  "explanation": "reason why not auto-fixable",
  "fixed_content": null
}

Rules:
- Only return can_fix=true with confidence high or medium
- fixed_content must be the ENTIRE file, not a diff
- Do NOT add or remove comments, imports, or unrelated code
- If the root cause is infra/config/env, return can_fix=false
"""


class FixAgent:
    async def attempt_fix(self, sentry_issue: dict, ticket_key: str) -> Optional[str]:
        """Try to auto-fix the error. Returns PR URL on success, None otherwise."""
        # Safety rail 1: daily budget check (per plan §2.5 — prevent
        # notification/PR storms). Runs before any LLM or GitHub call.
        try:
            allowed, count = await _check_and_bump_daily_quota()
            if not allowed:
                logger.warning(
                    "fix_agent.daily_quota_exceeded",
                    ticket=ticket_key,
                    count=count,
                    cap=AUTOFIX_MAX_PER_DAY,
                )
                return None
        except Exception as exc:  # noqa: BLE001 — fail closed on Redis error
            logger.warning("fix_agent.quota_check_failed", error=str(exc), ticket=ticket_key)
            return None

        # Safety rail 2: require explicit env opt-in (default true =
        # don't push PRs autonomously — just prepare the branch/commit
        # locally and log for human review).
        if AUTOFIX_REQUIRE_APPROVAL:
            logger.info(
                "fix_agent.approval_required_skipping_pr",
                ticket=ticket_key,
                note="set SENTRY_AUTOFIX_REQUIRE_APPROVAL=false to enable autonomous PRs",
            )
            return None

        culprit_path = find_culprit_file(sentry_issue)
        if not culprit_path:
            logger.info("fix_agent.no_culprit", ticket=ticket_key)
            return None

        gh = GitHubClient()
        file_data = await gh.get_file(culprit_path)
        if not file_data or file_data.get("type") != "file":
            logger.info("fix_agent.file_not_found", path=culprit_path, ticket=ticket_key)
            return None

        try:
            raw_content = base64.b64decode(file_data["content"]).decode("utf-8")
        except Exception as exc:
            logger.warning("fix_agent.decode_failed", error=str(exc))
            return None

        stack_summary = extract_stack_summary(sentry_issue)
        fix_result = await self._call_llm(
            issue=sentry_issue,
            file_path=culprit_path,
            file_content=raw_content,
            stack_summary=stack_summary,
        )

        if not fix_result:
            return None
        if not fix_result.get("can_fix"):
            logger.info(
                "fix_agent.llm_cannot_fix",
                reason=fix_result.get("explanation"),
                ticket=ticket_key,
            )
            return None
        if fix_result.get("confidence") == "low":
            logger.info("fix_agent.low_confidence", ticket=ticket_key)
            return None

        branch_name = _make_branch_name(ticket_key)
        await gh.create_branch(branch_name)

        commit_msg = (
            f"fix({ticket_key}): {fix_result['explanation'][:70]}\n\nAuto-fix for Sentry issue\nJira: {ticket_key}"
        )
        await gh.update_file(
            path=culprit_path,
            new_content=fix_result["fixed_content"],
            commit_message=commit_msg,
            branch=branch_name,
            blob_sha=file_data["sha"],
        )

        pr_body = _build_pr_body(
            sentry_issue=sentry_issue,
            ticket_key=ticket_key,
            culprit_path=culprit_path,
            explanation=fix_result["explanation"],
            confidence=fix_result.get("confidence", "unknown"),
            stack_summary=stack_summary,
        )
        pr = await gh.create_pr(
            title=f"fix({ticket_key}): {sentry_issue.get('title', 'Sentry Error')[:60]}",
            body=pr_body,
            head=branch_name,
        )
        return pr["html_url"]

    async def _call_llm(
        self,
        *,
        issue: dict,
        file_path: str,
        file_content: str,
        stack_summary: str,
    ) -> Optional[dict]:
        error_title = issue.get("title", "Unknown error")
        level = issue.get("level", "error")
        project = issue.get("project", {}).get("name", "unknown")

        user_prompt = (
            f"Error: {error_title}\n"
            f"Level: {level}  |  Project: {project}\n"
            f"Culprit file: {file_path}\n\n"
            f"Stack trace:\n{stack_summary}\n\n"
            f"Content of `{file_path}`:\n"
            f"```\n{file_content[:6000]}\n```\n\n"
            "Produce the fix JSON now."
        )

        try:
            async with httpx.AsyncClient(timeout=90) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={
                        "model": LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.1,
                        "max_tokens": 8192,
                    },
                )
                r.raise_for_status()
                raw = r.json()["choices"][0]["message"]["content"]
                result: dict = json.loads(raw)
                logger.info(
                    "fix_agent.llm_response",
                    can_fix=result.get("can_fix"),
                    confidence=result.get("confidence"),
                )
                return result
        except Exception as exc:
            logger.error("fix_agent.llm_failed", error=str(exc))
            return None


def _make_branch_name(ticket_key: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", ticket_key.lower())
    return f"sentry/{slug}-autofix"


def _build_pr_body(
    *,
    sentry_issue: dict,
    ticket_key: str,
    culprit_path: str,
    explanation: str,
    confidence: str,
    stack_summary: str,
) -> str:
    title = sentry_issue.get("title", "Sentry Error")
    permalink = sentry_issue.get("permalink", "N/A")
    project = sentry_issue.get("project", {}).get("name", "unknown")
    count = sentry_issue.get("count", "?")

    return (
        f"## Auto-fix: {title}\n\n"
        f"| Field | Value |\n"
        f"|---|---|\n"
        f"| **Jira** | `{ticket_key}` |\n"
        f"| **Sentry** | {permalink} |\n"
        f"| **Project** | {project} |\n"
        f"| **Culprit** | `{culprit_path}` |\n"
        f"| **Occurrences** | {count} |\n"
        f"| **Confidence** | {confidence} |\n\n"
        f"### What changed\n{explanation}\n\n"
        f"### Stack trace\n```\n{stack_summary[:1500]}\n```\n\n"
        f"---\n*Generated by Sentry Agent — review carefully before merging*"
    )
