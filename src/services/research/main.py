from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from datetime import date, datetime

import httpx
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.redis_client import close_redis, get_redis
from src.schemas.common import HealthResponse, ServiceResponse

import src.providers.boot  # noqa: F401

from src.providers.registry import ProviderRegistry
from src.providers.llm.base import LLMRequest

from src.services.research.trend_collector import collect_trends
from src.services.research.competitor_insights import collect_competitor_insights
from src.services.research.similarity import (
    check_similarity, compute_embedding, compute_freshness, store_topic_embedding,
)
from src.services.research.opportunity_scorer import (
    score_opportunity, store_research_features,
)
from src.services.research.self_learning import (
    predict_success, thompson_sample, bandit_update, ingest_performance,
    train_model, check_model_drift,
)
from src.services.research.burst_detector import (
    detect_bursts, mine_phrases, get_rising_phrases,
    compute_phrase_novelty, compute_advanced_seasonality,
)
from src.observability.metrics import instrument_app

logger = structlog.get_logger()



class ResearchRequest(BaseModel):
    channel_id: str
    content_mode: str = "short"
    topic_candidates: list[str] = Field(default_factory=list)
    content_id: str | None = None
    budget_guard: dict = Field(default_factory=lambda: {"max_cost_usd": 2.50, "accrued_cost_usd": 0.0})


class IdeationRequest(BaseModel):
    channel_id: str
    research_data: dict = Field(default_factory=dict)



def _safe_format(template: str, **kwargs) -> str:
    """Replace {key} placeholders without failing on unknown/literal braces."""
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template


def _parse_json(text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def _log_usage(content_id: str, service: str, provider: str, model: str,
                     tokens_in: int, tokens_out: int, cost: float, latency: int):
    try:
        pool = await get_pool()
        cost_col = f"{provider}_cost" if provider in ("openai", "claude", "gemini") else "cost_usd"
        await pool.execute(
            "INSERT INTO api_usage (content_id, service, provider, model, tokens_in, tokens_out, cost_usd, latency_ms) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            content_id, service, provider, model, tokens_in, tokens_out, float(cost), latency,
        )
    except Exception as e:
        logger.warning("research.db_log_failed", error=str(e))


async def _load_channel_dna(channel_id: str) -> dict:
    """Load full channel DNA from PostgreSQL."""
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    if not row:
        return {}
    return dict(row)


async def _load_beliefs(channel_id: str) -> list[dict]:
    """Load beliefs for a channel from the belief_registry."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT belief_id, belief, counter_narrative, angle, belief_status, times_used, cooling_until_date "
        "FROM belief_registry WHERE channel_id = $1 ORDER BY times_used ASC",
        channel_id,
    )
    return [dict(r) for r in rows]


async def _load_used_topics(channel_id: str) -> list[str]:
    """Load recently used topics to avoid duplication."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT topic FROM videos WHERE channel_id = $1 AND created_at > NOW() - INTERVAL '30 days' "
        "ORDER BY created_at DESC LIMIT 50",
        channel_id,
    )
    return [r["topic"] for r in rows if r["topic"]]


