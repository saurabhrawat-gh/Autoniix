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

from core.config import settings
from core.db import close_pool, get_pool
from schemas.common import HealthResponse, ServiceResponse

import providers.boot  # noqa: F401
from providers.registry import ProviderRegistry
from providers.llm.base import LLMRequest
from providers.storage.base import StorageUpload

from src.services.assets.query_optimizer import (
    optimize_query,
    check_asset_cache,
    store_in_cache,
    log_search,
)
from src.services.assets.provider_chain import (
    run_chain,
    provider_health_snapshot,
)
from observability.metrics import instrument_app

try:
    from prometheus_client import Counter, Histogram, Gauge
    ASSET_COVERAGE_TOTAL = Counter(
        "asset_coverage_total",
        "Per-segment asset acquisition outcomes.",
        labelnames=("outcome",),
    )
    ASSET_RELEVANCE = Histogram(
        "asset_relevance_score",
        "Final semantic-ranker score of the picked clip per segment (0-1).",
        buckets=(0.3, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95),
    )
    ASSET_PROVIDER_HEALTH = Gauge(
        "asset_provider_error_rate",
        "Rolling 5-min error rate per stock-footage provider.",
        labelnames=("provider",),
    )
except Exception:  # pragma: no cover
    class _Noop:
        def labels(self, *a, **kw): return self
        def inc(self, *a, **kw): return None
        def observe(self, *a, **kw): return None
        def set(self, *a, **kw): return None
    ASSET_COVERAGE_TOTAL = ASSET_RELEVANCE = ASSET_PROVIDER_HEALTH = _Noop()  # type: ignore

logger = structlog.get_logger()



class AssetsRequest(BaseModel):
    content_id: str
    channel_id: str
    segments: list[dict] = Field(default_factory=list)
    music_mood: str = ""
    content_mode: str = "short"


class MusicRequest(BaseModel):
    content_id: str
    channel_id: str
    mood: str = ""
    duration_s: float = 45.0



def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def _load_channel(channel_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM channels WHERE channel_id = $1", channel_id)
    return dict(row) if row else {}


async def _log_usage(content_id: str, service: str, provider: str, cost: float):
    try:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO api_usage (content_id, service, provider, cost_usd) VALUES ($1, $2, $3, $4)",
            content_id, service, provider, float(cost))
    except Exception as e:
        logger.warning("assets.db_log_failed", error=str(e))



NICHE_KEYWORDS: dict[str, list[str]] = {
    "tech": ["technology", "digital", "futuristic", "code", "circuit"],
    "health": ["wellness", "nature", "calm", "medical", "fitness"],
    "finance": ["money", "trading", "graph", "growth", "business"],
    "education": ["learning", "classroom", "knowledge", "books", "study"],
    "entertainment": ["fun", "colorful", "party", "celebration", "performance"],
    "gaming": ["gaming", "esports", "controller", "neon", "cyber"],
    "travel": ["landscape", "adventure", "aerial", "destination", "scenic"],
    "food": ["cooking", "kitchen", "ingredients", "delicious", "plating"],
    "sports": ["athletic", "competition", "stadium", "training", "action"],
}


def _expand_query_for_niche(query: str, niche: str, content_mode: str = "short") -> str:
    """Expand search query with niche-specific keywords and aspect ratio hints."""
    niche_terms = NICHE_KEYWORDS.get(niche, [])
    if niche_terms:
        import random
        extras = random.sample(niche_terms, min(2, len(niche_terms)))
        query = f"{query} {' '.join(extras)}"

    if content_mode == "short":
        query = f"{query} vertical"
    return query


def _filter_by_aspect_ratio(clips: list[dict], content_mode: str = "short") -> list[dict]:
    """Filter clips by aspect ratio preference: 9:16 for shorts, 16:9 for long."""
    if not clips:
        return clips

    target_ratio = 9 / 16 if content_mode == "short" else 16 / 9
    scored = []
    for clip in clips:
        w = clip.get("width", 1920)
        h = clip.get("height", 1080)
        if w and h:
            clip_ratio = w / h
            ratio_diff = abs(clip_ratio - target_ratio)
            clip["aspect_score"] = max(0, 1.0 - ratio_diff)
        else:
            clip["aspect_score"] = 0.5
        scored.append(clip)

    scored.sort(key=lambda c: c.get("aspect_score", 0), reverse=True)
    return scored



