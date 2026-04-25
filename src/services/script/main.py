from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

import src.providers.llm.openai_provider  # noqa: F401
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()


# ── Request / Response Models ────────────────────────────────

class ScriptRequest(BaseModel):
    channel_id: str
    content_mode: str = "long_form"
    topic: str
    title: str = ""
    research_data: dict = Field(default_factory=dict)
    budget_guard: dict = Field(default_factory=lambda: {"max_cost_usd": 2.50, "accrued_cost_usd": 0.0})


class TitleRequest(BaseModel):
    channel_id: str
    topic: str
    niche: str = ""
    count: int = 5


# ── App ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("script.starting")
    yield
    await close_pool()
    logger.info("script.stopped")


app = FastAPI(title="Script Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="script")


@app.post("/generate-titles", response_model=ServiceResponse)
async def generate_titles(req: TitleRequest):
    llm = ProviderRegistry.get("llm")
    from src.providers.llm.base import LLMRequest

    result = await llm.complete(LLMRequest(
        messages=[
            {"role": "system", "content": (
                "You are a YouTube title expert. Generate click-worthy, accurate titles. "
                "Respond in JSON: {\"titles\": [\"title1\", ...]}."
            )},
            {"role": "user", "content": f"Topic: {req.topic}\nNiche: {req.niche}\nGenerate {req.count} titles."},
        ],
        temperature=0.8,
        max_tokens=500,
        response_format="json",
    ))

    try:
        data = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", result.content.strip()))
    except json.JSONDecodeError:
        data = {"titles": [req.topic]}

    return ServiceResponse(
        status="success",
        data=data,
        cost={"cost_usd": result.cost_usd, "provider": result.provider},
    )


SCRIPT_SYSTEM_PROMPT = """You are a world-class YouTube scriptwriter. Generate a complete video script.

Output STRICTLY valid JSON with this structure:
{
  "title": "Final video title",
  "hook": "Opening hook (first 5 seconds)",
  "segments": [
    {
      "id": "s1",
      "section": "hook|intro|body|climax|outro",
      "narration": "Exact words the narrator says",
      "duration_s": 30,
      "scene_direction": "Visual description for the video editor",
      "asset_suggestions": ["search term for stock footage or image"],
      "b_roll_keywords": ["keyword1", "keyword2"],
      "text_overlay": "Optional text to show on screen",
      "transition": "cut|dissolve|slide"
    }
  ],
  "total_duration_s": 480,
  "word_count": 1100,
  "tags": ["tag1", "tag2", "tag3"],
  "description": "YouTube video description (2-3 paragraphs)"
}

Rules:
- Long-form: ~8 min (480s), ~1100 words, 8-12 segments
- Short-form: ~45s, ~80 words, 3-4 segments
- Hook must be attention-grabbing in first 5 seconds
- Each segment has clear visual direction
- Include pattern interrupts every 60-90 seconds
- End with a strong CTA"""


@app.post("/generate-script", response_model=ServiceResponse)
async def generate_script(req: ScriptRequest):
    logger.info("script.generating", channel_id=req.channel_id, topic=req.topic)

    llm = ProviderRegistry.get("llm")
    from src.providers.llm.base import LLMRequest

    duration_hint = "8 minutes (~1100 words)" if req.content_mode == "long_form" else "45 seconds (~80 words)"
    research_context = json.dumps(req.research_data, indent=2)[:3000] if req.research_data else "No research data."

    result = await llm.complete(LLMRequest(
        messages=[
            {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Channel: {req.channel_id}\n"
                f"Topic: {req.topic}\n"
                f"Title suggestion: {req.title or 'Generate one'}\n"
                f"Target duration: {duration_hint}\n"
                f"Content mode: {req.content_mode}\n\n"
                f"Research data:\n{research_context}"
            )},
        ],
        temperature=0.7,
        max_tokens=4000,
        response_format="json",
    ))

    try:
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", result.content.strip())
        script_data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="LLM returned invalid JSON for script")

    # Log usage
    try:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO api_usage (content_id, service, provider, model, tokens_in, tokens_out, cost_usd, latency_ms) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            f"script-{req.channel_id}",
            "script",
            result.provider,
            result.model,
            result.tokens_in,
            result.tokens_out,
            float(result.cost_usd),
            result.latency_ms,
        )
    except Exception as e:
        logger.warning("script.db_log_failed", error=str(e))

    logger.info("script.generated", segments=len(script_data.get("segments", [])), cost=result.cost_usd)

    return ServiceResponse(
        status="success",
        data=script_data,
        cost={"cost_usd": result.cost_usd, "provider": result.provider},
    )


if __name__ == "__main__":
    uvicorn.run("src.services.script.main:app", host="0.0.0.0", port=8002, log_level="info")
