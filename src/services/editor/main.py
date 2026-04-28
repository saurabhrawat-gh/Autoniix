"""Editor / Post-Production Service — Final polish before rendering.

Takes direction v3, applies:
1. Timeline optimization (pacing adjustments)
2. Transition smoothing
3. Caption generation (word-level for Remotion)
4. Audio mix configuration
5. Final QC brain

Intelligence cost: $0.00 — all local computation.
Port: 8013
"""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

from src.services.editor.timeline_optimizer import (
    analyze_pacing,
    optimize_transitions,
    apply_pacing_adjustments,
    apply_transition_changes,
)
from src.services.editor.caption_generator import (
    generate_captions,
    generate_audio_mix_config,
)
from src.services.editor.final_qc import run_final_qc

logger = structlog.get_logger()


# ── Request Models ───────────────────────────────────────────

class EditorRequest(BaseModel):
    content_id: str
    channel_id: str
    direction_v3: dict = Field(default_factory=dict)
    caption_style: str = ""
    apply_pacing: bool = True
    apply_transitions: bool = True
    generate_captions_flag: bool = True


# ── Helpers ──────────────────────────────────────────────────

async def _load_channel(channel_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    return dict(row) if row else {}


async def _load_config(key: str) -> str:
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = $1", key)
        return row["config_value"] if row else ""
    except Exception:
        return ""


# ── App ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("editor.starting")
    yield
    await close_pool()
    logger.info("editor.stopped")


app = FastAPI(title="Editor Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="editor")


@app.post("/post-produce", response_model=ServiceResponse)
async def post_produce(req: EditorRequest):
    """Full post-production pipeline: pacing → transitions → captions → audio mix → QC."""
    logger.info("editor.post_producing", content_id=req.content_id,
                 segments=len(req.direction_v3.get("segments", [])))
    start_time = time.time()

    try:
        direction_v3 = req.direction_v3
        if not direction_v3 or not direction_v3.get("segments"):
            raise HTTPException(status_code=400, detail="No direction_v3 data provided")

        channel = await _load_channel(req.channel_id)
        caption_style = req.caption_style or channel.get("caption_style", "word_highlight")
        duck_db = float(await _load_config("editor_music_duck_db") or "-12")

        pre_score = 0.0
        total_adjustments = 0
        pacing_result = {}
        transition_result = {}
        captions = {}
        audio_mix = {}

        # ── Step 1: Analyze pacing ─────────────────────────
        pacing_analysis = analyze_pacing(direction_v3)
        pre_score = pacing_analysis.get("pacing_score", 7.0)

        # ── Step 2: Apply pacing adjustments ───────────────
        if req.apply_pacing and pacing_analysis.get("adjustments"):
            pacing_result = apply_pacing_adjustments(
                direction_v3, pacing_analysis["adjustments"], apply_high_only=True)
            direction_v3 = pacing_result.get("direction_v3", direction_v3)
            total_adjustments += pacing_result.get("applied", 0)

        # ── Step 3: Optimize transitions ───────────────────
        transition_analysis = optimize_transitions(direction_v3)

        if req.apply_transitions and transition_analysis.get("changes"):
            transition_result = apply_transition_changes(
                direction_v3, transition_analysis["changes"])
            total_adjustments += transition_result.get("applied", 0)

        # ── Step 4: Generate captions ──────────────────────
        if req.generate_captions_flag:
            captions = generate_captions(direction_v3, caption_style)
            # Inject caption data into direction_v3
            direction_v3["captions"] = captions

        # ── Step 5: Audio mix config ───────────────────────
        audio_mix = generate_audio_mix_config(direction_v3, duck_db=duck_db)
        direction_v3["audio_mix_config"] = audio_mix

        # ── Step 6: Final QC ──────────────────────────────
        qc_result = run_final_qc(direction_v3, captions=captions, audio_mix=audio_mix)
        post_score = qc_result.get("score", 7.0)

        direction_v3["editor_qc"] = qc_result
        direction_v3["editor_applied"] = True

        # ── Step 7: Store session ──────────────────────────
        edit_time_ms = int((time.time() - start_time) * 1000)
        try:
            pool = await get_pool()
            await pool.execute("""
                INSERT INTO editor_sessions (content_id, channel_id,
                    pacing_adjustments, transition_changes, audio_mix_config,
                    captions_generated, caption_word_count,
                    pre_edit_score, post_edit_score, total_adjustments, edit_time_ms)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
                req.content_id, req.channel_id,
                json.dumps(pacing_analysis.get("adjustments", [])),
                json.dumps(transition_analysis.get("changes", [])),
                json.dumps(audio_mix),
                req.generate_captions_flag,
                captions.get("total_words", 0),
                pre_score, post_score, total_adjustments, edit_time_ms,
            )
        except Exception as e:
            logger.warning("editor.db_store_failed", error=str(e))

        logger.info("editor.completed",
                     pre_score=pre_score, post_score=post_score,
                     adjustments=total_adjustments,
                     captions=captions.get("total_words", 0),
                     time_ms=edit_time_ms)

        return ServiceResponse(
            status="success",
            data={
                "direction_v3": direction_v3,
                "pacing_analysis": {
                    "score": pacing_analysis.get("pacing_score"),
                    "adjustments_count": len(pacing_analysis.get("adjustments", [])),
                    "applied": pacing_result.get("applied", 0),
                },
                "transition_analysis": {
                    "score": transition_analysis.get("transition_score"),
                    "changes_count": len(transition_analysis.get("changes", [])),
                    "applied": transition_result.get("applied", 0),
                },
                "captions": {
                    "style": caption_style,
                    "total_words": captions.get("total_words", 0),
                    "total_lines": captions.get("total_lines", 0),
                },
                "qc": qc_result,
                "pre_edit_score": round(pre_score, 1),
                "post_edit_score": round(post_score, 1),
                "total_adjustments": total_adjustments,
                "edit_time_ms": edit_time_ms,
            },
            cost={"cost_usd": 0, "provider": "local"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("editor.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.editor.main:app", host="0.0.0.0", port=8013, log_level="info")