async def _search_pixabay_videos(query: str, min_duration: int = 5) -> list[dict]:
    """Search Pixabay for stock video clips."""
    api_key = settings.pixabay_api_key
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://pixabay.com/api/videos/", params={
                "key": api_key, "q": query, "per_page": 5, "min_width": 1280,
            })
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            return [
                {
                    "source": "pixabay", "id": str(h["id"]),
                    "url": h.get("videos", {}).get("medium", {}).get("url", ""),
                    "thumbnail": h.get("videos", {}).get("tiny", {}).get("thumbnail", ""),
                    "duration": h.get("duration", 0),
                    "width": h.get("videos", {}).get("medium", {}).get("width", 0),
                    "height": h.get("videos", {}).get("medium", {}).get("height", 0),
                    "tags": h.get("tags", ""),
                    "license": "pixabay_free",
                }
                for h in hits if h.get("duration", 0) >= min_duration
            ]
    except Exception as e:
        logger.warning("assets.pixabay_failed", error=str(e))
        return []


async def _search_pexels_videos(query: str, min_duration: int = 5) -> list[dict]:
    """Search Pexels for stock video clips."""
    api_key = settings.pexels_api_key
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.pexels.com/videos/search", params={
                "query": query, "per_page": 5, "size": "medium",
            }, headers={"Authorization": api_key})
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
            results = []
            for v in videos:
                files = v.get("video_files", [])
                best = None
                for f in files:
                    if f.get("height", 0) >= 720:
                        best = f
                        break
                if not best and files:
                    best = files[0]
                if best and v.get("duration", 0) >= min_duration:
                    results.append({
                        "source": "pexels", "id": str(v["id"]),
                        "url": best.get("link", ""),
                        "thumbnail": v.get("image", ""),
                        "duration": v.get("duration", 0),
                        "width": best.get("width", 0),
                        "height": best.get("height", 0),
                        "tags": "",
                        "license": "pexels_free",
                    })
            return results
    except Exception as e:
        logger.warning("assets.pexels_failed", error=str(e))
        return []



async def _search_freesound(query: str, duration_max: float = 30.0) -> list[dict]:
    """Search Freesound for SFX clips."""
    api_key = settings.freesound_api_key
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://freesound.org/apiv2/search/text/", params={
                "query": query, "filter": f"duration:[0 TO {duration_max}]",
                "fields": "id,name,duration,previews,license,tags",
                "page_size": 5, "token": api_key,
            })
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return [
                {
                    "source": "freesound", "id": str(r["id"]),
                    "name": r.get("name", ""),
                    "url": r.get("previews", {}).get("preview-hq-mp3", ""),
                    "duration": r.get("duration", 0),
                    "tags": ", ".join(r.get("tags", [])[:5]),
                    "license": r.get("license", ""),
                }
                for r in results
            ]
    except Exception as e:
        logger.warning("assets.freesound_failed", error=str(e))
        return []



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("assets.starting")
    yield
    await close_pool()
    logger.info("assets.stopped")


from observability.sentry import init_sentry
init_sentry("assets")

app = FastAPI(title="Assets Service", version="0.1.0", lifespan=lifespan)


instrument_app(app, service_name="assets")
@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="assets")


