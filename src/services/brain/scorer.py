"""OutcomeScorer — back-fills brain_decisions.outcome_score so the
Reflector has data to mine.

The Reflector (``src/services/brain/reflector.py``) only fires when it
sees decisions whose ``outcome_score`` column is populated. Until this
loop ran, every brain_decisions row had ``outcome_score IS NULL`` and
the Reflector silently did nothing. This module is the missing link.

Scoring philosophy
------------------

Scores live on a 0-10 scale. **High = the decision was good**, low =
the decision was bad. The Reflector uses this directly: a class of
decisions with sustained low scores is the signal to propose a flag
tweak that makes that decision class harder to trigger.

Per-type scoring is intentionally pragmatic — proxies, not perfect
counterfactuals. Each function returns ``(score, outcome_jsonb)`` or
``None`` if there is not enough downstream data yet (in which case the
row is left untouched and the next pass tries again).

* HALT (scope=channel): the channel was halted. After resolve, look at
  delivered video quality. *Low post-resume quality validates the
  HALT* → high outcome_score. *High post-resume quality means the HALT
  was a false positive* → low outcome_score. No videos at all = the
  HALT was probably the right call (channel stayed off) → 8.0.

* HOLD (scope=video/content_id): the specific video was held. If it
  was eventually delivered, the HOLD let a real video through after a
  transient issue → score is the video's own final composite. If it
  failed permanently, the HOLD was a waste → 3.0.

* NUDGE (scope=channel): a bias was applied. Score = 5 + (post_avg -
  pre_avg) × 2, clamped to [0, 10]. Positive delta = NUDGE worked.

* RESUME (scope=channel): the channel was un-halted. *High post-resume
  quality validates the RESUME* → high score. Low quality means we
  resumed too eagerly → low score.

* ADVISE: informational, no enforcement. Default to 5.0 once the
  measurement window has elapsed so the Reflector doesn't ignore them
  forever (the Reflector applies a sample-size + threshold filter
  anyway, so neutral scores don't trigger spurious proposals).

Decisions whose scope can't be mapped to a video/channel signal
(missing scope_id, unknown decision_type) are left unscored.

Part of AE-P1 / Agentic Foundation.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from src.db import get_pool
from src.flags import get_flag

logger = structlog.get_logger()




async def score_once(*, dry_run: bool = False) -> int:
    """Run a single scoring pass.

    Returns the number of decisions that received a score (or that
    would have, in ``dry_run`` mode). Errors are caught and logged so a
    transient DB blip never kills the loop.
    """
    try:
        enabled = await get_flag("brain.scorer.enabled", default=False)
    except Exception as exc:
        logger.warning("brain.scorer.flag_read_failed", error=str(exc))
        return 0
    if not enabled:
        logger.debug("brain.scorer.disabled")
        return 0

    try:
        return await _score_pass(dry_run=dry_run)
    except Exception as exc:
        logger.error("brain.scorer.failed", error=str(exc))
        return 0


async def run_scorer_loop(
    interval_s: int | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run :func:`score_once` periodically until ``stop_event`` is set.

    ``interval_s`` defaults to ``brain.scorer.interval_hours`` × 3600.
    The interval is re-read each loop so operators can speed up
    scoring by lowering the flag without restarting the service.
    """
    logger.info("brain.scorer.starting")
    while True:
        if stop_event is not None and stop_event.is_set():
            break

        await score_once()

        if interval_s is None:
            try:
                hours = await get_flag(
                    "brain.scorer.interval_hours", default=6
                )
                sleep_for = max(60, int(float(hours) * 3600))
            except Exception:
                sleep_for = 6 * 3600
        else:
            sleep_for = max(60, int(interval_s))

        try:
            if stop_event is not None:
                await asyncio.wait_for(stop_event.wait(), timeout=sleep_for)
                break
            else:
                await asyncio.sleep(sleep_for)
        except asyncio.TimeoutError:
            pass
    logger.info("brain.scorer.stopped")




