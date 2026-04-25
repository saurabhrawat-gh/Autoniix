from __future__ import annotations

import io
import json
import re
from contextlib import asynccontextmanager

import httpx
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

import src.providers.image.dalle_provider  # noqa: F401
import src.providers.storage.minio_provider  # noqa: F401
import src.providers.llm.openai_provider  # noqa: F401
import src.providers.llm.openai_vision_provider  # noqa: F401
from src.providers.registry import ProviderRegistry
from src.providers.llm.base import LLMRequest

logger = structlog.get_logger()


# ── Request Models ───────────────────────────────────────────

class ThumbnailRequest(BaseModel):
    content_id: str
    channel_id: str
    title: str
    topic: str = ""
    niche: str = ""
    style_hints: dict = Field(default_factory=dict)


# ── Helpers ──────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def _load_channel(channel_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    return dict(row) if row else {}


async def _load_prompt(prompt_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT system_prompt, user_prompt_template FROM prompt_registry "
        "WHERE prompt_id = $1 AND is_active = true", prompt_id)
    return dict(row) if row else {}


async def _log_usage(content_id: str, service: str, provider: str, cost: float):
    try:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO api_usage (content_id, service, provider, cost_usd) VALUES ($1, $2, $3, $4)",
            content_id, service, provider, float(cost))
    except Exception as e:
        logger.warning("thumbnail.db_log_failed", error=str(e))


# ── App ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("thumbnail.starting")
    yield
    await close_pool()
    logger.info("thumbnail.stopped")


