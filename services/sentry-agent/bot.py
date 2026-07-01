"""Sentry Agent — Slack Socket Mode entry point.

Listens to #alerts-critical and #alerts-warnings.
On every Sentry alert:
  1. Deduplicates via Redis fingerprint
  2. Fetches full issue from Sentry API
  3. Creates a Jira bug ticket (bug:production or bug:normal)
  4. Attempts an LLM-powered code fix + GitHub PR
  5. Replies in the Slack thread with the PR link
"""
from __future__ import annotations

import asyncio
import logging

import redis.asyncio as aioredis
import structlog
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from config import (
    DEDUP_TTL_SECONDS,
    REDIS_URL,
    SLACK_APP_TOKEN,
    SLACK_BOT_TOKEN,
    SLACK_CRITICAL_CHANNEL_ID,
    SLACK_WARNINGS_CHANNEL_ID,
)
from fix_agent import FixAgent
from jira_client import JiraClient
from sentry_client import SentryClient
from triage import (
    detect_layer,
    map_priority,
    parse_sentry_slack_message,
)

logging.basicConfig(level=logging.INFO)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
logger = structlog.get_logger()

app = AsyncApp(token=SLACK_BOT_TOKEN)

_WATCHED = {SLACK_CRITICAL_CHANNEL_ID, SLACK_WARNINGS_CHANNEL_ID}


@app.event("message")
async def on_message(event: dict, client: object) -> None:
    channel_id: str = event.get("channel", "")
    if channel_id not in _WATCHED:
        return

    is_bot = bool(event.get("bot_id") or event.get("subtype") == "bot_message")
    if not is_bot:
        return

    alert = parse_sentry_slack_message(event)
    if not alert:
        return

    is_critical = channel_id == SLACK_CRITICAL_CHANNEL_ID
    thread_ts: str = event.get("ts", "")

    asyncio.create_task(
        _process(alert, is_critical, channel_id, thread_ts, client)
    )


async def _process(
    alert: dict,
    is_critical: bool,
    channel_id: str,
    thread_ts: str,
    client: object,
) -> None:
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        dedup_key = f"sentry:dedup:{alert['fingerprint']}"
        existing_ticket = await redis_client.get(dedup_key)
        if existing_ticket:
            logger.info("sentry_agent.dedup_skip",
                        fingerprint=alert["fingerprint"], ticket=existing_ticket)
            return

        await _slack_reply(client, channel_id, thread_ts,
                           f":robot_face: *Sentry Agent* picked up `{alert['title']}` — triaging...")

        sentry = SentryClient()
        full_issue = await sentry.get_issue(alert["issue_id"])

        layer = detect_layer(full_issue)
        bug_label, jira_priority = map_priority(is_critical, full_issue.get("level", "error"))
        env_prefix = "Prod" if is_critical else "QA"
        title = f"bug | {env_prefix} | {layer} | {alert['title'][:80]}"

        jira = JiraClient()
        ticket = await jira.create_bug(
            title=title,
            full_issue=full_issue,
            jira_priority=jira_priority,
            is_critical=is_critical,
            bug_label=bug_label,
            sentry_url=alert["url"],
            layer=layer,
        )
        ticket_key: str = ticket["key"]

        await redis_client.setex(dedup_key, DEDUP_TTL_SECONDS, ticket_key)
        logger.info("sentry_agent.ticket_created", ticket=ticket_key,
                    layer=layer, priority=jira_priority)

        await _slack_reply(client, channel_id, thread_ts,
                           f":ticket: Jira `{ticket_key}` created ({jira_priority}) — attempting auto-fix...")

        fixer = FixAgent()
        pr_url = await fixer.attempt_fix(full_issue, ticket_key)

        if pr_url:
            await jira.post_comment(
                ticket_key,
                f"Sentry Agent auto-fix PR: {pr_url}",
            )
            await _slack_reply(
                client, channel_id, thread_ts,
                f":white_check_mark: *Fix ready for review*\n"
                f"> PR: {pr_url}\n"
                f"> Jira: `{ticket_key}`",
            )
        else:
            await _slack_reply(
                client, channel_id, thread_ts,
                f":warning: Could not auto-fix — ticket `{ticket_key}` is `ready-for-dev`. "
                f"Dev team will pick it up.",
            )

    except Exception as exc:
        logger.exception("sentry_agent.processing_failed", error=str(exc))
        await _slack_reply(
            client, channel_id, thread_ts,
            f":x: Sentry Agent error: `{exc}`\nCheck agent logs for details.",
        )
    finally:
        await redis_client.aclose()


async def _slack_reply(
    client: object, channel: str, thread_ts: str, text: str
) -> None:
    await client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=text,
    )


async def main() -> None:
    logger.info("sentry_agent.starting",
                critical_channel=SLACK_CRITICAL_CHANNEL_ID,
                warnings_channel=SLACK_WARNINGS_CHANNEL_ID)
    handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