async def _score_pass(*, dry_run: bool) -> int:
    window_days = int(
        await get_flag("brain.scorer.measurement_window_days", default=7) or 7
    )
    min_videos = int(
        await get_flag("brain.scorer.min_videos_for_signal", default=3) or 3
    )
    batch_size = int(
        await get_flag("brain.scorer.batch_size", default=200) or 200
    )

    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, decision_type, scope, scope_id, created_at, resolved_at
        FROM brain_decisions
        WHERE resolved_at IS NOT NULL
          AND outcome_score IS NULL
          AND resolved_at < NOW() - ($1 || ' days')::interval
        ORDER BY resolved_at ASC
        LIMIT $2
        """,
        str(window_days),
        batch_size,
    )
    if not rows:
        logger.debug(
            "brain.scorer.nothing_to_score", window_days=window_days,
        )
        return 0

    scored = 0
    skipped = 0
    for row in rows:
        result = await _score_decision(
            row, window_days=window_days, min_videos=min_videos
        )
        if result is None:
            skipped += 1
            continue
        score, outcome = result
        if dry_run:
            logger.info(
                "brain.scorer.would_score",
                decision_id=row["id"],
                decision_type=row["decision_type"],
                score=score,
            )
            scored += 1
            continue
        try:
            await _persist_score(
                decision_id=row["id"], score=score, outcome=outcome
            )
            scored += 1
        except Exception as exc:
            logger.warning(
                "brain.scorer.persist_failed",
                decision_id=row["id"], error=str(exc),
            )

    logger.info(
        "brain.scorer.cycle_complete",
        scored=scored,
        skipped=skipped,
        batch_size=len(rows),
        dry_run=dry_run,
    )
    return scored


async def _score_decision(
    row: dict[str, Any], *, window_days: int, min_videos: int
) -> tuple[float, dict[str, Any]] | None:
    """Dispatch to the per-type scorer. Returns ``None`` to leave the
    row unscored (the next pass tries again)."""
    dtype = row["decision_type"]
    if dtype == "HALT":
        return await _score_halt(row, window_days=window_days, min_videos=min_videos)
    if dtype == "HOLD":
        return await _score_hold(row, window_days=window_days)
    if dtype == "NUDGE":
        return await _score_nudge(row, window_days=window_days, min_videos=min_videos)
    if dtype == "RESUME":
        return await _score_resume(row, window_days=window_days, min_videos=min_videos)
    if dtype == "ADVISE":
        return _score_advise(row)
    logger.debug(
        "brain.scorer.unknown_decision_type",
        decision_id=row["id"], decision_type=dtype,
    )
    return None




async def _score_halt(
    row: dict[str, Any], *, window_days: int, min_videos: int
) -> tuple[float, dict[str, Any]] | None:
    channel_id = row["scope_id"]
    if not channel_id:
        return None
    scores = await _post_resolve_scores(
        channel_id=channel_id,
        resolved_at=row["resolved_at"],
        window_days=window_days,
    )
    if not scores:
        return 8.0, {
            "scoring_method": "halt.no_post_resume_videos",
            "window_days": window_days,
        }
    if len(scores) < min_videos:
        return None
    avg = sum(scores) / len(scores)
    score = max(0.0, min(10.0, 10.0 - avg))
    return round(score, 2), {
        "scoring_method": "halt.inverted_post_resume_quality",
        "post_resume_avg_score": round(avg, 2),
        "sample_size": len(scores),
        "window_days": window_days,
    }




async def _score_hold(
    row: dict[str, Any], *, window_days: int
) -> tuple[float, dict[str, Any]] | None:
    content_id = row["scope_id"]
    if not content_id:
        return None
    pool = await get_pool()
    video = await pool.fetchrow(
        """
        SELECT status, final_composite_score
        FROM videos
        WHERE id = $1
        """,
        content_id,
    )
    if video is None:
        return 5.0, {"scoring_method": "hold.video_not_found"}
    status = video["status"]
    if status == "delivered":
        final = video["final_composite_score"]
        if final is None:
            return 5.0, {"scoring_method": "hold.delivered_no_score"}
        return round(float(final), 2), {
            "scoring_method": "hold.delivered_score",
            "final_composite_score": round(float(final), 2),
        }
    if status == "failed":
        return 3.0, {"scoring_method": "hold.video_failed_after_hold"}
    return None




async def _score_nudge(
    row: dict[str, Any], *, window_days: int, min_videos: int
) -> tuple[float, dict[str, Any]] | None:
    channel_id = row["scope_id"]
    if not channel_id:
        return None
    pool = await get_pool()
    pre_rows = await pool.fetch(
        """
        SELECT final_composite_score
        FROM videos
        WHERE channel_id = $1
          AND status = 'delivered'
          AND final_composite_score IS NOT NULL
          AND created_at <  $2
          AND created_at >= $2 - ($3 || ' days')::interval
        """,
        channel_id, row["created_at"], str(window_days),
    )
    post_rows = await pool.fetch(
        """
        SELECT final_composite_score
        FROM videos
        WHERE channel_id = $1
          AND status = 'delivered'
          AND final_composite_score IS NOT NULL
          AND created_at >= $2
          AND created_at <  $2 + ($3 || ' days')::interval
        """,
        channel_id, row["resolved_at"], str(window_days),
    )
    pre = [float(r["final_composite_score"]) for r in pre_rows]
    post = [float(r["final_composite_score"]) for r in post_rows]
    if len(post) < min_videos:
        return None
    pre_avg = sum(pre) / len(pre) if pre else 5.0
    post_avg = sum(post) / len(post)
    delta = post_avg - pre_avg
    score = max(0.0, min(10.0, 5.0 + delta * 2.0))
    return round(score, 2), {
        "scoring_method": "nudge.quality_delta",
        "pre_avg_score": round(pre_avg, 2),
        "post_avg_score": round(post_avg, 2),
        "delta": round(delta, 2),
        "pre_sample_size": len(pre),
        "post_sample_size": len(post),
        "window_days": window_days,
    }




async def _score_resume(
    row: dict[str, Any], *, window_days: int, min_videos: int
) -> tuple[float, dict[str, Any]] | None:
    channel_id = row["scope_id"]
    if not channel_id:
        return None
    scores = await _post_resolve_scores(
        channel_id=channel_id,
        resolved_at=row["resolved_at"],
        window_days=window_days,
    )
    if len(scores) < min_videos:
        return None
    avg = sum(scores) / len(scores)
    score = max(0.0, min(10.0, avg))
    return round(score, 2), {
        "scoring_method": "resume.post_resume_quality",
        "post_resume_avg_score": round(avg, 2),
        "sample_size": len(scores),
        "window_days": window_days,
    }




def _score_advise(row: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """ADVISE is informational only — there is no enforcement event to
    measure. Score neutrally (5.0) so the row leaves the queue."""
    return 5.0, {"scoring_method": "advise.neutral_default"}




async def _post_resolve_scores(
    *, channel_id: str, resolved_at: Any, window_days: int
) -> list[float]:
    """Return final_composite_scores for delivered videos on
    *channel_id* in the [resolved_at, resolved_at + window) window."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT final_composite_score
        FROM videos
        WHERE channel_id = $1
          AND status = 'delivered'
          AND final_composite_score IS NOT NULL
          AND created_at >= $2
          AND created_at <  $2 + ($3 || ' days')::interval
        """,
        channel_id, resolved_at, str(window_days),
    )
    return [float(r["final_composite_score"]) for r in rows]


async def _persist_score(
    *, decision_id: int, score: float, outcome: dict[str, Any]
) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE brain_decisions
        SET outcome_score = $1,
            outcome = COALESCE(outcome, '{}'::jsonb) || $2::jsonb
        WHERE id = $3
        """,
        round(float(score), 2),
        json.dumps(outcome),
        decision_id,
    )
    logger.info(
        "brain.scorer.scored",
        decision_id=decision_id,
        score=score,
        method=outcome.get("scoring_method"),
    )