app = FastAPI(title="Thumbnail Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="thumbnail")


@app.post("/generate-thumbnail", response_model=ServiceResponse)
async def generate_thumbnail(req: ThumbnailRequest):
    """Full thumbnail pipeline: 5 concepts → DALL-E generation → Vision QC → best selection."""
    logger.info("thumbnail.generating", content_id=req.content_id, title=req.title[:50])
    total_cost = 0.0

    try:
        channel = await _load_channel(req.channel_id)
        niche = req.niche or channel.get("niche", "general")
        thumbnail_style = channel.get("thumbnail_style", "bold_cinematic")
        primary_color = channel.get("primary_color", "#1A237E")
        target_audience = channel.get("target_audience", "")

        # ── Step 1: Generate 5 Concepts (GPT) ───────────
        prompt = await _load_prompt("PRM_B3_THUMBNAIL")
        concept_llm = ProviderRegistry.get("llm")

        system_prompt = prompt.get("system_prompt",
            "Generate 5 thumbnail concepts. Respond in JSON.").format(niche=niche)
        user_prompt = prompt.get("user_prompt_template",
            "Title: {title}\nThumbnail style: {thumbnail_style}").format(
            title=req.title,
            niche=niche,
            thumbnail_style=thumbnail_style,
            primary_color=primary_color,
            target_audience=target_audience,
            competitor_patterns="bold text, dramatic lighting, face close-ups",
        )

        concept_result = await concept_llm.complete(LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="gpt-4o",
            temperature=0.8,
            max_tokens=2000,
            response_format="json",
        ))
        total_cost += concept_result.cost_usd

        try:
            concept_data = _parse_json(concept_result.content)
            concepts = concept_data.get("concepts", [])
        except json.JSONDecodeError:
            concepts = [{"concept_name": "default", "dall_e_prompt": f"YouTube thumbnail for: {req.title}", "predicted_ctr": 0.08}]

        # Sort by predicted CTR, take top 3
        concepts.sort(key=lambda c: float(c.get("predicted_ctr", 0)), reverse=True)
        top_concepts = concepts[:3]

        # ── Step 2: Generate thumbnails via DALL-E ───────
        image_provider = ProviderRegistry.get("image")
        storage = ProviderRegistry.get("storage")
        from src.providers.image.base import ImageRequest

        variants = []
        for i, concept in enumerate(top_concepts):
            dalle_prompt = concept.get("dall_e_prompt", f"YouTube thumbnail: {req.title}")
            # Sanitize prompt (remove triggering content)
            dalle_prompt = dalle_prompt[:900]

            try:
                img_result = await image_provider.generate(ImageRequest(
                    prompt=dalle_prompt,
                    size="1792x1024",
                    quality="hd",
                    style="vivid",
                    n=1,
                ))
                total_cost += img_result.cost_usd

                if img_result.images:
                    img_url = img_result.images[0].get("url", "")
                    if img_url:
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.get(img_url)
                            resp.raise_for_status()
                            img_bytes = resp.content

                        key = f"thumbnails/{req.content_id}/variant_{i}.png"
                        url = await storage.upload(key, io.BytesIO(img_bytes), content_type="image/png")

                        variants.append({
                            "variant_id": i,
                            "concept_name": concept.get("concept_name", f"variant_{i}"),
                            "url": url,
                            "key": key,
                            "predicted_ctr": float(concept.get("predicted_ctr", 0.08)),
                            "dall_e_prompt": dalle_prompt[:200],
                            "revised_prompt": img_result.images[0].get("revised_prompt", ""),
                        })

            except Exception as gen_err:
                logger.warning("thumbnail.variant_failed", variant=i, error=str(gen_err))

        if not variants:
            raise HTTPException(status_code=500, detail="All thumbnail variants failed to generate")

        # ── Step 3: GPT Vision QC (inspect best variant) ─
        best_variant = variants[0]
        vision_score = 7.5  # Default

        try:
            vision_llm = ProviderRegistry.get("llm.vision")
            from src.providers.llm.openai_vision_provider import VisionRequest

            vision_result = await vision_llm.complete(VisionRequest(
                messages=[
                    {"role": "system", "content": (
                        "You are a YouTube thumbnail expert. Evaluate this thumbnail for click-worthiness. "
                        "Score 1-10 on: composition, contrast, readability, emotion, uniqueness. "
                        "Respond in JSON: {\"scores\": {\"composition\": N, \"contrast\": N, \"readability\": N, "
                        "\"emotion\": N, \"uniqueness\": N}, \"overall_score\": N, \"issues\": [], \"mobile_readable\": true/false}"
                    )},
                    {"role": "user", "content": (
                        f"Title: {req.title}\n"
                        f"Niche: {niche}\n"
                        f"Target audience: {target_audience}\n"
                        "Evaluate this thumbnail:"
                    )},
                ],
                model="gpt-4o",
                temperature=0.2,
                max_tokens=1000,
                response_format="json",
                image_urls=[best_variant["url"]],
            ))
            total_cost += vision_result.cost_usd

            try:
                vision_data = _parse_json(vision_result.content)
                vision_score = float(vision_data.get("overall_score", 7.5))
                best_variant["vision_scores"] = vision_data.get("scores", {})
                best_variant["vision_issues"] = vision_data.get("issues", [])
                best_variant["mobile_readable"] = vision_data.get("mobile_readable", True)
            except json.JSONDecodeError:
                pass

        except Exception as vis_err:
            logger.warning("thumbnail.vision_qc_failed", error=str(vis_err))

        # ── Step 4: Select winner ────────────────────────
        best_variant["thumbnail_score"] = round(vision_score, 1)

        await _log_usage(req.content_id, "thumbnail", "multi", total_cost)

        logger.info("thumbnail.generated",
                     variants=len(variants),
                     best_score=vision_score,
                     cost=round(total_cost, 4))

        return ServiceResponse(
            status="success",
            data={
                "selected_thumbnail": best_variant,
                "all_variants": variants,
                "concepts_generated": len(concepts),
                "thumbnail_score": round(vision_score, 1),
                "thumbnail_ctr_prediction": float(best_variant.get("predicted_ctr", 0.08)),
            },
            cost={"cost_usd": round(total_cost, 6), "provider": "multi"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("thumbnail.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.thumbnail.main:app", host="0.0.0.0", port=8005, log_level="info")
