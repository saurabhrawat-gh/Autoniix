"""Brand Identity Service — Manages per-channel brand DNA.

Provides brand fingerprinting, consistency scoring, and brand evolution
tracking. All other services query this for brand-aware generation.

Intelligence cost: $0.00 — all local NLP + heuristic computation.
Port: 8012
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

from src.services.brand.brand_dna import (
    compute_brand_fingerprint,
    load_brand_profile,
    save_brand_profile,
    score_brand_consistency,
)
from src.observability.metrics import instrument_app

logger = structlog.get_logger()


# Request Models

class BrandProfileRequest(BaseModel):
    channel_id: str


class BrandConsistencyRequest(BaseModel):
    channel_id: str
    content_data: dict = Field(default_factory=dict)


class BrandEvolutionRequest(BaseModel):
    channel_id: str
    days_lookback: int = 30


# Helpers

async def _load_channel(channel_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    return dict(row) if row else {}


# App

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("brand.starting")
    yield
    await close_pool()
    logger.info("brand.stopped")


from src.observability.sentry import init_sentry
init_sentry("brand")

app = FastAPI(title="Brand Identity Service", version="0.1.0", lifespan=lifespan)


instrument_app(app, service_name="brand")
@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="brand")


@app.post("/profile", response_model=ServiceResponse)
async def get_or_create_profile(req: BrandProfileRequest):
    """Get or compute brand profile for a channel."""
    logger.info("brand.profile", channel_id=req.channel_id)

    try:
        # Try to load existing profile
        profile = await load_brand_profile(req.channel_id)
        if profile:
            return ServiceResponse(
                status="success",
                data={"profile": profile, "source": "cached"},
            )

        # Compute from channel DNA
        channel = await _load_channel(req.channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {req.channel_id} not found")

        fingerprint = compute_brand_fingerprint(channel)
        await save_brand_profile(req.channel_id, fingerprint)

        logger.info("brand.profile_created", channel_id=req.channel_id)
        return ServiceResponse(
            status="success",
            data={"profile": fingerprint, "source": "computed"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("brand.profile_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/consistency", response_model=ServiceResponse)
async def check_consistency(req: BrandConsistencyRequest):
    """Check content consistency against brand identity."""
    logger.info("brand.consistency_check", channel_id=req.channel_id)

    try:
        channel = await _load_channel(req.channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {req.channel_id} not found")

        fingerprint = compute_brand_fingerprint(channel)
        result = score_brand_consistency(req.content_data, fingerprint)

        return ServiceResponse(
            status="success",
            data=result,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("brand.consistency_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/evolution", response_model=ServiceResponse)
async def track_evolution(req: BrandEvolutionRequest):
    """Track brand evolution by comparing recent performance patterns."""
    logger.info("brand.evolution", channel_id=req.channel_id)

    try:
        pool = await get_pool()

        # Get recent video performance data
        rows = await pool.fetch("""
            SELECT v.content_id, v.script_structure_score, v.hook_retention_score,
                   v.thumbnail_score, v.direction_score,
                   fl.yt_views, fl.engagement_rate, fl.performance_tier
            FROM videos v
            LEFT JOIN feedback_loop fl ON v.content_id = fl.video_id
            WHERE v.channel_id = $1 AND v.created_at > NOW() - ($2 || ' days')::INTERVAL
            ORDER BY v.created_at DESC LIMIT 20
        """, req.channel_id, str(req.days_lookback))

        if not rows:
            return ServiceResponse(
                status="success",
                data={"evolution": "insufficient_data", "videos_analyzed": 0},
            )

        # Analyze performance trends
        scores = [dict(r) for r in rows]
        avg_script = sum(float(s.get("script_structure_score") or 7) for s in scores) / len(scores)
        avg_hook = sum(float(s.get("hook_retention_score") or 7) for s in scores) / len(scores)
        avg_views = sum(int(s.get("yt_views") or 0) for s in scores) / len(scores)

        # Detect tier distribution
        tiers = [s.get("performance_tier", "C") for s in scores if s.get("performance_tier")]
        tier_dist = {}
        for t in tiers:
            tier_dist[t] = tier_dist.get(t, 0) + 1

        # Suggestions based on patterns
        suggestions = []
        if avg_script < 8.0:
            suggestions.append("Script quality trending below target — consider adjusting pacing or hook styles")
        if avg_hook < 8.5:
            suggestions.append("Hook retention could improve — try more pattern interrupts or open loops")
        if tier_dist.get("D", 0) > len(tiers) * 0.3:
            suggestions.append("High D-tier rate — review content strategy and topic selection")

        # Save snapshot
        import datetime
        try:
            await pool.execute("""
                INSERT INTO brand_style_history (channel_id, snapshot_date, style_features, performance_correlation)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (channel_id, snapshot_date) DO UPDATE SET
                    style_features = EXCLUDED.style_features,
                    performance_correlation = EXCLUDED.performance_correlation
            """, req.channel_id, datetime.date.today(),
                json.dumps({"avg_script": avg_script, "avg_hook": avg_hook}),
                json.dumps({"avg_views": avg_views, "tier_dist": tier_dist}))
        except Exception:
            pass

        return ServiceResponse(
            status="success",
            data={
                "videos_analyzed": len(scores),
                "avg_script_score": round(avg_script, 2),
                "avg_hook_score": round(avg_hook, 2),
                "avg_views": round(avg_views),
                "tier_distribution": tier_dist,
                "suggestions": suggestions,
                "days_lookback": req.days_lookback,
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("brand.evolution_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.brand.main:app", host="0.0.0.0", port=8012, log_level="info")
