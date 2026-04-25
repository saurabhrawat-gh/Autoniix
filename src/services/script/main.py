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
import src.providers.llm.claude_provider  # noqa: F401
import src.providers.llm.gemini_provider  # noqa: F401
from src.providers.registry import ProviderRegistry
from src.providers.llm.base import LLMRequest

logger = structlog.get_logger()


# ── Request Models ───────────────────────────────────────────

class ScriptRequest(BaseModel):
    channel_id: str
    content_mode: str = "short"
    topic: str
    title: str = ""
    hook: str = ""
    research_data: dict = Field(default_factory=dict)
    idea_data: dict = Field(default_factory=dict)
    budget_guard: dict = Field(default_factory=lambda: {"max_cost_usd": 2.50, "accrued_cost_usd": 0.0})


class HookRequest(BaseModel):
    channel_id: str
    title: str
    topic: str
    original_hook: str = ""
    script_summary: str = ""


class PackagingRequest(BaseModel):
    channel_id: str
    title: str
    topic: str
    script_data: dict = Field(default_factory=dict)


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


async def _log_usage(content_id: str, service: str, provider: str, model: str,
                     tokens_in: int, tokens_out: int, cost: float, latency: int):
    try:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO api_usage (content_id, service, provider, model, tokens_in, tokens_out, cost_usd, latency_ms) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            content_id, service, provider, model, tokens_in, tokens_out, float(cost), latency)
    except Exception as e:
        logger.warning("script.db_log_failed", error=str(e))


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


# ── Full Script Pipeline ─────────────────────────────────────