@app.post("/generate-assets", response_model=ServiceResponse)
async def generate_assets(req: AssetsRequest):
    """Full asset pipeline: stock search → relevance score → filter → DALL-E fallback → upload."""
    logger.info("assets.generating", content_id=req.content_id, segments=len(req.segments))

    storage = ProviderRegistry.get("storage")
    total_cost = 0.0
    manifest = []
    stock_count = 0
    generated_count = 0

    import asyncio
    import time as _time
    channel = await _load_channel(req.channel_id)
    cache_enabled = True

    for seg in req.segments:
        seg_id = seg.get("id", "unknown")
        direction = seg.get("scene_direction", "")
        suggestions = seg.get("asset_suggestions", [])
        b_roll = seg.get("b_roll_keywords", [])

        if not direction and not suggestions and not b_roll:
            manifest.append({"segment_id": seg_id, "type": "none", "assets": []})
            continue

        optimized = optimize_query(seg)
        queries = optimized.get("queries", [])
        query_hash = optimized.get("primary_hash", "")
        query = queries[0] if queries else " ".join(b_roll[:2] or suggestions[:2]) or direction[:50]
        search_start = _time.time()

        try:
            if cache_enabled and query_hash:
                cached = await check_asset_cache(query_hash)
                if cached:
                    manifest.append({
                        "segment_id": seg_id,
                        "type": cached.get("asset_type", "stock_video"),
                        "source": cached.get("provider", "cache"),
                        "assets": [{"url": cached["url"], "type": cached["asset_type"],
                                     "source": "cache", "cached": True}],
                    })
                    stock_count += 1
                    ASSET_COVERAGE_TOTAL.labels(outcome="cached").inc()
                    await log_search(req.content_id, req.channel_id, seg_id,
                                     query, "cache", 1, used_cache=True,
                                     search_time_ms=int((_time.time() - search_start) * 1000))
                    continue

            niche = channel.get("niche", "") if channel else ""
            expanded_query = _expand_query_for_niche(query, niche, req.content_mode)

            target_dur_s = float(seg.get("duration_ms", 0) or 0) / 1000.0
            motion_intent = (seg.get("motion_intent")
                              or seg.get("mood", {}).get("name")
                              or ("frenetic" if req.content_mode == "short" else "dynamic"))
            brand_palette = (channel.get("brand_palette")
                             or channel.get("brand_color_palette")
                             or [])
            if isinstance(brand_palette, str):
                try:
                    brand_palette = json.loads(brand_palette)
                except Exception:
                    brand_palette = []

            chain_result = await run_chain(
                query=expanded_query,
                target_duration_s=target_dur_s,
                motion_intent=motion_intent,
                brand_palette=brand_palette if isinstance(brand_palette, list) else None,
                prefer_1080p=(req.content_mode != "short"),
            )

            for prov_name, prov in provider_health_snapshot().items():
                ASSET_PROVIDER_HEALTH.labels(provider=prov_name).set(prov["error_rate"])

            best = chain_result.best
            selected_clip = best.clip if best else None

            if selected_clip and selected_clip.get("url"):
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.get(selected_clip["url"])
                        resp.raise_for_status()
                        video_bytes = resp.content

                    ext = "mp4" if "mp4" in selected_clip["url"] else "mp4"
                    key = f"assets/{req.content_id}/{seg_id}_stock.{ext}"
                    sr = await storage.upload(StorageUpload(key=key, data=video_bytes, content_type=f"video/{ext}"))
                    url = sr.url

                    relevance = float(best.final) if best else 0.0
                    manifest.append({
                        "segment_id": seg_id,
                        "type": "stock_video",
                        "source": selected_clip["source"],
                        "assets": [{
                            "url": url, "key": key,
                            "type": "stock_video",
                            "source": selected_clip["source"],
                            "source_id": selected_clip["id"],
                            "duration": selected_clip.get("duration", 0),
                            "license": selected_clip.get("license", ""),
                            "relevance_score": relevance,
                            "sub_scores": best.as_dict() if best else {},
                        }],
                    })
                    stock_count += 1
                    ASSET_COVERAGE_TOTAL.labels(outcome="stock").inc()
                    ASSET_RELEVANCE.observe(relevance)
                    await store_in_cache(
                        query, selected_clip["source"], selected_clip["url"],
                        minio_key=key, quality_score=round(relevance * 10, 2),
                        duration_s=float(selected_clip.get("duration", 0)))
                    await log_search(req.content_id, req.channel_id, seg_id,
                                     query, selected_clip["source"],
                                     len(chain_result.all_scored),
                                     selected_id=selected_clip["id"],
                                     search_time_ms=int((_time.time() - search_start) * 1000))
                    continue
                except Exception as dl_err:
                    logger.warning("assets.stock_download_failed", seg=seg_id, error=str(dl_err))

            enable_dalle = bool(channel.get("enable_dalle_fallback", False))
            if not enable_dalle:
                manifest.append({
                    "segment_id": seg_id,
                    "type": "kinetic_text",
                    "source": "fallback",
                    "assets": [{
                        "type": "kinetic_text",
                        "text": (direction or query)[:140],
                        "reason": "no stock candidate above relevance threshold",
                        "chain_candidates": len(chain_result.all_scored),
                        "providers_called": chain_result.providers_called,
                    }],
                })
                ASSET_COVERAGE_TOTAL.labels(outcome="kinetic_fallback").inc()
                await log_search(req.content_id, req.channel_id, seg_id,
                                 query, "kinetic_fallback",
                                 len(chain_result.all_scored),
                                 used_fallback=True,
                                 search_time_ms=int((_time.time() - search_start) * 1000))
                continue

            image_provider = ProviderRegistry.get("image")
            from providers.image.base import ImageRequest

            prompt = f"YouTube video scene: {direction}. {', '.join(suggestions[:3])}"
            prompt = prompt[:900]

            img_result = await image_provider.generate(ImageRequest(
                prompt=prompt, size="1792x1024", quality="standard", style="vivid", n=1,
            ))
            total_cost += img_result.cost_usd

            assets = []
            for i, img in enumerate(img_result.images):
                img_bytes = img.get("_bytes")
                if not img_bytes:
                    img_url = img.get("url", "")
                    if not img_url or img_url.startswith("data:"):
                        continue
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.get(img_url)
                        resp.raise_for_status()
                        img_bytes = resp.content

                key = f"assets/{req.content_id}/{seg_id}_{i}.png"
                sr = await storage.upload(StorageUpload(key=key, data=img_bytes, content_type="image/png"))
                url = sr.url
                assets.append({
                    "url": url, "key": key, "type": "generated_image",
                    "prompt": prompt[:200],
                })
                generated_count += 1

            manifest.append({"segment_id": seg_id, "type": "generated_image", "assets": assets})
            ASSET_COVERAGE_TOTAL.labels(outcome="dalle").inc()
            await log_search(req.content_id, req.channel_id, seg_id,
                             query, "dalle", 0, used_fallback=True,
                             search_time_ms=int((_time.time() - search_start) * 1000))

        except Exception as exc:
            logger.warning("assets.segment_failed", segment_id=seg_id, error=str(exc))
            manifest.append({"segment_id": seg_id, "type": "failed", "error": str(exc), "assets": []})
            ASSET_COVERAGE_TOTAL.labels(outcome="failed").inc()

    await _log_usage(req.content_id, "assets", "multi", total_cost)

    total_assets = sum(len(m.get("assets", [])) for m in manifest)
    logger.info("assets.generated", total=total_assets, stock=stock_count,
                 generated=generated_count, cost=round(total_cost, 4))

    return ServiceResponse(
        status="success",
        data={
            "manifest": manifest,
            "total_assets": total_assets,
            "stock_footage_count": stock_count,
            "generated_image_count": generated_count,
        },
        cost={"cost_usd": round(total_cost, 6), "provider": "multi"},
    )



@app.post("/search-music", response_model=ServiceResponse)
async def search_music(req: MusicRequest):
    """Search for background music and SFX."""
    channel = await _load_channel(req.channel_id)
    mood = req.mood or channel.get("music_mood_default", "ambient")

    sfx_density = channel.get("sfx_density", "low")
    sfx_count = {"minimal": 1, "low": 2, "medium": 4, "high": 6}.get(sfx_density, 2)

    import asyncio
    music_task = _search_freesound(f"{mood} background music", duration_max=req.duration_s * 2)
    sfx_task = _search_freesound(f"transition whoosh impact", duration_max=5.0)

    music_results, sfx_results = await asyncio.gather(music_task, sfx_task)

    return ServiceResponse(
        status="success",
        data={
            "music": music_results[:3],
            "sfx": sfx_results[:sfx_count],
            "mood": mood,
            "sfx_density": sfx_density,
        },
        cost={"cost_usd": 0.0, "provider": "freesound"},
    )


if __name__ == "__main__":
    uvicorn.run("src.services.assets.main:app", host="0.0.0.0", port=8004, log_level="info")