async def _load_prompt(prompt_id: str) -> dict:
    """Load a prompt template from the prompt_registry."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT system_prompt, user_prompt_template FROM prompt_registry "
        "WHERE prompt_id = $1 AND is_active = true",
        prompt_id,
    )
    return dict(row) if row else {}



async def _search_youtube(topic: str, niche: str) -> list[dict]:
    """Search YouTube Data API for trending/relevant videos."""
    api_key = settings.youtube_api_key
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": f"{topic} {niche}",
                    "type": "video",
                    "order": "relevance",
                    "maxResults": 10,
                    "key": api_key,
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return [
                {
                    "source": "youtube",
                    "title": it["snippet"]["title"],
                    "description": it["snippet"]["description"][:200],
                    "url": f"https://youtube.com/watch?v={it['id']['videoId']}",
                    "channel": it["snippet"]["channelTitle"],
                    "published": it["snippet"]["publishedAt"],
                }
                for it in items if it.get("id", {}).get("videoId")
            ]
    except Exception as e:
        logger.warning("research.youtube_search_failed", error=str(e))
        return []


async def _search_serpapi(queries: list[str]) -> list[dict]:
    """Search via SerpAPI (Google + Google Trends)."""
    try:
        search_provider = ProviderRegistry.get("search")
        from src.providers.search.base import SearchRequest
        results = []
        for q in queries[:3]:
            result = await search_provider.search(SearchRequest(
                query=q,
                num_results=5,
            ))
            for r in result.results:
                results.append({
                    "source": "google",
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "url": r.get("link", ""),
                })
        return results
    except Exception as e:
        logger.warning("research.serpapi_failed", error=str(e))
        return []


async def _search_reddit(topic: str, niche: str) -> list[dict]:
    """Search Reddit for relevant discussions."""
    try:
        async with httpx.AsyncClient(timeout=10.0, headers={
            "User-Agent": "YTAutomation/1.0",
        }) as client:
            resp = await client.get(
                "https://www.reddit.com/search.json",
                params={"q": f"{topic} {niche}", "sort": "relevance", "limit": 10, "t": "month"},
            )
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])
            return [
                {
                    "source": "reddit",
                    "title": p["data"]["title"],
                    "snippet": p["data"].get("selftext", "")[:200],
                    "url": f"https://reddit.com{p['data']['permalink']}",
                    "subreddit": p["data"]["subreddit"],
                    "score": p["data"].get("score", 0),
                }
                for p in posts[:10]
            ]
    except Exception as e:
        logger.warning("research.reddit_failed", error=str(e))
        return []


async def _search_news(topic: str, niche: str) -> list[dict]:
    """Search News API for recent articles."""
    api_key = settings.news_api_key
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": f"{topic} {niche}",
                    "sortBy": "relevancy",
                    "pageSize": 5,
                    "language": "en",
                    "apiKey": api_key,
                },
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            return [
                {
                    "source": "news",
                    "title": a.get("title", ""),
                    "snippet": a.get("description", "")[:200],
                    "url": a.get("url", ""),
                    "published": a.get("publishedAt", ""),
                }
                for a in articles
            ]
    except Exception as e:
        logger.warning("research.news_failed", error=str(e))
        return []


async def _search_wikipedia(topic: str) -> list[dict]:
    """Search Wikipedia for background knowledge."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": topic,
                    "srlimit": 3,
                    "format": "json",
                },
            )
            resp.raise_for_status()
            results = resp.json().get("query", {}).get("search", [])
            return [
                {
                    "source": "wikipedia",
                    "title": r["title"],
                    "snippet": re.sub(r"<[^>]+>", "", r.get("snippet", "")),
                    "url": f"https://en.wikipedia.org/wiki/{r['title'].replace(' ', '_')}",
                }
                for r in results
            ]
    except Exception as e:
        logger.warning("research.wikipedia_failed", error=str(e))
        return []



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("research.starting")
    yield
    await close_pool()
    await close_redis()
    logger.info("research.stopped")


from src.observability.sentry import init_sentry
init_sentry("research")

app = FastAPI(title="Research Service", version="0.1.0", lifespan=lifespan)


instrument_app(app, service_name="research")
@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="research")


