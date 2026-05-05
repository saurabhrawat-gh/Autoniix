from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

from src.services.assembly.render_predictor import (
    compute_direction_complexity,
    estimate_render_duration,
    simplify_direction_for_retry,
    log_render_attempt,
)

logger = structlog.get_logger()


# ── Request Models ───────────────────────────────────────────

class AssemblyRequest(BaseModel):
    content_id: str
    channel_id: str
    content_mode: str = "short"
    title: str
    direction_v3: dict = Field(default_factory=dict)
    thumbnail_url: str = ""
    environment: str = "test"


class RenderStatusRequest(BaseModel):
    render_id: str


# ── Helpers ──────────────────────────────────────────────────

async def _load_channel(channel_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    return dict(row) if row else {}


# ── App ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("assembly.starting")
    yield
    await close_pool()
    logger.info("assembly.stopped")


app = FastAPI(title="Assembly Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="assembly")


@app.post("/assemble", response_model=ServiceResponse)
async def assemble(req: AssemblyRequest):
    """Submit Direction v3 to Remotion API for rendering, poll until complete."""
    logger.info("assembly.assembling", content_id=req.content_id,
                 segments=len(req.direction_v3.get("segments", [])))

    try:
        direction_v3 = req.direction_v3
        if not direction_v3 or not direction_v3.get("segments"):
            raise HTTPException(status_code=400, detail="No direction_v3 data provided")

        # ── Test Mode: skip Remotion, return mock render ──
        is_test_mode = req.environment != "production"
        if is_test_mode:
            seg_count = len(direction_v3.get("segments", []))
            total_ms = sum(s.get("duration_ms", 0) for s in direction_v3.get("segments", []))
            mock_url = f"test://mock-render/{req.content_id}.mp4"
            logger.info("assembly.test_mode_mock", content_id=req.content_id, segments=seg_count)
            try:
                pool = await get_pool()
                await pool.execute(
                    "UPDATE videos SET render_url = $1, production_score = $2, "
                    "status = 'rendered', updated_at = NOW() WHERE content_id = $3",
                    mock_url, 8.0, req.content_id,
                )
            except Exception as e:
                logger.warning("assembly.test_mock_db_update_failed", error=str(e))
            return ServiceResponse(
                status="success",
                data={
                    "render_id": f"mock-{req.content_id}",
                    "video_url": mock_url,
                    "render_duration_s": 0,
                    "video_duration_s": round(total_ms / 1000, 1) if total_ms else 30.0,
                    "production_score": 8.0,
                    "production_issues": [],
                    "segment_count": seg_count,
                    "intelligence": {
                        "complexity": {"complexity": 0, "risk": "low"},
                        "estimated_render_s": 0,
                    },
                    "test_mode": True,
                },
                cost={"cost_usd": 0, "provider": "mock"},
            )

        segments = direction_v3.get("segments", [])

        # ── Pre-Render Sync Validation ────────────────────
        sync_issues = []

        # 1. Timeline continuity: no gaps or overlaps
        for i, seg in enumerate(segments):
            if i == 0:
                if seg.get("start_ms", 0) != 0:
                    sync_issues.append(f"Segment {seg.get('id')}: start_ms should be 0, got {seg.get('start_ms')}")
            else:
                prev = segments[i - 1]
                expected_start = prev.get("start_ms", 0) + prev.get("duration_ms", 0)
                actual_start = seg.get("start_ms", 0)
                if actual_start != expected_start:
                    sync_issues.append(
                        f"Segment {seg.get('id')}: timeline gap/overlap — "
                        f"expected start_ms={expected_start}, got {actual_start}"
                    )

        # 2. Voice-text alignment: every segment with narration must have audio_url
        for seg in segments:
            narration = seg.get("narration", {})
            if isinstance(narration, dict):
                text = narration.get("text", "")
                audio_url = narration.get("audio_url", "")
                if text and not audio_url:
                    sync_issues.append(f"Segment {seg.get('id')}: has narration text but no audio_url")
                if audio_url and not text:
                    sync_issues.append(f"Segment {seg.get('id')}: has audio_url but no narration text")

        # 3. Asset coverage: check background_url or background_strategy
        for seg in segments:
            bg_url = seg.get("scene_overrides", {}).get("background_url", "")
            bg_strategy = seg.get("background_strategy", {}).get("type", "")
            if not bg_url and bg_strategy not in ("gradient", "solid"):
                sync_issues.append(f"Segment {seg.get('id')}: no background asset and no fallback strategy")

        # 4. Text strategy presence
        missing_text_strategy = sum(1 for s in segments if not s.get("text_strategy", {}).get("primary_text"))
        if missing_text_strategy > 0:
            sync_issues.append(f"{missing_text_strategy} segments missing text_strategy.primary_text")

        # 5. Audio master validation
        audio_master = direction_v3.get("audio_master", {})
        if not audio_master.get("narration_url"):
            sync_issues.append("No master narration_url in audio_master")

        # 6. Duration sanity
        total_duration_ms = sum(s.get("duration_ms", 0) for s in segments)
        target_duration_s = direction_v3.get("meta", {}).get("duration_target_seconds", 0)
        if target_duration_s and abs(total_duration_ms / 1000 - target_duration_s) > target_duration_s * 0.2:
            sync_issues.append(
                f"Duration mismatch: segments total {total_duration_ms/1000:.1f}s, "
                f"target {target_duration_s:.1f}s"
            )

        if sync_issues:
            logger.warning("assembly.sync_issues", issues=sync_issues, count=len(sync_issues))
            direction_v3["sync_validation"] = {
                "passed": len(sync_issues) == 0,
                "issues": sync_issues,
                "issue_count": len(sync_issues),
            }
        else:
            direction_v3["sync_validation"] = {"passed": True, "issues": [], "issue_count": 0}

        # ── Intelligence: Complexity Analysis ─────────────
        complexity = compute_direction_complexity(direction_v3)
        estimated_render_s = estimate_render_duration(complexity)
        logger.info("assembly.complexity",
                     complexity=complexity.get("complexity"),
                     risk=complexity.get("risk"),
                     estimated_render_s=estimated_render_s)

        if complexity.get("risk") == "high":
            logger.warning("assembly.high_complexity",
                           risk_factors=complexity.get("risk_factors", []))

        # ── Step 1: Submit render job to Remotion API ────
        remotion_url = settings.remotion_base_url
        is_test_mode = req.environment != "production"
        render_quality = "preview" if is_test_mode else "high"
        composition = "ShortFormVideo" if req.content_mode == "short" else "MainVideo"
        render_payload: dict = {
            "composition": composition,
            "inputProps": direction_v3,
            "outputFormat": "mp4",
            "quality": 80 if render_quality == "high" else 40,
            "codec": "h264",
        }
        if is_test_mode:
            render_payload["width"] = 640
            render_payload["height"] = 360
            logger.info("assembly.test_mode", quality="preview", resolution="640x360")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{remotion_url}/api/render", json=render_payload)
            resp.raise_for_status()
            render_data = resp.json()

        render_id = render_data.get("renderId", render_data.get("id", ""))
        if not render_id:
            raise HTTPException(status_code=500, detail="No render ID returned from Remotion")

        logger.info("assembly.render_submitted", render_id=render_id)

        # ── Step 2: Poll for render completion ───────────
        max_wait_s = 600  # 10 minutes max
        poll_interval_s = 5
        elapsed = 0
        render_result = None

        while elapsed < max_wait_s:
            await asyncio.sleep(poll_interval_s)
            elapsed += poll_interval_s

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    status_resp = await client.get(f"{remotion_url}/api/render/{render_id}")
                    status_resp.raise_for_status()
                    render_result = status_resp.json()

                status = render_result.get("status", "unknown")
                if status in ("completed", "done"):
                    break
                elif status == "failed":
                    error_msg = render_result.get("error", "Unknown render error")
                    raise HTTPException(status_code=500, detail=f"Render failed: {error_msg}")
                else:
                    progress = render_result.get("progress", 0)
                    logger.info("assembly.render_progress", render_id=render_id,
                                 status=status, progress=progress, elapsed=elapsed)

            except httpx.HTTPError as poll_err:
                logger.warning("assembly.poll_error", error=str(poll_err))

        if not render_result or render_result.get("status") != "completed":
            # Intelligence: Try simplified direction on failure
            logger.warning("assembly.render_failed_trying_simplified")
            await log_render_attempt(
                req.content_id, req.channel_id, render_id,
                complexity, success=False, error_category="timeout")

            simplified = simplify_direction_for_retry(direction_v3)
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp2 = await client.post(f"{remotion_url}/api/render", json={
                        "composition": composition,
                        "inputProps": simplified, "outputFormat": "mp4",
                        "quality": 80, "codec": "h264",
                    })
                    resp2.raise_for_status()
                    retry_data = resp2.json()
                    retry_id = retry_data.get("renderId", retry_data.get("id", ""))

                if retry_id:
                    elapsed2 = 0
                    while elapsed2 < 300:
                        await asyncio.sleep(5)
                        elapsed2 += 5
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            sr = await client.get(f"{remotion_url}/api/render/{retry_id}")
                            sr.raise_for_status()
                            render_result = sr.json()
                        if render_result.get("status") in ("completed", "done"):
                            render_id = retry_id
                            break
                        elif render_result.get("status") == "failed":
                            break
            except Exception as retry_err:
                logger.error("assembly.retry_failed", error=str(retry_err))

            if not render_result or render_result.get("status") not in ("completed", "done"):
                await log_render_attempt(
                    req.content_id, req.channel_id, render_id,
                    complexity, success=False, retry_count=1, error_category="timeout_retry")
                raise HTTPException(status_code=504, detail="Render timed out after retry")

        video_url = render_result.get("outputUrl", render_result.get("url", ""))
        render_duration = render_result.get("renderDuration", 0)

        # ── Step 3: Production QC ────────────────────────
        production_score = 8.0
        production_issues = []

        target_duration = direction_v3.get("meta", {}).get("duration_target_seconds", 0)
        actual_duration = render_result.get("videoDuration", target_duration)
        if target_duration and abs(actual_duration - target_duration) > target_duration * 0.1:
            production_score -= 1.0
            production_issues.append(f"Duration mismatch: target {target_duration}s, actual {actual_duration}s")

        if not video_url:
            production_score -= 2.0
            production_issues.append("No output URL from render")

        # ── Step 4: Update DB ────────────────────────────
        try:
            pool = await get_pool()
            await pool.execute(
                "UPDATE videos SET render_url = $1, render_id = $2, production_score = $3, "
                "status = 'rendered', updated_at = NOW() WHERE content_id = $4",
                video_url, render_id, production_score, req.content_id)
        except Exception as e:
            logger.warning("assembly.db_update_failed", error=str(e))

        # Intelligence: Log successful render
        await log_render_attempt(
            req.content_id, req.channel_id, render_id,
            complexity, success=True,
            render_duration_s=render_duration,
            video_duration_s=actual_duration)

        logger.info("assembly.completed",
                     render_id=render_id,
                     video_url=video_url[:80] if video_url else "",
                     production_score=production_score,
                     render_time=render_duration)

        return ServiceResponse(
            status="success",
            data={
                "render_id": render_id,
                "video_url": video_url,
                "render_duration_s": render_duration,
                "video_duration_s": actual_duration,
                "production_score": round(production_score, 1),
                "production_issues": production_issues,
                "segment_count": len(direction_v3.get("segments", [])),
                "intelligence": {
                    "complexity": complexity,
                    "estimated_render_s": estimated_render_s,
                },
            },
            cost={"cost_usd": 0, "provider": "remotion"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("assembly.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/render-status/{render_id}", response_model=ServiceResponse)
async def render_status(render_id: str):
    """Check the status of a Remotion render job."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.remotion_base_url}/render/{render_id}")
            resp.raise_for_status()
            return ServiceResponse(status="success", data=resp.json())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.assembly.main:app", host="0.0.0.0", port=8006, log_level="info")
