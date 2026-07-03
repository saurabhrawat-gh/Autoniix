"""YouTube Analytics retention-curve fetcher (Phase 9).

The YouTube *Data* API (used by ``analytics/main.py``) returns
view counts and engagement metrics — but **not** the audience-retention
curve. That data lives behind the YouTube *Analytics* API
(``youtubeAnalytics.reports.query``) which requires OAuth, not just an
API key.

This module:

1. Refreshes the OAuth access token using the configured refresh token.
2. Calls ``audienceWatchRatio`` for one video, which returns ~100
   (elapsedVideoTimeRatio, audienceWatchRatio) pairs.
3. Parses the curve, derives the three Phase-9 features via
   :mod:`src.quality.retention_features`, and persists everything to
   ``retention_curves``.

Failure modes are explicit (``RetentionFetchError``) so the caller —
typically a Temporal activity — can decide whether to retry or skip.
Most failures (404, 403, 401-needs-refresh) are transient at the
per-video level and the workflow should not abort the batch.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import httpx
import structlog

from src.config import settings
from src.db import get_pool
from src.quality.retention_features import (
    CurvePoint,
    RetentionFeatures,
    compute_features,
    parse_curve,
)

logger = structlog.get_logger()




class RetentionFetchError(Exception):
    """Raised when the retention fetch fails for a video. Carries the
    HTTP status code (or 0 for non-HTTP errors) so the caller can
    distinguish "this video has no analytics yet" (404) from "auth
    expired" (401) from "wrong scope" (403)."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status




_token_cache: dict[str, Any] = {"access_token": None, "expires_at": None}


async def _get_access_token() -> str:
    """Return a valid access token, refreshing if needed.

    Uses a tiny in-process cache so a batch of N video fetches doesn't
    trigger N refreshes. The cache holds the token until 60 seconds
    before its declared expiry — well inside Google's typical 1-hour
    TTL, with margin for clock skew.
    """
    now = datetime.utcnow()
    cached = _token_cache.get("access_token")
    expires_at = _token_cache.get("expires_at")
    if cached and expires_at and now < expires_at:
        return cached

    if not (settings.google_oauth_client_id
            and settings.google_oauth_client_secret
            and settings.google_oauth_refresh_token):
        raise RetentionFetchError(
            "OAuth credentials not configured (need client_id, client_secret, refresh_token)",
            status=0,
        )

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id":     settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "refresh_token": settings.google_oauth_refresh_token,
                "grant_type":    "refresh_token",
            },
        )
    if resp.status_code != 200:
        raise RetentionFetchError(
            f"OAuth refresh failed: {resp.status_code} {resp.text[:200]}",
            status=resp.status_code,
        )
    data = resp.json()
    token = data.get("access_token")
    expires_in = int(data.get("expires_in", 3600))
    if not token:
        raise RetentionFetchError("OAuth response missing access_token", status=0)

    _token_cache["access_token"] = token
    _token_cache["expires_at"]   = now + timedelta(seconds=max(60, expires_in - 60))
    return token