@app.post("/research", response_model=ServiceResponse)
async def research(req: ResearchRequest):
    """Full multi-source research pipeline with quality gate."""
    logger.info("research.started", channel_id=req.channel_id, topics=req.topic_candidates)
    total_cost = 0.0

    try:
        channel = await _load_channel_dna(req.channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {req.channel_id} not found")

        niche = channel.get("niche", "general")
        sub_niche = channel.get("sub_niche", "")
        topic_domain = channel.get("topic_domain", "")
        belief_territory = channel.get("belief_territory", "")
        intellectual_lens = channel.get("intellectual_lens", "")

        queries = req.topic_candidates[:3] if req.topic_candidates else []
        if topic_domain and not queries:
            queries = [t.strip() for t in topic_domain.split(",")[:3]]
        primary_topic = queries[0] if queries else niche

        import asyncio
        youtube_task = _search_youtube(primary_topic, niche)
        serpapi_task = _search_serpapi([f"{q} {niche}" for q in queries])
        reddit_task = _search_reddit(primary_topic, niche)
        news_task = _search_news(primary_topic, niche)
        wiki_task = _search_wikipedia(primary_topic)

        youtube_results, serp_results, reddit_results, news_results, wiki_results = (
            await asyncio.gather(youtube_task, serpapi_task, reddit_task, news_task, wiki_task)
        )

        all_sources = youtube_results + serp_results + reddit_results + news_results + wiki_results
        logger.info("research.sources_collected",
                     youtube=len(youtube_results), serp=len(serp_results),
                     reddit=len(reddit_results), news=len(news_results), wiki=len(wiki_results))

        from src.llm import route as _route, BudgetExceeded as _BudgetExceeded
        prompt = await _load_prompt("PRM_B1_RESEARCH_SYNTH")

        yt_text = "\n".join(f"- [{r['title']}]({r['url']}) by {r.get('channel','')}" for r in youtube_results[:8])
        serp_text = "\n".join(f"- {r['title']}: {r.get('snippet','')}" for r in serp_results[:8])
        reddit_text = "\n".join(f"- r/{r.get('subreddit','')}: {r['title']} (score: {r.get('score',0)})" for r in reddit_results[:8])
        news_text = "\n".join(f"- {r['title']}: {r.get('snippet','')}" for r in news_results[:5])

        system_prompt = _safe_format(prompt.get("system_prompt", "You are a YouTube research analyst. Respond in valid JSON."),
            niche=niche,
        )
        user_prompt = _safe_format(prompt.get("user_prompt_template", "Channel: {channel_id}\nTopics: {topic_candidates}"),
            channel_id=req.channel_id,
            channel_name=channel.get("channel_name", ""),
            niche=niche,
            sub_niche=sub_niche,
            belief_territory=belief_territory,
            intellectual_lens=intellectual_lens,
            topic_domain=topic_domain,
            topic_candidates=json.dumps(queries),
            search_results=serp_text,
            youtube_trending=yt_text,
            reddit_data=reddit_text,
            news_data=news_text,
        )

        max_retries = 2
        research_data = None

        for attempt in range(1, max_retries + 2):
            try:
                research_data = _parse_json(synthesis.content)
            except json.JSONDecodeError:
                logger.warning("research.synthesis_json_failed", attempt=attempt)
                research_data = {"selected_topic": primary_topic, "research_depth_score": 5.0,
                                 "title_candidates": [], "sources": [], "fact_claims": [],
                                 "trend_data": {}, "competitor_analysis": {}, "audience_pain_points": []}

            depth_score = float(research_data.get("research_depth_score", 0))
            if depth_score >= 8.0:
                logger.info("research.quality_gate_passed", score=depth_score, attempt=attempt)
                break
            elif attempt <= max_retries:
                logger.info("research.quality_gate_retry", score=depth_score, attempt=attempt)
                user_prompt += (
                    f"\n\n[RETRY: Your research_depth_score was {depth_score}/10. "
                    "Provide deeper analysis with more specific data points, statistics, and nuanced insights.]"
                )
            else:
                logger.warning("research.quality_gate_failed", score=depth_score)

        fact_claims = research_data.get("fact_claims", [])
        if fact_claims:
            fc_prompt = await _load_prompt("PRM_B1_FACT_CHECK")

            fc_system = fc_prompt.get("system_prompt", "You are a fact-checking specialist. Respond in JSON.")
            fc_user = _safe_format(fc_prompt.get("user_prompt_template", "Claims: {claims}\nSources: {sources}"),
                claims=json.dumps(fact_claims),
                sources=json.dumps(research_data.get("sources", [])),
            )

            try:
                fc_result = await _route(
                    category="llm.factcheck",
                    request=LLMRequest(
                        messages=[
                            {"role": "system", "content": fc_system},
                            {"role": "user", "content": fc_user},
                        ],
                        model="gpt-4o",
                        temperature=0.1,
                        max_tokens=2000,
                        response_format="json",
                    ),
                    channel_id=req.channel_id,
                    content_id=f"research-{req.channel_id}",
                    record_usage=False,
                )
            except _BudgetExceeded as exc:
                raise HTTPException(status_code=402, detail=str(exc))
            total_cost += fc_result.cost_usd
            await _log_usage(f"research-{req.channel_id}", "factcheck", fc_result.provider,
                             fc_result.model, fc_result.tokens_in, fc_result.tokens_out,
                             fc_result.cost_usd, fc_result.latency_ms)

            try:
                fc_data = _parse_json(fc_result.content)
                research_data["verified_claims"] = fc_data.get("verified_claims", [])
                research_data["removed_claims"] = fc_data.get("removed_claims", [])
                research_data["fact_claims"] = [
                    c for c in fc_data.get("verified_claims", [])
                    if c.get("confidence", 0) >= 0.7
                ]
                fact_confidence = sum(c.get("confidence", 0) for c in research_data["fact_claims"]) / max(len(research_data["fact_claims"]), 1)
                research_data["fact_confidence_score"] = round(fact_confidence * 10, 1)
            except json.JSONDecodeError:
                logger.warning("research.factcheck_json_failed")
                research_data["fact_confidence_score"] = 5.0

        selected_topic = research_data.get("selected_topic", primary_topic)

        try:
            trend_data = await collect_trends(niche, queries[:5])
            research_data["trend_signals"] = {
                "momentum": trend_data.get("google_trends", {}).get("momentum", {}),
                "suggestions": trend_data.get("youtube_suggestions", {}),
                "trending_videos": trend_data.get("youtube_trending", [])[:5],
            }
        except Exception as e:
            logger.warning("research.trends_failed", error=str(e))
            trend_data = {}

        try:
            competitor_yt_ids = [
                c.strip() for c in (channel.get("competitor_channels") or "").split(",") if c.strip()
            ]
            comp_data = await collect_competitor_insights(req.channel_id, niche, competitor_yt_ids or None)
            research_data["competitor_insights"] = {
                "competitor_count": comp_data.get("competitor_count", 0),
                "outlier_videos": comp_data.get("outlier_videos", [])[:5],
                "niche_outliers": comp_data.get("niche_outliers", [])[:5],
            }
        except Exception as e:
            logger.warning("research.competitors_failed", error=str(e))
            comp_data = {}

        try:
            bursts = await detect_bursts(niche)
            bursting = [b for b in bursts if b.get("is_burst")]
            research_data["bursting_keywords"] = bursting[:5]
        except Exception as e:
            logger.warning("research.bursts_failed", error=str(e))
            bursting = []

        try:
            phrases = await mine_phrases(niche)
            rising_phrases = [p for p in phrases if p.get("is_rising")]
            research_data["rising_phrases"] = [p["phrase"] for p in rising_phrases[:10]]
        except Exception as e:
            logger.warning("research.phrases_failed", error=str(e))
            rising_phrases = []

        try:
            sim_result = await check_similarity(selected_topic, text_type="topic")
            research_data["similarity_check"] = {
                "is_duplicate": sim_result.get("is_duplicate", False),
                "max_similarity": sim_result.get("max_similarity", 0),
                "novelty_score": sim_result.get("novelty_score", 1.0),
            }
        except Exception as e:
            logger.warning("research.similarity_failed", error=str(e))
            sim_result = {"novelty_score": 0.7}

        try:
            trend_momentum = 0.0
            momentum_data = trend_data.get("google_trends", {}).get("momentum", {})
            if momentum_data:
                first_kw = next(iter(momentum_data.values()), {})
                trend_momentum = first_kw.get("momentum", 0.0)
            fresh = await compute_freshness(selected_topic, niche, trend_momentum)
            research_data["freshness"] = fresh
        except Exception as e:
            logger.warning("research.freshness_failed", error=str(e))
            fresh = {"freshness_score": 0.5}

        try:
            phrase_nov = await compute_phrase_novelty(selected_topic, niche)
        except Exception:
            phrase_nov = 0.5

        try:
            season = await compute_advanced_seasonality(selected_topic, niche)
            research_data["seasonality"] = season
        except Exception:
            season = {"seasonality_score": 0.3}

        try:
            from src.services.research.saturation import compute_saturation
            sat = await compute_saturation(selected_topic, niche)
            research_data["saturation"] = {
                "score":               sat.saturation,
                "gap":                 sat.saturation_gap,
                "n_matches":           sat.n_matches,
                "top_match_similarity": sat.top_match_similarity,
                "cold_start":          sat.cold_start,
            }
        except Exception as e:
            logger.warning("research.saturation_failed", error=str(e))
            sat = None

        try:
            features = {
                "freshness_score": fresh.get("freshness_score", 0.5),
                "novelty_score": sim_result.get("novelty_score", 0.7),
                "trend_momentum": trend_momentum,
                "burst_score": bursting[0]["burst_score"] if bursting else 0.0,
                "phrase_novelty": phrase_nov,
                "trend_volume_index": next(
                    (m.get("current_index", 50) for m in momentum_data.values()), 50
                ) if momentum_data else 50,
                "saturation_gap": sat.saturation_gap if sat is not None else 1.0,
            }
            opp = await score_opportunity(selected_topic, niche=niche, features=features)
            research_data["opportunity_score"] = opp.get("opportunity_score", 0.5)
            research_data["feature_breakdown"] = opp.get("features", {})
        except Exception as e:
            logger.warning("research.scoring_failed", error=str(e))
            opp = {"opportunity_score": 0.5, "features": {}}

        content_id_for_pred = req.content_id or (
            f"research-{req.channel_id}-{datetime.utcnow().strftime('%Y%m%d%H%M')}"
        )

        try:
            ml_pred = await predict_success(
                opp.get("features", {}),
                niche=niche,
                content_id=content_id_for_pred,
            )
            research_data["ml_prediction"] = ml_pred
        except Exception:
            ml_pred = {"predicted_probability": 0.5}

        try:
            topic_clusters = research_data.get("title_candidates", [])
            if topic_clusters and len(topic_clusters) >= 2:
                bandit_result = await thompson_sample(
                    niche, topic_clusters[:10], channel_id=req.channel_id,
                )
                research_data["bandit_selection"] = bandit_result
        except Exception:
            pass

        try:
            await store_topic_embedding(
                content_id_for_pred,
                req.channel_id, "topic", selected_topic,
            )
        except Exception:
            pass

        try:
            await store_research_features(
                content_id=content_id_for_pred,
                channel_id=req.channel_id,
                topic=selected_topic,
                features=opp.get("features", {}),
                opportunity_score=opp.get("opportunity_score", 0.5),
                model_predicted=ml_pred.get("predicted_probability"),
            )
        except Exception:
            pass

        if research_data.get("similarity_check", {}).get("is_duplicate"):
            research_data["_warning"] = "HIGH_SIMILARITY_DETECTED"
            logger.warning("research.duplicate_detected",
                           topic=selected_topic,
                           sim=research_data["similarity_check"]["max_similarity"])

        logger.info("research.completed",
                     topic=selected_topic,
                     depth=research_data.get("research_depth_score"),
                     fact_conf=research_data.get("fact_confidence_score"),
                     opportunity=research_data.get("opportunity_score"),
                     novelty=sim_result.get("novelty_score"),
                     freshness=fresh.get("freshness_score"),
                     cost_usd=round(total_cost, 4))

        return ServiceResponse(
            status="success",
            data=research_data,
            cost={"cost_usd": round(total_cost, 6), "provider": "multi"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("research.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))



@app.post("/ideate", response_model=ServiceResponse)
async def ideate(req: IdeationRequest):
    """Full ideation pipeline: 10 ideas → scoring → novelty → quality gate."""
    logger.info("ideation.started", channel_id=req.channel_id)
    total_cost = 0.0

    try:
        channel = await _load_channel_dna(req.channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {req.channel_id} not found")

        beliefs = await _load_beliefs(req.channel_id)
        used_topics = await _load_used_topics(req.channel_id)

        today = date.today()
        available_beliefs = [
            b for b in beliefs
            if b.get("belief_status") == "available"
            and (not b.get("cooling_until_date") or b["cooling_until_date"] <= today)
        ]
        selected_belief = available_beliefs[0] if available_beliefs else (beliefs[0] if beliefs else None)

        prompt = await _load_prompt("PRM_B1_IDEATION")
        llm = ProviderRegistry.get("llm.ideation")

        from src.intelligence import build_performance_context
        perf_context = await build_performance_context(req.channel_id)

        system_prompt = _safe_format(prompt.get("system_prompt", "Generate 10 YouTube video concepts. Respond in JSON."),
            niche=channel.get("niche", ""),
            belief_territory=selected_belief["belief"] if selected_belief else channel.get("belief_territory", ""),
            intellectual_lens=channel.get("intellectual_lens", ""),
        )
        user_prompt = _safe_format(prompt.get("user_prompt_template", "Channel: {channel_id}"),
            channel_id=req.channel_id,
            brand_voice=channel.get("brand_voice", ""),
            narrative_rhythm=channel.get("narrative_rhythm", ""),
            emotional_contract=channel.get("emotional_contract", ""),
            research_summary=json.dumps(req.research_data.get("selected_topic", ""), default=str)[:2000],
            used_topics=json.dumps(used_topics[:20]),
        )

        max_retries = 2
        ideation_data = None

        for attempt in range(1, max_retries + 2):
            user_with_memory = (
                f"{perf_context}\n\n{user_prompt}" if perf_context else user_prompt
            )
            idea_result = await llm.complete(LLMRequest(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_with_memory},
                ],
                model="gpt-4o",
                temperature=0.8,
                max_tokens=3000,
                response_format="json",
            ))
            total_cost += idea_result.cost_usd
            await _log_usage(f"ideation-{req.channel_id}", "ideation", idea_result.provider,
                             idea_result.model, idea_result.tokens_in, idea_result.tokens_out,
                             idea_result.cost_usd, idea_result.latency_ms)

            try:
                ideation_data = _parse_json(idea_result.content)
            except json.JSONDecodeError:
                logger.warning("ideation.json_failed", attempt=attempt)
                ideation_data = {"ideas": []}

            ideas = ideation_data.get("ideas", [])

            for idea in ideas:
                curiosity = float(idea.get("curiosity_score", 5))
                novelty = float(idea.get("novelty_score", 5))
                emotion = float(idea.get("emotion_score", 5))
                composite = (curiosity * 0.3 + novelty * 0.3 + emotion * 0.4)
                idea["composite_score"] = round(composite, 2)

            for idea in ideas:
                title_lower = idea.get("title", "").lower()
                is_novel = not any(
                    t.lower() in title_lower or title_lower in t.lower()
                    for t in used_topics
                )
                idea["is_novel"] = is_novel

            novel_ideas = [i for i in ideas if i.get("is_novel", True)]
            novel_ideas.sort(key=lambda x: x.get("composite_score", 0), reverse=True)

            top_score = novel_ideas[0].get("composite_score", 0) if novel_ideas else 0
            if top_score >= 7.5:
                logger.info("ideation.quality_gate_passed", score=top_score, attempt=attempt, ideas=len(novel_ideas))
                break
            elif attempt <= max_retries:
                logger.info("ideation.quality_gate_retry", score=top_score, attempt=attempt)
                user_prompt += (
                    f"\n\n[RETRY: Top idea scored {top_score}/10. "
                    "Generate bolder, more surprising concepts with higher curiosity and emotion.]"
                )
            else:
                logger.warning("ideation.quality_gate_failed", score=top_score)

        winner = novel_ideas[0] if novel_ideas else (ideas[0] if ideas else {"title": "Unknown", "hook": ""})

        result = {
            "selected_idea": winner,
            "all_ideas": novel_ideas[:10],
            "belief_used": selected_belief,
            "idea_count": len(novel_ideas),
            "top_composite_score": winner.get("composite_score", 0),
        }

        logger.info("ideation.completed",
                     title=winner.get("title", "")[:60],
                     score=winner.get("composite_score"),
                     cost=round(total_cost, 4))

        return ServiceResponse(
            status="success",
            data=result,
            cost={"cost_usd": round(total_cost, 6), "provider": "multi"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("ideation.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))




class FeedbackRequest(BaseModel):
    content_id: str
    analytics: dict = Field(default_factory=dict)


class TrainRequest(BaseModel):
    niche: str | None = None
    min_samples: int = 20


class SimilarityRequest(BaseModel):
    text: str
    channel_id: str | None = None
    text_type: str = "topic"


class TrendRequest(BaseModel):
    niche: str
    keywords: list[str] = Field(default_factory=list)


class CompetitorRequest(BaseModel):
    channel_id: str
    niche: str
    competitor_yt_ids: list[str] = Field(default_factory=list)


@app.post("/feedback", response_model=ServiceResponse)
async def feedback(req: FeedbackRequest):
    """Ingest post-publish YouTube analytics for self-learning loop."""
    try:
        result = await ingest_performance(req.content_id, req.analytics)
        return ServiceResponse(status="success", data=result)
    except Exception as exc:
        logger.error("feedback.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/train", response_model=ServiceResponse)
async def train(req: TrainRequest):
    """Train/retrain the topic success predictor model."""
    try:
        result = await train_model(req.niche, req.min_samples)
        return ServiceResponse(status="success", data=result)
    except Exception as exc:
        logger.error("train.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/drift", response_model=ServiceResponse)
async def drift(niche: str | None = None):
    """Check if the ML model has drifted and needs retraining."""
    try:
        result = await check_model_drift(niche)
        return ServiceResponse(status="success", data=result)
    except Exception as exc:
        logger.error("drift.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/similarity", response_model=ServiceResponse)
async def similarity_check(req: SimilarityRequest):
    """Check topic similarity against existing catalog."""
    try:
        result = await check_similarity(req.text, req.channel_id, req.text_type)
        return ServiceResponse(status="success", data=result)
    except Exception as exc:
        logger.error("similarity.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/trends", response_model=ServiceResponse)
async def trends(req: TrendRequest):
    """Collect trend signals for a niche."""
    try:
        result = await collect_trends(req.niche, req.keywords)
        return ServiceResponse(status="success", data=result)
    except Exception as exc:
        logger.error("trends.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/competitors", response_model=ServiceResponse)
async def competitors(req: CompetitorRequest):
    """Analyze competitors and find niche outliers."""
    try:
        result = await collect_competitor_insights(
            req.channel_id, req.niche, req.competitor_yt_ids or None
        )
        return ServiceResponse(status="success", data=result)
    except Exception as exc:
        logger.error("competitors.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/bursts", response_model=ServiceResponse)
async def bursts(niche: str):
    """Detect bursting keywords in a niche."""
    try:
        result = await detect_bursts(niche)
        return ServiceResponse(status="success", data=result)
    except Exception as exc:
        logger.error("bursts.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/phrases", response_model=ServiceResponse)
async def phrases(niche: str):
    """Get rising phrases for a niche."""
    try:
        result = await get_rising_phrases(niche)
        return ServiceResponse(status="success", data=result)
    except Exception as exc:
        logger.error("phrases.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run(
        "src.services.research.main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
