from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager

import httpx
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import providers.boot  # noqa: F401
from core.db import close_pool, get_pool
from observability.metrics import instrument_app
from providers.llm.base import LLMRequest
from providers.registry import ProviderRegistry
from providers.storage.base import StorageUpload
from schemas.common import HealthResponse, ServiceResponse
from services_api.thumbnail.composition_analyzer import analyze_composition
from services_api.thumbnail.ctr_predictor import (
    extract_thumbnail_features,
    ingest_ctr_outcome,
    predict_ctr,
    train_ctr_model,
)

logger = structlog.get_logger()


class ThumbnailRequest(BaseModel):
    content_id: str
    channel_id: str
    title: str
    topic: str = ""
    niche: str = ""
    style_hints: dict = Field(default_factory=dict)


def _safe_format(template: str, **kwargs) -> str:
    """Replace {key} placeholders without failing on unknown/literal braces."""
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template


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
        "SELECT system_prompt, user_prompt_template FROM prompt_registry WHERE prompt_id = $1 AND is_active = true",
        prompt_id,
    )
    return dict(row) if row else {}


async def _log_usage(content_id: str, service: str, provider: str, cost: float):
    try:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO api_usage (content_id, service, provider, cost_usd) VALUES ($1, $2, $3, $4)",
            content_id,
            service,
            provider,
            float(cost),
        )
    except Exception as e:
        logger.warning("thumbnail.db_log_failed", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("thumbnail.starting")
    yield
    await close_pool()
    logger.info("thumbnail.stopped")


from observability.sentry import init_sentry

init_sentry("thumbnail")

app = FastAPI(title="Thumbnail Service", version="0.1.0", lifespan=lifespan)


instrument_app(app, service_name="thumbnail")


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

        prompt = await _load_prompt("PRM_B3_THUMBNAIL")
        concept_llm = ProviderRegistry.get("llm")

        system_prompt = _safe_format(
            prompt.get("system_prompt", "Generate 5 thumbnail concepts. Respond in JSON."), niche=niche
        )
        user_prompt = _safe_format(
            prompt.get("user_prompt_template", "Title: {title}\nThumbnail style: {thumbnail_style}"),
            title=req.title,
            niche=niche,
            thumbnail_style=thumbnail_style,
            primary_color=primary_color,
            target_audience=target_audience,
            competitor_patterns="bold text, dramatic lighting, face close-ups",
        )

        concept_result = await concept_llm.complete(
            LLMRequest(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="gpt-4o",
                temperature=0.8,
                max_tokens=2000,
                response_format="json",
            )
        )
        total_cost += concept_result.cost_usd

        try:
            concept_data = _parse_json(concept_result.content)
            concepts = concept_data.get("concepts", [])
        except json.JSONDecodeError:
            concepts = [
                {
                    "concept_name": "default",
                    "dall_e_prompt": f"YouTube thumbnail for: {req.title}",
                    "predicted_ctr": 0.08,
                }
            ]

        concepts.sort(key=lambda c: float(c.get("predicted_ctr", 0)), reverse=True)
        top_concepts = concepts[:3]

        image_provider = ProviderRegistry.get("image")
        storage = ProviderRegistry.get("storage")
        from providers.image.base import ImageRequest

        variants = []
        for i, concept in enumerate(top_concepts):
            dalle_prompt = concept.get("dall_e_prompt", f"YouTube thumbnail: {req.title}")
            dalle_prompt = dalle_prompt[:1500]

            try:
                img_result = await image_provider.generate(
                    ImageRequest(
                        prompt=dalle_prompt,
                        size="1792x1024",
                        quality="hd",
                        style="vivid",
                        n=1,
                    )
                )
                total_cost += img_result.cost_usd

                if img_result.images:
                    img_data = img_result.images[0]
                    img_bytes = img_data.get("_bytes")
                    if not img_bytes:
                        img_url = img_data.get("url", "")
                        if not img_url or img_url.startswith("data:"):
                            continue
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.get(img_url)
                            resp.raise_for_status()
                            img_bytes = resp.content

                    if img_bytes:
                        key = f"thumbnails/{req.content_id}/variant_{i}.png"
                        sr = await storage.upload(StorageUpload(key=key, data=img_bytes, content_type="image/png"))
                        url = sr.url

                        variants.append(
                            {
                                "variant_id": i,
                                "concept_name": concept.get("concept_name", f"variant_{i}"),
                                "url": url,
                                "key": key,
                                "predicted_ctr": float(concept.get("predicted_ctr", 0.08)),
                                "text_overlay": concept.get("text_overlay", ""),
                                "text_style": concept.get("text_style", {}),
                                "composition_rule": concept.get("composition_rule", ""),
                                "emotion_trigger": concept.get("emotion_trigger", ""),
                                "dall_e_prompt": dalle_prompt[:500],
                                "revised_prompt": img_result.images[0].get("revised_prompt", ""),
                            }
                        )

            except Exception as gen_err:
                logger.warning("thumbnail.variant_failed", variant=i, error=str(gen_err))

        if not variants:
            try:
                fallback_prompt = f"YouTube thumbnail: {req.title} [TEST FALLBACK]"
                img_result = await image_provider.generate(
                    ImageRequest(
                        prompt=fallback_prompt,
                        size="1280x720",
                        quality="hd",
                        style="vivid",
                        n=1,
                    )
                )
                if img_result.images:
                    img_data = img_result.images[0]
                    img_bytes = img_data.get("_bytes")
                    if not img_bytes:
                        img_url = img_data.get("url", "")
                        if img_url and not img_url.startswith("data:"):
                            async with httpx.AsyncClient(timeout=30.0) as client:
                                resp = await client.get(img_url)
                                resp.raise_for_status()
                                img_bytes = resp.content
                    if img_bytes:
                        key = f"thumbnails/{req.content_id}/variant_fallback.png"
                        sr = await storage.upload(StorageUpload(key=key, data=img_bytes, content_type="image/png"))
                        variants.append(
                            {
                                "variant_id": 0,
                                "concept_name": "fallback",
                                "url": sr.url,
                                "key": key,
                                "predicted_ctr": 0.10,
                                "text_overlay": "",
                                "text_style": {},
                                "composition_rule": "",
                                "emotion_trigger": "",
                                "dall_e_prompt": fallback_prompt[:500],
                                "revised_prompt": img_data.get("revised_prompt", ""),
                            }
                        )
            except Exception as fb_err:
                logger.warning("thumbnail.fallback_failed", error=str(fb_err))

        if not variants:
            raise HTTPException(status_code=500, detail="All thumbnail variants failed to generate")

        local_qc_skip_threshold = 8.5
        try:
            _thresh = await _load_config("thumb_local_qc_skip_threshold")
            if _thresh:
                local_qc_skip_threshold = float(_thresh)
        except Exception:
            pass

        for variant in variants:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(variant["url"])
                    resp.raise_for_status()
                    img_bytes = resp.content

                composition = await analyze_composition(img_bytes)
                variant["local_composition"] = composition
                variant["local_score"] = composition.get("composition_score", 5.0)

                await extract_thumbnail_features(
                    req.content_id,
                    req.channel_id,
                    composition,
                    variant_id=variant.get("variant_id", 0),
                    text_overlay=variant.get("text_overlay", ""),
                )

                ml_ctr = await predict_ctr(composition.get("features", {}), niche)
                if ml_ctr is not None:
                    variant["ml_predicted_ctr"] = ml_ctr

            except Exception as comp_err:
                logger.warning(
                    "thumbnail.local_analysis_failed", variant=variant.get("variant_id"), error=str(comp_err)
                )
                variant["local_score"] = 5.0

        vision_llm = None
        try:
            vision_llm = ProviderRegistry.get("llm.vision")
        except Exception as vis_err:
            logger.warning("thumbnail.vision_provider_unavailable", error=str(vis_err))

        if vision_llm:
            from providers.llm.openai_vision_provider import VisionRequest

            for variant in variants:
                if variant.get("local_score", 0) >= local_qc_skip_threshold:
                    variant["thumbnail_score"] = variant["local_score"]
                    variant["vision_skipped"] = True
                    logger.info(
                        "thumbnail.vision_skipped",
                        variant=variant.get("variant_id"),
                        local_score=variant["local_score"],
                    )
                    continue

                try:
                    vision_result = await vision_llm.complete(
                        VisionRequest(
                            messages=[
                                {
                                    "role": "system",
                                    "content": (
                                        "You are a ruthless YouTube thumbnail critic. You rarely give scores above 7. "
                                        "A score of 9+ means this thumbnail would outperform 95% of YouTube thumbnails in this niche.\n\n"
                                        "Score 1-10 on each dimension:\n"
                                        "- composition: Rule of thirds? Visual hierarchy? Clear focal point?\n"
                                        "- contrast: Do colors pop? Is there enough contrast between elements?\n"
                                        "- readability: Can text be read at phone screen size (small thumbnail)?\n"
                                        "- emotion: Does this trigger an emotional click response (curiosity, fear, surprise)?\n"
                                        "- uniqueness: Would this stand out in a feed of similar niche videos?\n"
                                        "- click_worthiness: Would YOU click this thumbnail?\n\n"
                                        "Calibration: 4=generic stock photo, 6=decent but forgettable, 8=professional, 9=would stop scrolling\n\n"
                                        'Respond in JSON: {"scores": {"composition": N, "contrast": N, "readability": N, '
                                        '"emotion": N, "uniqueness": N, "click_worthiness": N}, "overall_score": N, '
                                        '"issues": [], "mobile_readable": true/false, "improvement_suggestions": []}'
                                    ),
                                },
                                {
                                    "role": "user",
                                    "content": (
                                        f"Title: {req.title}\n"
                                        f"Niche: {niche}\n"
                                        f"Target audience: {target_audience}\n"
                                        f"Text overlay: {variant.get('text_overlay', 'none')}\n"
                                        "Evaluate this thumbnail:"
                                    ),
                                },
                            ],
                            model="gpt-4o",
                            temperature=0.2,
                            max_tokens=1000,
                            response_format="json",
                            image_urls=[variant["url"]],
                        )
                    )
                    total_cost += vision_result.cost_usd

                    try:
                        vision_data = _parse_json(vision_result.content)
                        variant["vision_scores"] = vision_data.get("scores", {})
                        variant["vision_issues"] = vision_data.get("issues", [])
                        variant["mobile_readable"] = vision_data.get("mobile_readable", True)
                        variant["thumbnail_score"] = float(vision_data.get("overall_score", 7.0))
                        variant["improvement_suggestions"] = vision_data.get("improvement_suggestions", [])
                    except json.JSONDecodeError:
                        variant["thumbnail_score"] = 7.0

                except Exception as vis_err:
                    logger.warning("thumbnail.vision_qc_failed", variant=variant.get("variant_id"), error=str(vis_err))
                    variant["thumbnail_score"] = 7.0
        else:
            for variant in variants:
                variant["thumbnail_score"] = float(variant.get("predicted_ctr", 0.08)) * 100

        variants.sort(key=lambda v: v.get("thumbnail_score", 0), reverse=True)
        best_variant = variants[0]
        best_score = best_variant.get("thumbnail_score", 7.0)

        regen_count = 0
        target_thumb_score = 9.0
        while best_score < target_thumb_score and regen_count < 2:
            regen_count += 1
            logger.info(
                "thumbnail.regenerating", attempt=regen_count, current_score=best_score, target=target_thumb_score
            )

            regen_issues = best_variant.get("vision_issues", []) + best_variant.get("improvement_suggestions", [])
            regen_system = _safe_format(
                prompt.get("system_prompt", "Generate 5 thumbnail concepts. Respond in JSON."), niche=niche
            )
            regen_user = (
                f"REGENERATE thumbnail concepts. Previous best scored {best_score}/10.\n"
                f"Issues to fix: {json.dumps(regen_issues)}\n"
                f"Title: {req.title}\n"
                f"Niche: {niche}\n"
                f"Thumbnail style: {thumbnail_style}\n"
                f"Primary color: {primary_color}\n"
                f"Target audience: {target_audience}\n"
                f"MAKE DALL-E PROMPTS MORE DETAILED (200+ words). Fix all issues above.\n"
                f"Competitor patterns: bold text, dramatic lighting, face close-ups"
            )

            regen_result = await concept_llm.complete(
                LLMRequest(
                    messages=[
                        {"role": "system", "content": regen_system},
                        {"role": "user", "content": regen_user},
                    ],
                    model="gpt-4o",
                    temperature=0.9,
                    max_tokens=2000,
                    response_format="json",
                )
            )
            total_cost += regen_result.cost_usd

            try:
                regen_data = _parse_json(regen_result.content)
                regen_concepts = regen_data.get("concepts", [])
            except json.JSONDecodeError:
                break

            if not regen_concepts:
                break

            regen_concepts.sort(key=lambda c: float(c.get("predicted_ctr", 0)), reverse=True)
            regen_concept = regen_concepts[0]
            regen_prompt_text = regen_concept.get("dall_e_prompt", f"YouTube thumbnail: {req.title}")[:1500]

            try:
                regen_img = await image_provider.generate(
                    ImageRequest(
                        prompt=regen_prompt_text,
                        size="1792x1024",
                        quality="hd",
                        style="vivid",
                        n=1,
                    )
                )
                total_cost += regen_img.cost_usd

                if regen_img.images:
                    regen_data = regen_img.images[0]
                    img_bytes = regen_data.get("_bytes")
                    if not img_bytes:
                        img_url = regen_data.get("url", "")
                        if img_url and not img_url.startswith("data:"):
                            async with httpx.AsyncClient(timeout=30.0) as client:
                                resp = await client.get(img_url)
                                resp.raise_for_status()
                                img_bytes = resp.content

                    if img_bytes:
                        key = f"thumbnails/{req.content_id}/regen_{regen_count}.png"
                        sr = await storage.upload(StorageUpload(key=key, data=img_bytes, content_type="image/png"))
                        regen_url = sr.url

                        regen_variant = {
                            "variant_id": len(variants),
                            "concept_name": regen_concept.get("concept_name", f"regen_{regen_count}"),
                            "url": regen_url,
                            "key": key,
                            "predicted_ctr": float(regen_concept.get("predicted_ctr", 0.08)),
                            "text_overlay": regen_concept.get("text_overlay", ""),
                            "text_style": regen_concept.get("text_style", {}),
                            "composition_rule": regen_concept.get("composition_rule", ""),
                            "emotion_trigger": regen_concept.get("emotion_trigger", ""),
                            "dall_e_prompt": regen_prompt_text[:500],
                            "regenerated": True,
                        }

                        if vision_llm:
                            try:
                                from providers.llm.openai_vision_provider import VisionRequest

                                v_res = await vision_llm.complete(
                                    VisionRequest(
                                        messages=[
                                            {
                                                "role": "system",
                                                "content": (
                                                    "Score this YouTube thumbnail 1-10. Calibration: 6=decent, 8=professional, 9=exceptional. "
                                                    'Respond in JSON: {"overall_score": N, "scores": {}, "issues": [], "mobile_readable": true/false}'
                                                ),
                                            },
                                            {
                                                "role": "user",
                                                "content": f"Title: {req.title}\nNiche: {niche}\nEvaluate:",
                                            },
                                        ],
                                        model="gpt-4o",
                                        temperature=0.2,
                                        max_tokens=800,
                                        response_format="json",
                                        image_urls=[regen_url],
                                    )
                                )
                                total_cost += v_res.cost_usd
                                v_data = _parse_json(v_res.content)
                                regen_variant["thumbnail_score"] = float(v_data.get("overall_score", 7.0))
                                regen_variant["vision_scores"] = v_data.get("scores", {})
                                regen_variant["vision_issues"] = v_data.get("issues", [])
                            except Exception:
                                regen_variant["thumbnail_score"] = 7.0

                        variants.append(regen_variant)

                        if regen_variant.get("thumbnail_score", 0) > best_score:
                            best_variant = regen_variant
                            best_score = regen_variant["thumbnail_score"]

            except Exception as regen_err:
                logger.warning("thumbnail.regen_failed", attempt=regen_count, error=str(regen_err))
                break

        best_variant["thumbnail_score"] = round(best_score, 1)

        await _log_usage(req.content_id, "thumbnail", "multi", total_cost)

        logger.info(
            "thumbnail.generated",
            variants=len(variants),
            best_score=best_score,
            regenerations=regen_count,
            cost=round(total_cost, 4),
        )

        vision_skipped_count = sum(1 for v in variants if v.get("vision_skipped"))

        return ServiceResponse(
            status="success",
            data={
                "selected_thumbnail": best_variant,
                "all_variants": variants,
                "concepts_generated": len(concepts),
                "regeneration_count": regen_count,
                "thumbnail_score": round(best_score, 1),
                "thumbnail_ctr_prediction": float(best_variant.get("predicted_ctr", 0.08)),
                "intelligence": {
                    "local_composition_scores": [
                        {"variant": v.get("variant_id"), "score": v.get("local_score", 0)} for v in variants
                    ],
                    "ml_ctr_predictions": [
                        {"variant": v.get("variant_id"), "ctr": v.get("ml_predicted_ctr")}
                        for v in variants
                        if v.get("ml_predicted_ctr") is not None
                    ],
                    "vision_calls_skipped": vision_skipped_count,
                    "vision_cost_saved": vision_skipped_count > 0,
                },
            },
            cost={"cost_usd": round(total_cost, 6), "provider": "multi"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("thumbnail.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


class ThumbnailFeedbackRequest(BaseModel):
    content_id: str
    channel_id: str
    actual_ctr: float
    impressions: int = 0


class ThumbnailTrainRequest(BaseModel):
    niche: str


@app.post("/thumbnail-feedback", response_model=ServiceResponse)
async def thumbnail_feedback(req: ThumbnailFeedbackRequest):
    """Ingest actual CTR data for thumbnail ML learning."""
    ok = await ingest_ctr_outcome(req.content_id, req.channel_id, req.actual_ctr, req.impressions)
    return ServiceResponse(status="success" if ok else "failed", data={"ingested": ok})


@app.post("/thumbnail-train", response_model=ServiceResponse)
async def thumbnail_train(req: ThumbnailTrainRequest):
    """Train/retrain thumbnail CTR prediction model."""
    result = await train_ctr_model(req.niche)
    return ServiceResponse(status="success", data=result)


async def _load_config(key: str) -> str:
    try:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT config_value FROM system_config WHERE config_key = $1", key)
        return row["config_value"] if row else ""
    except Exception:
        return ""


if __name__ == "__main__":
    uvicorn.run("services_api.thumbnail.main:app", host="0.0.0.0", port=8005, log_level="info")
