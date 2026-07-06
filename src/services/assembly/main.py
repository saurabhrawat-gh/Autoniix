from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.config import settings
from core.db import close_pool, get_pool
from schemas.common import HealthResponse, ServiceResponse

from src.services.assembly.render_predictor import (
    compute_direction_complexity,
    estimate_render_duration,
    simplify_direction_for_retry,
    log_render_attempt,
)
from observability.metrics import instrument_app

logger = structlog.get_logger()



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



async def _load_channel(channel_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    return dict(row) if row else {}


def _build_diagnostic_direction(
    title: str,
    content_id: str,
    reason: str,
    duration_s: float,
    aspect: str = "16:9",
    fps: int = 30,
) -> dict:
    """Build a minimal Direction v3 that renders the loud DiagnosticScene.

    Used when assembly must produce *something* renderable in test mode while
    a real direction is unavailable. The output is intentionally distinguishable
    from a real render (red checkerboard, big yellow warning text) so operators
    immediately see that a fallback path was hit.
    """
    duration_ms = int(max(3.0, min(duration_s, 60.0)) * 1000)
    is_short = aspect in ("9:16", "vertical", "short", "shorts")
    width, height = (1080, 1920) if is_short else (1920, 1080)
    return {
        "version": "3.0",
        "meta": {
            "video_id": content_id,
            "channel_id": "diagnostic",
            "title": title[:120],
            "duration_target_seconds": duration_ms / 1000,
            "aspect": "9:16" if is_short else "16:9",
            "fps": fps,
            "resolution": {"width": width, "height": height},
        },
        "template": "hybrid-kinetic",
        "theme": {
            "primary_color": "#FF3B30",
            "accent_color": "#FFD60A",
            "background_color": "#3A0000",
            "text_color": "#FFFFFF",
            "fonts": {"heading": "Inter", "body": "Inter"},
        },
        "segments": [
            {
                "id": "diag-1",
                "start_ms": 0,
                "duration_ms": duration_ms,
                "scene_preset": "scene.error.diagnostic",
                "scene_overrides": {
                    "reason": reason,
                    "videoId": content_id,
                    "presetId": "(diagnostic fallback)",
                },
            },
        ],
    }


async def _render_diagnostic_via_remotion(
    *,
    content_id: str,
    channel_id: str,
    title: str,
    composition: str,
    aspect: str,
    duration_s: float,
    reason: str,
    remotion_url: str,
) -> tuple[str, float] | None:
    """Submit a DiagnosticScene-only direction to Remotion. Returns
    ``(video_url, video_duration_s)`` on success, or ``None`` on any failure.

    Test-mode-only fallback. Stays on the same render path (Remotion + post-QC
    + S3 upload) so we never produce a "fake" placeholder MP4 that pollutes
    storage and masks pipeline issues.
    """
    diag_direction = _build_diagnostic_direction(
        title=title or content_id,
        content_id=content_id,
        reason=reason,
        duration_s=duration_s,
        aspect=aspect,
    )
    payload = {
        "composition": composition,
        "inputProps": diag_direction,
        "outputFormat": "mp4",
        "quality": 50,
        "codec": "h264",
        "width": 640 if not aspect.startswith("9") else 360,
        "height": 360 if not aspect.startswith("9") else 640,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{remotion_url}/api/render", json=payload)
            resp.raise_for_status()
            render_id = resp.json().get("renderId", "")
        if not render_id:
            return None
        elapsed = 0
        while elapsed < 180:
            await asyncio.sleep(3)
            elapsed += 3
            async with httpx.AsyncClient(timeout=10.0) as client:
                sr = await client.get(f"{remotion_url}/api/render/{render_id}")
                sr.raise_for_status()
                rr = sr.json()
            if rr.get("status") in ("completed", "done"):
                url = rr.get("outputUrl", "")
                if not url:
                    return None
                return url, float(rr.get("qc", {}).get("durationSec") or duration_s)
            if rr.get("status") == "failed":
                logger.warning("assembly.diagnostic_render_failed",
                               content_id=content_id, error=rr.get("error"))
                return None
        logger.warning("assembly.diagnostic_render_timeout", content_id=content_id)
        return None
    except Exception as exc:
        logger.warning("assembly.diagnostic_render_exception",
                       content_id=content_id, error=str(exc))
        return None



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("assembly.starting")
    yield
    await close_pool()
    logger.info("assembly.stopped")


from observability.sentry import init_sentry
init_sentry("assembly")

app = FastAPI(title="Assembly Service", version="0.1.0", lifespan=lifespan)


instrument_app(app, service_name="assembly")
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

        is_test_mode = req.environment != "production"
        segments = direction_v3.get("segments", [])

        sync_issues = []

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

        for seg in segments:
            narration = seg.get("narration", {})
            if isinstance(narration, dict):
                text = narration.get("text", "")
                audio_url = narration.get("audio_url", "")
                if text and not audio_url:
                    sync_issues.append(f"Segment {seg.get('id')}: has narration text but no audio_url")
                if audio_url and not text:
                    sync_issues.append(f"Segment {seg.get('id')}: has audio_url but no narration text")

        for seg in segments:
            bg_url = seg.get("scene_overrides", {}).get("background_url", "")
            bg_strategy = seg.get("background_strategy", {}).get("type", "")
            if not bg_url and bg_strategy not in ("gradient", "solid"):
                sync_issues.append(f"Segment {seg.get('id')}: no background asset and no fallback strategy")

        missing_text_strategy = sum(1 for s in segments if not s.get("text_strategy", {}).get("primary_text"))
        if missing_text_strategy > 0:
            sync_issues.append(f"{missing_text_strategy} segments missing text_strategy.primary_text")

        audio_master = direction_v3.get("audio_master", {})
        if not audio_master.get("narration_url"):
            sync_issues.append("No master narration_url in audio_master")

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

        complexity = compute_direction_complexity(direction_v3)
        estimated_render_s = estimate_render_duration(complexity)
        logger.info("assembly.complexity",
                     complexity=complexity.get("complexity"),
                     risk=complexity.get("risk"),
                     estimated_render_s=estimated_render_s)

        if complexity.get("risk") == "high":
            logger.warning("assembly.high_complexity",
                           risk_factors=complexity.get("risk_factors", []))

        remotion_url = settings.remotion_base_url
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

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{remotion_url}/api/render", json=render_payload)
                resp.raise_for_status()
                render_data = resp.json()
        except Exception as remotion_err:
            if not is_test_mode:
                raise HTTPException(status_code=503,
                                    detail=f"Remotion service unreachable: {remotion_err}")
            logger.warning("assembly.remotion_unreachable_diagnostic_fallback",
                           error=str(remotion_err), content_id=req.content_id)
            total_ms = sum(s.get("duration_ms", 0) for s in segments)
            duration_s = round(total_ms / 1000, 1) if total_ms else 8.0
            aspect = direction_v3.get("meta", {}).get("aspect", "16:9")
            diag = await _render_diagnostic_via_remotion(
                content_id=req.content_id, channel_id=req.channel_id,
                title=req.title, composition=composition, aspect=aspect,
                duration_s=duration_s,
                reason=f"Remotion error on first submit: {str(remotion_err)[:120]}",
                remotion_url=remotion_url,
            )
            if diag is None:
                raise HTTPException(status_code=502,
                                    detail=f"Remotion unreachable and diagnostic fallback failed: {remotion_err}")
            diag_url, diag_dur = diag
            try:
                pool = await get_pool()
                await pool.execute(
                    "UPDATE videos SET rendered_video_url = $1, "
                    "production_score = $2, status = 'rendered', updated_at = NOW() "
                    "WHERE content_id = $3",
                    diag_url, 3.0, req.content_id,
                )
            except Exception as db_err:
                logger.warning("assembly.fallback_db_failed", error=str(db_err))
            return ServiceResponse(
                status="success",
                data={
                    "render_id": f"diagnostic-{req.content_id}",
                    "video_url": diag_url,
                    "render_duration_s": 0,
                    "video_duration_s": diag_dur,
                    "production_score": 3.0,
                    "production_issues": [
                        "DIAGNOSTIC FALLBACK — Remotion unreachable on first submit",
                    ],
                    "segment_count": len(segments),
                    "intelligence": {
                        "complexity": complexity,
                        "estimated_render_s": estimated_render_s,
                    },
                    "fallback": True,
                },
                cost={"cost_usd": 0, "provider": "remotion_diagnostic"},
            )

        render_id = render_data.get("renderId", render_data.get("id", ""))
        if not render_id:
            raise HTTPException(status_code=500, detail="No render ID returned from Remotion")

        logger.info("assembly.render_submitted", render_id=render_id)

        max_wait_s = 600
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
                if not is_test_mode:
                    raise HTTPException(status_code=504, detail="Render timed out after retry")
                logger.warning("assembly.render_timeout_diagnostic_fallback",
                               content_id=req.content_id)
                total_ms = sum(s.get("duration_ms", 0) for s in segments)
                duration_s = round(total_ms / 1000, 1) if total_ms else 8.0
                aspect = direction_v3.get("meta", {}).get("aspect", "16:9")
                diag = await _render_diagnostic_via_remotion(
                    content_id=req.content_id, channel_id=req.channel_id,
                    title=req.title, composition=composition, aspect=aspect,
                    duration_s=duration_s,
                    reason="Render + simplified retry both timed out",
                    remotion_url=remotion_url,
                )
                if diag is None:
                    raise HTTPException(status_code=504,
                                        detail="Render timed out and diagnostic fallback failed")
                diag_url, diag_dur = diag
                try:
                    pool = await get_pool()
                    await pool.execute(
                        "UPDATE videos SET rendered_video_url = $1, "
                        "production_score = $2, status = 'rendered', updated_at = NOW() "
                        "WHERE content_id = $3",
                        diag_url, 3.0, req.content_id,
                    )
                except Exception as db_err:
                    logger.warning("assembly.fallback_db_failed", error=str(db_err))
                return ServiceResponse(
                    status="success",
                    data={
                        "render_id": f"diagnostic-{req.content_id}",
                        "video_url": diag_url,
                        "render_duration_s": 0,
                        "video_duration_s": diag_dur,
                        "production_score": 3.0,
                        "production_issues": [
                            "DIAGNOSTIC FALLBACK — render + simplified retry both timed out",
                        ],
                        "segment_count": len(segments),
                        "fallback": True,
                    },
                    cost={"cost_usd": 0, "provider": "remotion_diagnostic"},
                )

        video_url = render_result.get("outputUrl", render_result.get("url", ""))
        render_duration = render_result.get("renderDuration", 0)

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

        try:
            pool = await get_pool()
            await pool.execute(
                "UPDATE videos SET rendered_video_url = $1, production_score = $2, "
                "status = 'rendered', updated_at = NOW() WHERE content_id = $3",
                video_url, production_score, req.content_id)
        except Exception as e:
            logger.warning("assembly.db_update_failed", error=str(e))

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
