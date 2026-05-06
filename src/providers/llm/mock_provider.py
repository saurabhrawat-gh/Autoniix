"""Mock LLM Provider — cached responses for test mode.

Resolution order:
  1. Disk cache (tests/fixtures/llm/<hash>.json) — instant, $0
  2. GPT-4o-mini fallback — cheapest model, caches result for next run
  3. Static fallback JSON — if no API key available

Cost: $0.00 on cache hit, ~$0.001 on cache miss (GPT-4o-mini).
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
from pathlib import Path

import httpx
import structlog

from src.config import settings
from src.providers.llm.base import LLMProvider, LLMRequest, LLMResult
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()


# ── Topic variety pool for test mode ──────────────────────────
# Each topic has: selected_topic, title_candidates, hook, key_facts
TOPIC_POOL = [
    {
        "selected_topic": "The Future of AI in Everyday Life",
        "title_candidates": [
            "How AI Is Secretly Changing Your Daily Routine",
            "5 Ways AI Already Runs Your Life",
            "AI in 2025: What Nobody Tells You",
        ],
        "hook": "Right now, as you're watching this, artificial intelligence is making decisions for you.",
        "key_facts": ["AI market growing 37% annually", "73% of businesses use AI"],
        "niche_hint": "tech",
    },
    {
        "selected_topic": "The Hidden Psychology of Habits",
        "title_candidates": [
            "Why You Can't Stop Scrolling (Backed by Science)",
            "The 21-Day Habit Myth: What Actually Works",
            "How Your Brain Sabotages Every Goal You Set",
        ],
        "hook": "Your brain just made 35,000 decisions today, and most of them were on autopilot.",
        "key_facts": ["Habits drive 45% of daily behavior", "Most habits form in 66 days"],
        "niche_hint": "self-improvement",
    },
    {
        "selected_topic": "Money Mistakes Most People Make",
        "title_candidates": [
            "5 Money Habits That Keep You Broke",
            "Why Saving Money Is Making You Poorer",
            "The $1,000 Mistake 90% of People Make Every Year",
        ],
        "hook": "If you have less than $1,000 in savings, this video could change everything.",
        "key_facts": ["64% of Americans live paycheck to paycheck", "Average inflation 3.5%"],
        "niche_hint": "finance",
    },
    {
        "selected_topic": "Sleep Science Breakthroughs",
        "title_candidates": [
            "The Sleep Trick Doctors Don't Tell You",
            "Why You Wake Up Tired (Even After 8 Hours)",
            "This 90-Minute Rule Will Change How You Sleep",
        ],
        "hook": "You're sleeping wrong, and it's destroying your energy.",
        "key_facts": ["Sleep cycles run 90 mins", "Deep sleep restores immunity"],
        "niche_hint": "health",
    },
    {
        "selected_topic": "Productivity Myths That Waste Your Time",
        "title_candidates": [
            "The Productivity Hack That Actually Works",
            "Why Multitasking Is Making You Slower",
            "Stop Doing This — It's Killing Your Focus",
        ],
        "hook": "You're working 8 hours a day but only producing 3 hours of real value.",
        "key_facts": ["Avg focus span: 47 seconds", "Multitasking drops IQ by 10"],
        "niche_hint": "productivity",
    },
    {
        "selected_topic": "Space Discoveries That Sound Fake",
        "title_candidates": [
            "5 Space Facts That Sound Made Up",
            "What NASA Just Found Will Blow Your Mind",
            "The Universe Is Weirder Than You Think",
        ],
        "hook": "There's a planet where it rains glass sideways. And it gets weirder.",
        "key_facts": ["Diamond rain on Neptune", "1 day on Venus = 243 Earth days"],
        "niche_hint": "science",
    },
]


def _pick_topic(seed: str | None = None) -> dict:
    """Pick a topic from the pool. Uses seed (e.g. content_id) for determinism if provided."""
    if seed:
        idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(TOPIC_POOL)
        return TOPIC_POOL[idx]
    return random.choice(TOPIC_POOL)

# Prefer tests/fixtures/llm for local dev, /tmp/mock_llm_cache for Docker
_LOCAL_CACHE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "llm"
CACHE_DIR = _LOCAL_CACHE if _LOCAL_CACHE.parent.exists() else Path("/tmp/mock_llm_cache")


def _cache_key(messages: list[dict], model: str) -> str:
    """Deterministic hash of prompt for cache lookup."""
    raw = json.dumps(messages, sort_keys=True) + model
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class MockLLM(LLMProvider):
    """Cached LLM for test mode. Checks disk cache first, falls back to GPT-4o-mini."""

    def __init__(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.api_key = settings.openai_api_key  # for fallback

    async def complete(self, request: LLMRequest) -> LLMResult:
        model = request.model or "gpt-4o-mini"
        key = _cache_key(request.messages, model)
        cache_file = CACHE_DIR / f"{key}.json"

        # If no real LLM key, skip cache entirely to allow variety in static fallback
        if not self.api_key:
            logger.info("mock_llm.no_api_key_static_response", key=key)
            static_content = self._static_response(request)
            return LLMResult(
                content=static_content,
                model="mock-static",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                provider="mock_llm",
                latency_ms=0,
                finish_reason="stop",
            )

        # 1. Check disk cache
        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text())
                logger.info("mock_llm.cache_hit", key=key)
                return LLMResult(
                    content=cached["content"],
                    model=f"mock-cached-{model}",
                    tokens_in=cached.get("tokens_in", 0),
                    tokens_out=cached.get("tokens_out", 0),
                    cost_usd=0.0,
                    provider="mock_llm",
                    latency_ms=1,
                    finish_reason="stop",
                )
            except (json.JSONDecodeError, KeyError):
                cache_file.unlink(missing_ok=True)

        # 2. Fallback: call GPT-4o-mini if API key available
        if self.api_key:
            try:
                result = await self._call_cheap_model(request, model)
                # Cache the result
                cache_file.write_text(json.dumps({
                    "content": result.content,
                    "tokens_in": result.tokens_in,
                    "tokens_out": result.tokens_out,
                    "model": model,
                    "cached_at": time.time(),
                }))
                logger.info("mock_llm.cache_miss_called_api", key=key, cost=result.cost_usd)
                return result
            except Exception as exc:
                logger.warning("mock_llm.api_fallback_failed", error=str(exc))

        # 3. Static fallback — return generic JSON response
        logger.info("mock_llm.static_fallback", key=key)
        static_content = self._static_response(request)
        return LLMResult(
            content=static_content,
            model="mock-static",
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            provider="mock_llm",
            latency_ms=0,
            finish_reason="stop",
        )

    async def _call_cheap_model(self, request: LLMRequest, model: str) -> LLMResult:
        """Call GPT-4o-mini as cheap fallback."""
        body: dict = {
            "model": "gpt-4o-mini",
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": min(request.max_tokens, 2000),
        }
        if request.response_format == "json":
            body["response_format"] = {"type": "json_object"}

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        usage = data["usage"]
        cost = usage["prompt_tokens"] * 0.15e-6 + usage["completion_tokens"] * 0.60e-6
        latency = int((time.monotonic() - start) * 1000)

        return LLMResult(
            content=data["choices"][0]["message"]["content"],
            model="gpt-4o-mini",
            tokens_in=usage["prompt_tokens"],
            tokens_out=usage["completion_tokens"],
            cost_usd=cost,
            provider="mock_llm",
            latency_ms=latency,
            finish_reason=data["choices"][0]["finish_reason"],
        )

    def _static_response(self, request: LLMRequest) -> str:
        """Return structurally valid mock data based on prompt content."""
        # Use SYSTEM message for classification (clean, unique per call type)
        # User messages often embed JSON payloads that confuse keyword matching
        system_text = ""
        user_text = ""
        for m in request.messages:
            content = m.get("content", "").lower()
            if m.get("role") == "system":
                system_text += content + " "
            else:
                user_text += content + " "

        if request.response_format == "json":
            data = self._detect_and_mock(system_text, user_text)
            return json.dumps(data)

        return "This is a mock response generated in test mode. The pipeline is working correctly but no real LLM was called."

    def _detect_and_mock(self, system_text: str, user_text: str) -> dict:
        """Produce mock JSON matching the expected schema for each pipeline phase.

        Classification uses system_text ONLY. User messages embed JSON payloads
        from previous pipeline steps (e.g. research_data in script prompt) which
        would cause false pattern matches if checked.
        """

        # Extract content_id or channel_id from prompts as seed for variety
        seed = None
        for token in (user_text + system_text).split():
            if token.startswith("TEST_VID") or token.startswith("VID_"):
                seed = token.strip(",.\"'")
                break
        topic = _pick_topic(seed)

        # Research synthesis — system prompt contains "research"
        if "research" in system_text and "scriptwriter" not in system_text:
            return {
                "selected_topic": topic["selected_topic"],
                "research_depth_score": 8.5,
                "title_candidates": topic["title_candidates"],
                "sources": [
                    {"url": "https://en.wikipedia.org/wiki/Main_Page", "title": "Reference", "key_facts": topic["key_facts"]},
                ],
                "fact_claims": [
                    {"claim": topic["key_facts"][0], "confidence": 0.85},
                    {"claim": topic["key_facts"][-1] if len(topic["key_facts"]) > 1 else topic["key_facts"][0], "confidence": 0.80},
                ],
                "trend_data": {"momentum": 0.8, "search_volume": "high"},
                "competitor_analysis": {"gap_found": True, "angle": "fresh perspective"},
                "audience_pain_points": ["information overload", "uncertainty", "lack of clarity"],
                "key_statistics": topic["key_facts"],
                "unique_angle": f"Practical insights on {topic['selected_topic']}",
            }

        # Fact-checking
        if "fact" in system_text and ("check" in system_text or "verify" in system_text):
            return {
                "verified_claims": [
                    {"claim": "AI market is projected to reach $190B by 2025", "status": "verified", "confidence": 0.9},
                ],
                "removed_claims": [],
                "overall_accuracy": 0.92,
            }

        # Ideation
        if "idea" in system_text or "ideation" in system_text:
            primary_title = topic["title_candidates"][0]
            return {
                "ideas": [
                    {
                        "title": primary_title,
                        "hook_angle": topic["hook"],
                        "target_emotion": "curiosity",
                        "estimated_appeal": 8.2,
                    },
                ],
                "selected_idea": {
                    "title": primary_title,
                    "hook_angle": topic["hook"],
                    "score": 8.5,
                },
            }

        # Script critique / QC — detect by system prompt keywords
        if "critique" in system_text or "score" in system_text and "dimension" in system_text:
            return {
                "overall_score": 9.5,
                "hook_retention_score": 9.2,
                "structure_score": 9.0,
                "clarity_score": 9.1,
                "engagement_score": 8.9,
                "pacing_score": 9.0,
                "scene_direction_quality": 8.8,
                "audience_retention_curve": 9.0,
                "emotional_arc_score": 9.1,
                "weak_dimensions": [],
                "improvements": [],
                "rewrite_suggestions": [],
                "pass": True,
            }

        # Script generation — detect by system prompt ("scriptwriter")
        if "scriptwriter" in system_text or ("script" in system_text and "json" in system_text):
            return {
                "title": topic["title_candidates"][0],
                "segments": [
                    {
                        "id": "seg_1",
                        "section": "hook",
                        "text": topic["hook"] + " And you don't even know it.",
                        "narration": topic["hook"] + " And you don't even know it.",
                        "duration_s": 8,
                        "emotion": "curiosity",
                        "scene_direction": "Close-up face shot, dramatic lighting, slow zoom in",
                        "emphasis_words": ["artificial intelligence", "decisions", "don't even know"],
                    },
                    {
                        "id": "seg_2",
                        "section": "intro",
                        "text": "From your morning alarm to your evening playlist, AI is everywhere. Today we're going to expose exactly how it works.",
                        "narration": "From your morning alarm to your evening playlist, AI is everywhere. Today we're going to expose exactly how it works.",
                        "duration_s": 10,
                        "emotion": "intrigue",
                        "scene_direction": "Montage of daily tech: phone, smart speaker, Netflix",
                        "emphasis_words": ["everywhere", "expose"],
                    },
                    {
                        "id": "seg_3",
                        "section": "body_1",
                        "text": "Let's start with something you do every single morning. You check your phone. That notification order? AI decided it. The news you see first? AI picked it.",
                        "narration": "Let's start with something you do every single morning. You check your phone. That notification order? AI decided it. The news you see first? AI picked it.",
                        "duration_s": 15,
                        "emotion": "surprise",
                        "scene_direction": "Split screen: person checking phone / algorithm visualization",
                        "emphasis_words": ["every single morning", "AI decided", "AI picked"],
                    },
                    {
                        "id": "seg_4",
                        "section": "body_2",
                        "text": "Your Spotify Discover Weekly? An AI that's analyzed 30 billion data points about your listening habits. It knows your taste better than your best friend.",
                        "narration": "Your Spotify Discover Weekly? An AI that's analyzed 30 billion data points about your listening habits. It knows your taste better than your best friend.",
                        "duration_s": 12,
                        "emotion": "amazement",
                        "scene_direction": "Spotify UI animation, data flow visualization",
                        "emphasis_words": ["30 billion", "better than your best friend"],
                    },
                    {
                        "id": "seg_5",
                        "section": "conclusion",
                        "text": "AI isn't coming. It's already here. The question isn't whether you'll use it — it's whether you'll understand it. And now, you do.",
                        "narration": "AI isn't coming. It's already here. The question isn't whether you'll use it — it's whether you'll understand it. And now, you do.",
                        "duration_s": 10,
                        "emotion": "empowerment",
                        "scene_direction": "Wide shot, confident posture, warm lighting",
                        "emphasis_words": ["already here", "understand it"],
                    },
                    {
                        "id": "seg_6",
                        "section": "cta",
                        "text": "If this opened your eyes, hit subscribe. We break down tech that matters, every single week.",
                        "narration": "If this opened your eyes, hit subscribe. We break down tech that matters, every single week.",
                        "duration_s": 6,
                        "emotion": "friendly",
                        "scene_direction": "Subscribe button animation, channel branding",
                        "emphasis_words": ["subscribe", "every single week"],
                    },
                ],
                "total_duration_s": 61,
                "word_count": 180,
                "script_structure_score": 9.5,
            }

        # Hook generation
        if "hook" in system_text:
            return {
                "hooks": [
                    {"text": "Right now, AI is making 35 decisions for you. And you have no idea.", "score": 8.8, "style": "provocative"},
                    {"text": "What if I told you an algorithm knows you better than your mother?", "score": 8.5, "style": "question"},
                    {"text": "I tracked every AI decision in my life for 24 hours. The results shocked me.", "score": 8.3, "style": "personal_experiment"},
                ],
                "selected_hook": "Right now, AI is making 35 decisions for you. And you have no idea.",
                "hook_retention_score": 8.8,
            }

        # Thumbnail concepts
        if "thumbnail" in system_text:
            return {
                "concepts": [
                    {
                        "description": "Shocked face looking at phone with glowing AI brain overlay, bold text 'AI CONTROLS YOU?'",
                        "dall_e_prompt": "Photorealistic shocked young person looking at smartphone, glowing blue AI neural network hologram emerging from phone screen, dark moody background, cinematic lighting, high contrast, 4K quality, YouTube thumbnail style",
                        "text_overlay": "AI CONTROLS YOU?",
                        "text_style": "bold_impact",
                        "composition_rule": "rule_of_thirds",
                        "emotion_trigger": "curiosity",
                        "score": 8.7,
                    },
                ],
                "thumbnail_score": 8.7,
            }

        # Direction / scene direction
        if "direction" in system_text or "camera" in system_text or "visual" in system_text:
            return {
                "direction_v3": {
                    "segments": [
                        {
                            "section": "hook",
                            "camera": {"shot": "close_up", "movement": "slow_zoom_in", "angle": "eye_level"},
                            "text_strategy": {"style": "kinetic_bold", "position": "center", "animation": "fade_in"},
                            "motion_design": {"bg_effect": "particle_flow", "transition_in": "cut", "transition_out": "dissolve"},
                            "audio_cues": {"sfx": "tech_whoosh", "music_mood": "suspense", "volume": 0.3},
                            "background_strategy": {"type": "gradient", "colors": ["#0a0a2e", "#1a1a4e"]},
                        },
                    ],
                },
                "direction_score": 8.5,
            }

        # Emotion mapping for voice
        if "emotion" in system_text:
            return {
                "emotion_map": [
                    {"section": "hook", "emotion": "curiosity", "stability": 0.4, "similarity_boost": 0.7, "style": 0.6, "speed": 1.05},
                    {"section": "intro", "emotion": "intrigue", "stability": 0.5, "similarity_boost": 0.75, "style": 0.5, "speed": 1.0},
                    {"section": "body_1", "emotion": "surprise", "stability": 0.45, "similarity_boost": 0.8, "style": 0.55, "speed": 1.02},
                    {"section": "body_2", "emotion": "amazement", "stability": 0.4, "similarity_boost": 0.85, "style": 0.6, "speed": 0.98},
                    {"section": "conclusion", "emotion": "empowerment", "stability": 0.55, "similarity_boost": 0.8, "style": 0.65, "speed": 0.95},
                    {"section": "cta", "emotion": "friendly", "stability": 0.6, "similarity_boost": 0.75, "style": 0.5, "speed": 1.05},
                ],
                "emphasis_words": ["artificial intelligence", "decisions", "every single morning"],
                "volume_shift": {"hook": 1.1, "conclusion": 1.05, "cta": 1.0},
            }

        # Brand DNA / identity
        if "brand" in system_text:
            return {
                "brand_score": 8.5,
                "consistency": 0.88,
                "tone_match": True,
                "suggestions": [],
            }

        # QC / quality check / inspector
        if "quality" in system_text or "inspect" in system_text or "qc" in system_text:
            return {
                "score": 8.5,
                "pass": True,
                "dimensions": {
                    "accuracy": 8.5,
                    "engagement": 8.3,
                    "production": 8.7,
                    "originality": 8.4,
                },
                "issues": [],
            }

        # Generic fallback
        return {
            "result": "test_mock_response",
            "score": 8.5,
            "items": [],
            "summary": "Mock response generated in test mode.",
            "pass": True,
        }

    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str | None = None) -> float:
        return 0.0

    async def health_check(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "mock_llm"

    def default_model(self) -> str:
        return "mock-gpt-4o-mini"

    def supported_models(self) -> list[str]:
        return ["mock-gpt-4o-mini", "mock-cached", "mock-static"]


# Register for all LLM categories
ProviderRegistry.register("llm", "mock_llm", MockLLM)
ProviderRegistry.register("llm.research", "mock_llm", MockLLM)
ProviderRegistry.register("llm.script", "mock_llm", MockLLM)
ProviderRegistry.register("llm.factcheck", "mock_llm", MockLLM)
ProviderRegistry.register("llm.qc", "mock_llm", MockLLM)
ProviderRegistry.register("llm.vision", "mock_llm", MockLLM)
ProviderRegistry.register("llm.ideation", "mock_llm", MockLLM)
ProviderRegistry.register("llm.hook", "mock_llm", MockLLM)
ProviderRegistry.register("llm.direction", "mock_llm", MockLLM)
ProviderRegistry.register("llm.emotion", "mock_llm", MockLLM)
