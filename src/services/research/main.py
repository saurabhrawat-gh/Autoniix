from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException

from src.config import settings
from src.db import close_pool, get_pool
from src.redis_client import close_redis, get_redis
from src.schemas.common import HealthResponse, ResearchRequest, ServiceResponse

# Import providers to trigger auto-registration
import src.providers.llm.openai_provider  # noqa: F401
import src.providers.search.serpapi_provider  # noqa: F401

from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("research.starting")
    yield
    await close_pool()
    await close_redis()
    logger.info("research.stopped")


app = FastAPI(title="Research Service", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="research")


@app.post("/research", response_model=ServiceResponse)
async def research(req: ResearchRequest):
    logger.info("research.started", channel_id=req.channel_id, topics=req.topic_candidates)

    total_cost = 0.0

    try:
        # ── Step 1: Search for topic data ────────────────────
        search_provider = ProviderRegistry.get("search")
        search_results = []

        queries = req.topic_candidates[:3] if req.topic_candidates else ["trending topics"]
        for query in queries:
            result = await search_provider.search(
                __import__("src.providers.search.base", fromlist=["SearchRequest"]).SearchRequest(
                    query=f"{query} site:youtube.com OR site:reddit.com",
                    num_results=5,
                )
            )
            search_results.extend(result.results)
            total_cost += result.cost_usd

        # ── Step 2: Synthesize with LLM ──────────────────────
        llm_provider = ProviderRegistry.get("llm.research")

        # Build sources context for the LLM
        sources_text = "\n".join(
            f"- {r.get('title', 'N/A')}: {r.get('snippet', 'N/A')}"
            for r in search_results[:10]
        )

        from src.providers.llm.base import LLMRequest

        synthesis = await llm_provider.complete(
            LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a YouTube research analyst. Analyze the provided search "
                            "results and topic candidates. Select the best topic and produce "
                            "a research synthesis. Respond in JSON with keys: "
                            "selected_topic, title_candidates (list of 5), "
                            "research_depth_score (1-10), sources (list of {url, title, relevance}), "
                            "fact_claims (list of {text, confidence}), "
                            "trend_data ({trending_score, search_volume_hint}), "
                            "competitor_analysis ({top_videos_count, avg_views_hint, gap})."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Channel: {req.channel_id}\n"
                            f"Content mode: {req.content_mode}\n"
                            f"Topic candidates: {json.dumps(req.topic_candidates)}\n\n"
                            f"Search results:\n{sources_text}"
                        ),
                    },
                ],
                temperature=0.4,
                max_tokens=2000,
                response_format="json",
            )
        )
        total_cost += synthesis.cost_usd

        # Parse LLM JSON response
        try:
            content = synthesis.content.strip()
            # Strip markdown fences if present
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {
                "selected_topic": req.topic_candidates[0] if req.topic_candidates else "Unknown",
                "title_candidates": [],
                "research_depth_score": 5.0,
                "sources": [],
                "fact_claims": [],
                "trend_data": {},
                "competitor_analysis": {},
            }

        # ── Step 3: Log usage ────────────────────────────────
        try:
            pool = await get_pool()
            await pool.execute(
                "INSERT INTO api_usage (content_id, service, provider, model, tokens_in, tokens_out, cost_usd, latency_ms) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                f"research-{req.channel_id}",
                "research",
                synthesis.provider,
                synthesis.model,
                synthesis.tokens_in,
                synthesis.tokens_out,
                float(synthesis.cost_usd),
                synthesis.latency_ms,
            )
        except Exception as db_err:
            logger.warning("research.db_log_failed", error=str(db_err))

        logger.info(
            "research.completed",
            topic=data.get("selected_topic"),
            cost_usd=round(total_cost, 4),
        )

        return ServiceResponse(
            status="success",
            data=data,
            cost={"cost_usd": round(total_cost, 6), "provider": synthesis.provider},
        )

    except Exception as exc:
        logger.error("research.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run(
        "src.services.research.main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
