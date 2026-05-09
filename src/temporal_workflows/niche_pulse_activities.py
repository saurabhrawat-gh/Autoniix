"""Activity for the NichePulseRefreshWorkflow (Phase 8).

The work is dispatched to the existing competitor-insights collector,
which already knows how to pull recent videos via YouTube Data API and
persist them. Phase 8's earlier change made that collector also write
``title_embedding``, so calling it here is sufficient — no separate
embedding pass is needed.

We pick a representative channel for each niche to drive the collector
(it requires a ``our_channel_id`` for linking competitor → owner). When
multiple channels share a niche, any one of them works because the
underlying ``competitor_videos`` rows are keyed on the *competitor*
channel + niche, not the requesting one.
"""
from __future__ import annotations

from temporalio import activity

from src.db import get_pool
from src.services.research.competitor_insights import collect_competitor_insights


@activity.defn(name="refresh_niche_pulse")
async def refresh_niche_pulse_activity(niche: str) -> dict:
    """Refresh the niche pulse for one niche.

    Returns a serialisable summary (videos stored, niche outliers found,
    competitor count). On a niche with no active channel we skip
    gracefully — there's nothing to attribute the data to.
    """
    pool = await get_pool()
    # Pick any active channel in this niche to act as the owner-of-record
    # for the competitor data. ``ORDER BY channel_id`` keeps the choice
    # deterministic across runs so the audit trail is stable.
    channel_id = await pool.fetchval(
        """
        SELECT channel_id FROM channels
        WHERE niche = $1 AND status = 'active'
        ORDER BY channel_id
        LIMIT 1
        """,
        niche,
    )
    if not channel_id:
        return {"niche": niche, "action": "skipped", "reason": "no active channel"}

    insights = await collect_competitor_insights(
        our_channel_id=channel_id,
        niche=niche,
        # competitor_yt_ids=None → discover via search; this is the
        # right behaviour for a periodic refresh because the operator
        # may not have curated a competitor list per niche.
        competitor_yt_ids=None,
    )

    return {
        "niche":             niche,
        "action":            "refreshed",
        "competitor_count":  insights.get("competitor_count", 0),
        "videos_stored":     insights.get("videos_stored", 0),
        "outliers":          len(insights.get("outlier_videos", [])),
        "niche_outliers":    len(insights.get("niche_outliers", [])),
    }
