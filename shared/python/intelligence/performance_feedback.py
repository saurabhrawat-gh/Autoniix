"""Performance feedback \u2192 prompt context.

Closes the long-loop the analytics service writes to but nothing reads from.

The shape of the loop:

    delivery \u2192 feedback_loop (initial scores)
                \u2193
    analytics.collect \u2192 yt_views/likes/engagement + performance_tier (S/A/B/C/D)
                \u2193
    build_performance_context (this module)
                \u2193
    research/ideation prompts + script v1 prompts

We surface:

* The 3 strongest performers (S+A tier) \u2014 patterns to repeat
* The 2 worst performers (D tier)        \u2014 patterns to avoid
* Aggregate stats                        \u2014 baseline the model can compare against

Output is **prompt-ready text**, not raw rows, because LLM context windows
are precious and the prompt template doesn't want to know about DB columns.

Defensive by design:
* Brand-new channels with no analytics yet get an empty context (no error).
* DB errors degrade silently to empty context \u2014 we never block content
  generation because the learning loop is unavailable.
"""

from __future__ import annotations

from typing import Any

import structlog

from core.db import get_pool

logger = structlog.get_logger()


_TOP_LIMIT = 3
_WORST_LIMIT = 2
_MIN_VIEWS_FOR_LEARNING = 200


async def _fetch_performers(channel_id: str) -> dict[str, Any]:
    """Pull recent labelled performance data for a channel.

    Returns ``{"top": [...], "worst": [...], "stats": {...}}`` or an empty
    dict if there's nothing to learn from.
    """
    pool = await get_pool()

    top = await pool.fetch(
        "SELECT title, yt_views, yt_likes, engagement_rate, performance_tier, "
        "       script_score, hook_retention_score, thumbnail_score "
        "FROM feedback_loop "
        "WHERE channel_id = $1 "
        "  AND performance_tier IN ('S', 'A') "
        "  AND yt_views >= $2 "
        "ORDER BY yt_views DESC "
        "LIMIT $3",
        channel_id,
        _MIN_VIEWS_FOR_LEARNING,
        _TOP_LIMIT,
    )
    worst = await pool.fetch(
        "SELECT title, yt_views, engagement_rate, performance_tier "
        "FROM feedback_loop "
        "WHERE channel_id = $1 "
        "  AND performance_tier = 'D' "
        "  AND yt_views >= $2 "
        "ORDER BY yt_views ASC "
        "LIMIT $3",
        channel_id,
        _MIN_VIEWS_FOR_LEARNING,
        _WORST_LIMIT,
    )
    stats_row = await pool.fetchrow(
        "SELECT COUNT(*) AS n, "
        "       AVG(yt_views) AS avg_views, "
        "       AVG(engagement_rate) AS avg_engagement "
        "FROM feedback_loop "
        "WHERE channel_id = $1 AND yt_views IS NOT NULL",
        channel_id,
    )
    return {
        "top": [dict(r) for r in top],
        "worst": [dict(r) for r in worst],
        "stats": dict(stats_row) if stats_row else {},
    }


def _format(performers: dict[str, Any]) -> str:
    """Convert the structured pull into a prompt fragment.

    Empty input \u2192 empty string. Non-empty \u2192 a clearly fenced block the
    upstream prompt can splice in verbatim.
    """
    top = performers.get("top") or []
    worst = performers.get("worst") or []
    stats = performers.get("stats") or {}

    if not top and not worst:
        return ""

    lines: list[str] = ["=== CHANNEL PERFORMANCE MEMORY (use this to guide choices) ==="]

    n = stats.get("n") or 0
    if n:
        avg_views = int(stats.get("avg_views") or 0)
        avg_eng = float(stats.get("avg_engagement") or 0.0)
        lines.append(f"Baseline over {n} measured videos: avg {avg_views:,} views, {avg_eng:.1f}% engagement.")

    if top:
        lines.append("")
        lines.append("WHAT WORKS (repeat these patterns):")
        for r in top:
            views = int(r.get("yt_views") or 0)
            eng = float(r.get("engagement_rate") or 0.0)
            tier = r.get("performance_tier") or "?"
            title = (r.get("title") or "").strip()[:120]
            lines.append(f'  - [{tier}] {views:,} views, {eng:.1f}% eng \u2014 "{title}"')

    if worst:
        lines.append("")
        lines.append("WHAT FLOPS (avoid these patterns):")
        for r in worst:
            views = int(r.get("yt_views") or 0)
            eng = float(r.get("engagement_rate") or 0.0)
            title = (r.get("title") or "").strip()[:120]
            lines.append(f'  - [D] {views:,} views, {eng:.1f}% eng \u2014 "{title}"')

    lines.append("=== END PERFORMANCE MEMORY ===")
    return "\n".join(lines)


async def build_performance_context(channel_id: str) -> str:
    """Public entrypoint. Always returns a string (possibly empty).

    Errors are logged and swallowed: a flaky DB must never block the
    pipeline that actually produces revenue.
    """
    try:
        performers = await _fetch_performers(channel_id)
    except Exception as exc:
        logger.warning("performance_feedback.fetch_failed", channel_id=channel_id, error=str(exc))
        return ""
    text = _format(performers)
    if text:
        logger.info(
            "performance_feedback.attached",
            channel_id=channel_id,
            top=len(performers.get("top") or []),
            worst=len(performers.get("worst") or []),
            chars=len(text),
        )
    return text


def _format_for_tests(performers: dict[str, Any]) -> str:
    return _format(performers)