async def fetch_retention_curve(yt_video_id: str) -> list[CurvePoint]:
    """Pull the audience-retention curve for one video.

    Returns the parsed curve. Raises ``RetentionFetchError`` on failure.
    Empty curves are returned as ``[]`` — that's a valid response from
    YT Analytics for very new or very low-view videos.
    """
    token = await _get_access_token()

    today = datetime.utcnow().strftime("%Y-%m-%d")

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            "https://youtubeanalytics.googleapis.com/v2/reports",
            params={
                "ids":        "channel==MINE",
                "startDate":  "2005-01-01",
                "endDate":    today,
                "metrics":    "audienceWatchRatio",
                "dimensions": "elapsedVideoTimeRatio",
                "filters":    f"video=={yt_video_id}",
                "sort":       "elapsedVideoTimeRatio",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    if resp.status_code == 401:
        _token_cache["access_token"] = None
        raise RetentionFetchError("OAuth token rejected (401)", status=401)
    if resp.status_code == 403:
        raise RetentionFetchError(
            f"Forbidden — likely missing yt-analytics.readonly scope: {resp.text[:200]}",
            status=403,
        )
    if resp.status_code == 404:
        raise RetentionFetchError(f"No analytics for video {yt_video_id}", status=404)
    if resp.status_code != 200:
        raise RetentionFetchError(
            f"Analytics API {resp.status_code}: {resp.text[:200]}",
            status=resp.status_code,
        )

    data = resp.json()
    rows = data.get("rows") or []
    return parse_curve(rows)




async def fetch_and_store_retention(content_id: str) -> dict:
    """Fetch + persist for one delivered video.

    Looks up the video in ``videos`` (for ``youtube_video_id``,
    ``channel_id``, and a duration estimate), pulls the curve, computes
    features, upserts ``retention_curves``. Returns a small summary the
    caller can log.

    Returns ``{"status": "skipped", "reason": "..."}`` for benign cases
    (no yt id, no duration) so a periodic batch can carry on.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT v.content_id,
               v.channel_id,
               v.youtube_video_id,
               v.created_at,
               -- voice_duration_s is the realised voiceover length and
               -- equals the rendered video length. yt_avg_view_duration
               -- is a fallback only when voice timing wasn't recorded
               -- (e.g. very old rows). Coalesce + cast for safety.
               COALESCE(v.voice_duration_s::float,
                        v.yt_avg_view_duration::float,
                        0)               AS duration_seconds
        FROM videos v
        WHERE v.content_id = $1
        """,
        content_id,
    )
    if row is None:
        return {"status": "skipped", "reason": "video not found"}
    yt_id = row["youtube_video_id"]
    if not yt_id:
        return {"status": "skipped", "reason": "no youtube_video_id"}

    duration = float(row["duration_seconds"] or 0)
    age_days = None
    if row["created_at"]:
        age_days = int((datetime.utcnow() - row["created_at"].replace(tzinfo=None)).total_seconds() / 86400)

    try:
        curve = await fetch_retention_curve(yt_id)
    except RetentionFetchError as exc:
        return {"status": "error", "yt_video_id": yt_id, "code": exc.status, "error": str(exc)}

    if not curve:
        return {"status": "empty", "yt_video_id": yt_id}

    features: RetentionFeatures = compute_features(curve, duration_seconds=duration or None)

    if not features.valid:
        return {"status": "invalid_curve", "yt_video_id": yt_id, "n_points": len(curve)}

    curve_json = json.dumps([
        {"elapsed_ratio": p.elapsed_ratio, "watch_ratio": p.watch_ratio}
        for p in curve
    ])

    await pool.execute(
        """
        INSERT INTO retention_curves (
            video_id, channel_id, yt_video_id,
            hook_dropoff_30s, mid_video_decay, end_retention,
            curve_points, sample_count, fetched_at, video_age_days
        ) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, NOW(), $9)
        ON CONFLICT (video_id) DO UPDATE SET
            hook_dropoff_30s = EXCLUDED.hook_dropoff_30s,
            mid_video_decay  = EXCLUDED.mid_video_decay,
            end_retention    = EXCLUDED.end_retention,
            curve_points     = EXCLUDED.curve_points,
            sample_count     = EXCLUDED.sample_count,
            fetched_at       = NOW(),
            video_age_days   = EXCLUDED.video_age_days
        """,
        content_id,
        row["channel_id"],
        yt_id,
        features.hook_dropoff_30s,
        features.mid_video_decay,
        features.end_retention,
        curve_json,
        len(curve),
        age_days,
    )

    logger.info("retention.fetched", video_id=content_id, yt_video_id=yt_id,
                hook_drop=features.hook_dropoff_30s,
                mid_decay=features.mid_video_decay,
                end_ret=features.end_retention,
                n_points=len(curve))
    return {
        "status":            "stored",
        "yt_video_id":       yt_id,
        "hook_dropoff_30s":  features.hook_dropoff_30s,
        "mid_video_decay":   features.mid_video_decay,
        "end_retention":     features.end_retention,
        "n_points":          len(curve),
    }




async def videos_needing_retention(
    *,
    min_age_days: int = 7,
    max_age_days: int = 30,
    limit: int = 50,
) -> list[str]:
    """Find delivered videos in the curve-stable window without a curve yet.

    YouTube retention curves shift over the first ~7 days as the
    algorithm finds the audience; pulling earlier than that gives
    unstable training labels. After ~30 days the algorithm has
    settled and re-fetching adds little. So we target [7, 30] days.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT v.content_id
        FROM videos v
        LEFT JOIN retention_curves rc ON rc.video_id = v.content_id
        WHERE v.status = 'delivered'
          AND v.youtube_video_id IS NOT NULL
          AND v.created_at <  NOW() - ($1::int * INTERVAL '1 day')
          AND v.created_at >= NOW() - ($2::int * INTERVAL '1 day')
          AND rc.video_id IS NULL
        ORDER BY v.created_at ASC
        LIMIT $3
        """,
        min_age_days, max_age_days, limit,
    )
    return [r["content_id"] for r in rows]