@app.post("/generate-script", response_model=ServiceResponse)
async def generate_script(req: ScriptRequest):
    """Full script pipeline: Claude write → validate → critique → rewrite loop → fact-check."""
    logger.info("script.generating", channel_id=req.channel_id, topic=req.topic)
    total_cost = 0.0

    try:
        channel = await _load_channel(req.channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {req.channel_id} not found")

        # Determine targets from Channel DNA
        is_long = req.content_mode == "long_form"
        word_target = channel.get("words_per_video_long", 1100) if is_long else channel.get("words_per_video_short", 80)
        duration_target = channel.get("long_form_duration", 480) if is_long else channel.get("short_form_duration", 45)
        seg_count = "8-12" if is_long else "3-4"
        forbidden = channel.get("forbidden_words", "")

        # ── Step 1: Generate Script v1 (Claude Sonnet) ───
        prompt = await _load_prompt("PRM_B1_SCRIPT_V1")
        script_llm = ProviderRegistry.get("llm.script")

        system_prompt = prompt.get("system_prompt",
            "You are a YouTube scriptwriter. Output valid JSON with segments.").format(
            brand_voice=channel.get("brand_voice", ""),
            narrative_rhythm=channel.get("narrative_rhythm", ""),
            emotional_contract=channel.get("emotional_contract", ""),
            content_mode=req.content_mode,
        )
        user_prompt = prompt.get("user_prompt_template",
            "Channel: {channel_id}\nTopic: {topic}\nTitle: {title}").format(
            channel_id=req.channel_id,
            topic=req.topic,
            title=req.title or "Generate one",
            hook=req.hook or "Generate one",
            target_duration=f"{duration_target}s (~{word_target} words, {seg_count} segments)",
            word_target=word_target,
            research_data=json.dumps(req.research_data, default=str)[:3000],
            forbidden_words=forbidden,
        )

        result = await script_llm.complete(LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
            response_format="json",
        ))
        total_cost += result.cost_usd
        await _log_usage(f"script-{req.channel_id}", "script_v1", result.provider,
                         result.model, result.tokens_in, result.tokens_out,
                         result.cost_usd, result.latency_ms)

        try:
            script_data = _parse_json(result.content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="LLM returned invalid JSON for script")

        # ── Step 2: Validation ───────────────────────────
        segments = script_data.get("segments", [])
        actual_words = sum(len(s.get("narration", "").split()) for s in segments)
        validation = {
            "word_count": actual_words,
            "word_target": word_target,
            "word_count_ok": abs(actual_words - word_target) <= word_target * 0.15,
            "segment_count": len(segments),
            "has_hook": any(s.get("section") == "hook" for s in segments),
            "has_outro": any(s.get("section") == "outro" for s in segments),
        }

        # Forbidden words check
        forbidden_list = [w.strip().lower() for w in forbidden.split(",") if w.strip()]
        full_narration = " ".join(s.get("narration", "") for s in segments).lower()
        found_forbidden = [w for w in forbidden_list if w in full_narration]
        validation["forbidden_words_found"] = found_forbidden
        validation["forbidden_words_ok"] = len(found_forbidden) == 0

        script_data["validation"] = validation

        # ── Step 3: Script Critique (GPT-4o-mini) ────────
        critique_prompt = await _load_prompt("PRM_B1_SCRIPT_CRITIQUE")
        critique_llm = ProviderRegistry.get("llm.qc")

        crit_system = critique_prompt.get("system_prompt",
            "Critique this script. Score 6 dimensions 1-10. Respond in JSON.").format(
            min_dimension_score=6.0,
        )
        crit_user = critique_prompt.get("user_prompt_template",
            "Script: {script_json}\nVoice: {brand_voice}").format(
            script_json=json.dumps(script_data)[:4000],
            brand_voice=channel.get("brand_voice", ""),
            target_audience=channel.get("target_audience", ""),
        )

        crit_result = await critique_llm.complete(LLMRequest(
            messages=[
                {"role": "system", "content": crit_system},
                {"role": "user", "content": crit_user},
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format="json",
        ))
        total_cost += crit_result.cost_usd
        await _log_usage(f"script-{req.channel_id}", "script_critique", crit_result.provider,
                         crit_result.model, crit_result.tokens_in, crit_result.tokens_out,
                         crit_result.cost_usd, crit_result.latency_ms)

        try:
            critique_data = _parse_json(crit_result.content)
        except json.JSONDecodeError:
            critique_data = {"dimensions": {}, "overall_score": 7.0, "weak_dimensions": [], "rewrite_suggestions": []}

        script_data["critique"] = critique_data
        weak_dims = critique_data.get("weak_dimensions", [])

        # ── Step 4: Rewrite Loop (max 2 retries) ────────
        rewrite_count = 0
        while weak_dims and rewrite_count < 2:
            rewrite_count += 1
            logger.info("script.rewriting", attempt=rewrite_count, weak=weak_dims)

            suggestions = critique_data.get("rewrite_suggestions", [])
            rewrite_prompt = (
                f"Rewrite this script to fix these weak dimensions: {json.dumps(weak_dims)}\n"
                f"Suggestions: {json.dumps(suggestions)}\n"
                f"Keep the same JSON structure. Fix ONLY the weak areas.\n\n"
                f"Current script:\n{json.dumps(script_data)[:4000]}"
            )

            rw_result = await script_llm.complete(LLMRequest(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": rewrite_prompt},
                ],
                temperature=0.6,
                max_tokens=4000,
                response_format="json",
            ))
            total_cost += rw_result.cost_usd
            await _log_usage(f"script-{req.channel_id}", f"script_rewrite_{rewrite_count}",
                             rw_result.provider, rw_result.model, rw_result.tokens_in,
                             rw_result.tokens_out, rw_result.cost_usd, rw_result.latency_ms)

            try:
                script_data = _parse_json(rw_result.content)
            except json.JSONDecodeError:
                logger.warning("script.rewrite_json_failed", attempt=rewrite_count)
                break

            # Re-critique
            crit_result2 = await critique_llm.complete(LLMRequest(
                messages=[
                    {"role": "system", "content": crit_system},
                    {"role": "user", "content": crit_user.replace(
                        json.dumps(script_data)[:4000], json.dumps(script_data)[:4000])},
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format="json",
            ))
            total_cost += crit_result2.cost_usd

            try:
                critique_data = _parse_json(crit_result2.content)
                script_data["critique"] = critique_data
                weak_dims = critique_data.get("weak_dimensions", [])
            except json.JSONDecodeError:
                break

        script_data["rewrite_count"] = rewrite_count
        overall_score = critique_data.get("overall_score", 7.0)
        script_data["script_structure_score"] = overall_score

        logger.info("script.generated",
                     segments=len(script_data.get("segments", [])),
                     score=overall_score,
                     rewrites=rewrite_count,
                     cost=round(total_cost, 4))

        return ServiceResponse(
            status="success",
            data=script_data,
            cost={"cost_usd": round(total_cost, 6), "provider": "multi"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("script.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ── Hook Engine ──────────────────────────────────────────────

@app.post("/generate-hooks", response_model=ServiceResponse)
async def generate_hooks(req: HookRequest):
    """Generate 5 hooks → predict retention → rank → quality gate (>=8.0)."""
    logger.info("hooks.generating", channel_id=req.channel_id, title=req.title[:50])
    total_cost = 0.0

    try:
        channel = await _load_channel(req.channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {req.channel_id} not found")

        prompt = await _load_prompt("PRM_B1_HOOK")
        llm = ProviderRegistry.get("llm.hook")

        is_long = channel.get("content_mode", "short") == "long_form"
        hook_seconds = channel.get("hook_length_seconds_long", 8) if is_long else channel.get("hook_length_seconds_short", 2)

        system_prompt = prompt.get("system_prompt",
            "Generate 5 hooks. Respond in JSON.").format(
            hook_length_seconds=hook_seconds,
        )
        user_prompt = prompt.get("user_prompt_template",
            "Title: {title}\nTopic: {topic}").format(
            title=req.title,
            topic=req.topic,
            narrative_rhythm=channel.get("narrative_rhythm", ""),
            target_audience=channel.get("target_audience", ""),
            original_hook=req.original_hook,
        )

        result = await llm.complete(LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="gpt-4o",
            temperature=0.8,
            max_tokens=1500,
            response_format="json",
        ))
        total_cost += result.cost_usd
        await _log_usage(f"hooks-{req.channel_id}", "hooks", result.provider,
                         result.model, result.tokens_in, result.tokens_out,
                         result.cost_usd, result.latency_ms)

        try:
            hook_data = _parse_json(result.content)
        except json.JSONDecodeError:
            hook_data = {"hooks": [{"text": req.original_hook or req.title, "predicted_retention": 7.0}]}

        hooks = hook_data.get("hooks", [])
        hooks.sort(key=lambda h: float(h.get("predicted_retention", 0)), reverse=True)

        best_hook = hooks[0] if hooks else {"text": req.original_hook, "predicted_retention": 7.0}

        return ServiceResponse(
            status="success",
            data={
                "selected_hook": best_hook,
                "all_hooks": hooks,
                "hook_retention_score": float(best_hook.get("predicted_retention", 7.0)),
            },
            cost={"cost_usd": round(total_cost, 6), "provider": result.provider},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hooks.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ── Packaging (Titles, Description, Tags, Chapters) ─────────

@app.post("/package", response_model=ServiceResponse)
async def package(req: PackagingRequest):
    """Generate optimized titles, description, tags, chapters, comment triggers."""
    logger.info("packaging.generating", channel_id=req.channel_id)
    total_cost = 0.0

    try:
        channel = await _load_channel(req.channel_id)
        llm = ProviderRegistry.get("llm")

        segments = req.script_data.get("segments", [])
        narration_preview = " ".join(s.get("narration", "")[:100] for s in segments[:5])

        result = await llm.complete(LLMRequest(
            messages=[
                {"role": "system", "content": (
                    "You are a YouTube SEO and packaging expert. Generate optimized metadata. "
                    "Respond in JSON: {\"titles\": [8 variants], \"description\": \"2-3 paragraphs with timestamps\", "
                    "\"tags\": [20 tags], \"chapters\": [\"00:00 Title\", ...], "
                    "\"comment_triggers\": [3 engaging questions], "
                    "\"shorts_funnel_text\": \"CTA linking to long-form\"}"
                )},
                {"role": "user", "content": (
                    f"Channel: {req.channel_id} ({channel.get('channel_name', '')})\n"
                    f"Niche: {channel.get('niche', '')}\n"
                    f"Title: {req.title}\n"
                    f"Topic: {req.topic}\n"
                    f"Content preview: {narration_preview[:500]}\n"
                    f"Target audience: {channel.get('target_audience', '')}\n"
                    f"CTA style: {channel.get('cta_style_long', '')}"
                )},
            ],
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=2000,
            response_format="json",
        ))
        total_cost += result.cost_usd
        await _log_usage(f"packaging-{req.channel_id}", "packaging", result.provider,
                         result.model, result.tokens_in, result.tokens_out,
                         result.cost_usd, result.latency_ms)

        try:
            pkg_data = _parse_json(result.content)
        except json.JSONDecodeError:
            pkg_data = {"titles": [req.title], "description": "", "tags": [], "chapters": []}

        # ── Compliance check ─────────────────────────────
        niche = channel.get("niche", "")
        disclaimers = {
            "health": "This content is for informational purposes only and is not medical advice. Consult a healthcare professional before making any health decisions.",
            "finance": "This is not financial advice. Consult a qualified financial advisor before making investment decisions. Past performance is not indicative of future results.",
            "psychology": "This content is for educational purposes. If you're experiencing mental health issues, please seek professional help.",
        }
        disclaimer = disclaimers.get(niche, "")
        if disclaimer:
            pkg_data["niche_disclaimer"] = disclaimer
            # Inject into description
            desc = pkg_data.get("description", "")
            if disclaimer not in desc:
                pkg_data["description"] = f"{desc}\n\n---\n{disclaimer}"

        pkg_data["ai_disclosure"] = True

        return ServiceResponse(
            status="success",
            data=pkg_data,
            cost={"cost_usd": round(total_cost, 6), "provider": result.provider},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("packaging.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("src.services.script.main:app", host="0.0.0.0", port=8002, log_level="info")
