"""Niche-pulse refresh workflow (Phase 8).

For every active channel's niche, refresh the recent-competitor-video
snapshot — including title embeddings — so the saturation scorer has
fresh data to compare candidates against.

Why a separate workflow vs. piggy-backing on research-on-demand:
the research endpoint is hit *per video*, but the pulse data is
*per niche* and shared across all videos in that niche. Coupling them
would (a) re-fetch the same competitor data 5× per day per niche and
(b) consume YouTube API quota wastefully. A weekly batched refresh is
the right cadence: niche saturation moves on a multi-day timescale,
not a multi-minute one.

Cron: Sunday 05:00 UTC (one hour after gate calibration so they don't
fight for the scheduler's activity slots).
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


RETRY_LIGHT = RetryPolicy(
    maximum_attempts=2,
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
)


@workflow.defn
class NichePulseRefreshWorkflow:
    """Weekly per-niche competitor-video refresh + embedding compute."""

    @workflow.run
    async def run(self, params: dict | None = None) -> dict:
        niches: list[str] = await workflow.execute_activity(
            "list_niches_with_outcomes",
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_LIGHT,
        )

        results: dict[str, dict] = {}
        for niche in niches:
            try:
                summary = await workflow.execute_activity(
                    "refresh_niche_pulse",
                    args=[niche],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RETRY_LIGHT,
                )
                results[niche] = summary
            except Exception as exc:
                results[niche] = {"action": "error", "error": str(exc)}

        return {"niches_processed": len(niches), "results": results}
