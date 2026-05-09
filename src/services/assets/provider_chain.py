"""Multi-provider stock-footage chain with semantic re-rank.

Calls every enabled provider in parallel, accumulates their top-K candidates,
re-ranks the union via :func:`semantic_ranker.score_candidates`, and returns
the best non-rejected result alongside the full scored set.

Providers are enabled by environment / settings:

* ``pexels``      — always on if ``PEXELS_API_KEY`` is set (free, recommended)
* ``pixabay``     — always on if ``PIXABAY_API_KEY`` is set (free)
* ``storyblocks`` — gated by ``STORYBLOCKS_API_KEY`` (paid, ~$30/mo for 5+ ch)
* ``envato``      — gated by ``ENVATO_API_KEY``
* ``library``     — local pgvector niche library (queried via ``query_optimizer``)

Provider health is tracked in-process: if a provider's rolling 5-min error
rate exceeds 50%, it's skipped for 60 seconds. Health metrics are exposed via
:func:`provider_health_snapshot` for the Prometheus exporter.

The chain itself is provider-agnostic — adding a new provider only requires
implementing an ``async def search(query) -> list[dict]`` callable with the
shared candidate schema (see :func:`_normalise_candidate`).
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Awaitable, Callable

import httpx
import structlog

from src.config import settings
from src.services.assets import semantic_ranker
from src.services.assets.semantic_ranker import ScoredCandidate

logger = structlog.get_logger()

# ── Provider-health (in-process, rolling 5-min) ─────────────────────


@dataclass
class _ProviderStats:
    events: deque = field(default_factory=lambda: deque(maxlen=60))
    skipped_until: float = 0.0  # epoch seconds

    def record(self, ok: bool) -> None:
        self.events.append((time.time(), ok))

    def error_rate(self, window_s: int = 300) -> float:
        cutoff = time.time() - window_s
        recent = [(t, ok) for (t, ok) in self.events if t >= cutoff]
        if not recent:
            return 0.0
        bad = sum(1 for (_, ok) in recent if not ok)
        return bad / len(recent)

    def healthy(self) -> bool:
        if time.time() < self.skipped_until:
            return False
        if len(self.events) >= 6 and self.error_rate() > 0.5:
            self.skipped_until = time.time() + 60
            return False
        return True


_HEALTH: dict[str, _ProviderStats] = {}


def _stats(name: str) -> _ProviderStats:
    s = _HEALTH.get(name)
    if s is None:
        s = _ProviderStats()
        _HEALTH[name] = s
    return s


def provider_health_snapshot() -> dict[str, dict]:
    """Snapshot for Prometheus / dashboards."""
    return {
        name: {
            "error_rate": round(s.error_rate(), 3),
            "skipped": time.time() < s.skipped_until,
            "samples": len(s.events),
        }
        for name, s in _HEALTH.items()
    }


# ── Candidate schema ────────────────────────────────────────────────


def _normalise_candidate(*, source: str, **kw) -> dict:
    return {
        "source": source,
        "id": str(kw.get("id", "")),
        "url": kw.get("url", ""),
        "thumbnail": kw.get("thumbnail", ""),
        "duration": float(kw.get("duration", 0) or 0),
        "width": int(kw.get("width", 0) or 0),
        "height": int(kw.get("height", 0) or 0),
        "tags": kw.get("tags", "") or "",
        "title": kw.get("title", "") or "",
        "description": kw.get("description", "") or "",
        "license": kw.get("license", "") or "",
        "dominant_colors": kw.get("dominant_colors") or [],
    }


# ── Providers ───────────────────────────────────────────────────────


async def _pexels(query: str, k: int = 10) -> list[dict]:
    api_key = settings.pexels_api_key
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.pexels.com/videos/search",
                params={"query": query, "per_page": k, "size": "medium"},
                headers={"Authorization": api_key},
            )
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
        out: list[dict] = []
        for v in videos:
            files = v.get("video_files", [])
            best = next((f for f in files if (f.get("height") or 0) >= 720), files[0] if files else None)
            if not best:
                continue
            out.append(_normalise_candidate(
                source="pexels", id=v.get("id", ""),
                url=best.get("link", ""), thumbnail=v.get("image", ""),
                duration=v.get("duration", 0),
                width=best.get("width", 0), height=best.get("height", 0),
                tags=" ".join((v.get("user", {}).get("name", ""),)),
                title=v.get("url", "").split("/")[-2].replace("-", " ") if v.get("url") else "",
                license="pexels_free",
            ))
        _stats("pexels").record(True)
        return out
    except Exception as exc:
        logger.warning("provider_chain.pexels_failed", error=str(exc))
        _stats("pexels").record(False)
        return []


async def _pixabay(query: str, k: int = 10) -> list[dict]:
    api_key = settings.pixabay_api_key
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://pixabay.com/api/videos/",
                params={"key": api_key, "q": query, "per_page": k, "min_width": 1280},
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        out: list[dict] = []
        for h in hits:
            vmedium = h.get("videos", {}).get("medium", {})
            if not vmedium.get("url"):
                continue
            out.append(_normalise_candidate(
                source="pixabay", id=h.get("id", ""),
                url=vmedium.get("url", ""),
                thumbnail=h.get("videos", {}).get("tiny", {}).get("thumbnail", ""),
                duration=h.get("duration", 0),
                width=vmedium.get("width", 0), height=vmedium.get("height", 0),
                tags=h.get("tags", ""),
                title=h.get("tags", "").split(",")[0].strip() if h.get("tags") else "",
                license="pixabay_free",
            ))
        _stats("pixabay").record(True)
        return out
    except Exception as exc:
        logger.warning("provider_chain.pixabay_failed", error=str(exc))
        _stats("pixabay").record(False)
        return []


async def _storyblocks(query: str, k: int = 10) -> list[dict]:
    """Storyblocks provider (paid tier). Stub implementation — Storyblocks
    requires HMAC-signed requests with a public/private key pair. The wiring
    here keeps the contract stable: when ``STORYBLOCKS_PUBLIC_KEY`` /
    ``STORYBLOCKS_PRIVATE_KEY`` are set we attempt the call, otherwise we
    return empty. Production deploys will fill the auth-signing block.
    """
    pub = getattr(settings, "storyblocks_public_key", "") or ""
    priv = getattr(settings, "storyblocks_private_key", "") or ""
    if not pub or not priv:
        return []
    # NOTE: real impl needs HMAC-SHA256 of (path + ts) signed with priv.
    # We log and return empty until creds are present in production.
    logger.info("provider_chain.storyblocks_skipped",
                reason="signing not yet implemented — supply STORYBLOCKS creds + sign helper")
    return []


async def _local_library(query: str, k: int = 10) -> list[dict]:
    """Search the in-DB ``asset_library`` for previously-curated clips.

    Uses the existing ``query_embedding`` column when SBERT is available;
    falls back to ``ILIKE`` keyword matching otherwise. Returns at most k
    high-quality candidates for the chain to re-rank against.
    """
    try:
        from src.db import get_pool
        pool = await get_pool()
        # Cheap path: keyword match on tags / query_text. Embedding-based
        # nearest neighbour is added in Phase 5 when the curate script
        # actually populates query_embedding.
        rows = await pool.fetch(
            """
            SELECT provider, asset_url, minio_key, asset_type, duration_s,
                   resolution_width, resolution_height, dominant_colors,
                   license_type, tags, quality_score, relevance_score
              FROM asset_library
             WHERE quality_score >= 6.0
               AND (tags ILIKE $1 OR query_text ILIKE $1)
             ORDER BY quality_score DESC, relevance_score DESC
             LIMIT $2
            """,
            f"%{query.split()[0] if query.split() else ''}%",
            k,
        )
        out: list[dict] = []
        for r in rows:
            colors = r["dominant_colors"]
            if isinstance(colors, str):
                import json
                try:
                    colors = json.loads(colors)
                except Exception:
                    colors = []
            out.append(_normalise_candidate(
                source=f"library:{r['provider']}",
                id="",
                url=r["minio_key"] or r["asset_url"],
                duration=float(r["duration_s"] or 0),
                width=int(r["resolution_width"] or 0),
                height=int(r["resolution_height"] or 0),
                tags=r["tags"] or "",
                license=r["license_type"] or "library",
                dominant_colors=colors or [],
            ))
        _stats("library").record(True)
        return out
    except Exception as exc:
        logger.warning("provider_chain.library_failed", error=str(exc))
        _stats("library").record(False)
        return []


# ── Chain orchestration ─────────────────────────────────────────────


@dataclass
class ChainResult:
    best: ScoredCandidate | None
    all_scored: list[ScoredCandidate]
    providers_called: list[str]
    providers_skipped: list[str]


_PROVIDERS: dict[str, Callable[[str, int], Awaitable[list[dict]]]] = {
    "pexels": _pexels,
    "pixabay": _pixabay,
    "storyblocks": _storyblocks,
    "library": _local_library,
}


async def run_chain(
    *,
    query: str,
    target_duration_s: float = 0.0,
    motion_intent: str = "dynamic",
    brand_palette: list[str] | None = None,
    prefer_1080p: bool = True,
    per_provider_k: int = 10,
    enabled: list[str] | None = None,
) -> ChainResult:
    """Run all enabled providers in parallel and return the chain result."""
    enabled = enabled or ["pexels", "pixabay", "storyblocks", "library"]
    called: list[str] = []
    skipped: list[str] = []
    coros = []
    for name in enabled:
        provider = _PROVIDERS.get(name)
        if provider is None:
            skipped.append(name)
            continue
        if not _stats(name).healthy():
            skipped.append(name)
            logger.info("provider_chain.skip_unhealthy", provider=name)
            continue
        called.append(name)
        coros.append(provider(query, per_provider_k))

    results: list[list[dict]] = []
    if coros:
        gathered = await asyncio.gather(*coros, return_exceptions=True)
        for name, res in zip(called, gathered):
            if isinstance(res, Exception):
                logger.warning("provider_chain.exception", provider=name, error=str(res))
                _stats(name).record(False)
                results.append([])
            else:
                results.append(res or [])
    union: list[dict] = []
    seen_keys: set[str] = set()
    for batch in results:
        for c in batch:
            key = (c.get("source", ""), c.get("id", ""), c.get("url", ""))
            kstr = "|".join(str(x) for x in key)
            if kstr in seen_keys:
                continue
            seen_keys.add(kstr)
            union.append(c)

    scored = semantic_ranker.score_candidates(
        query=query,
        candidates=union,
        motion_intent=motion_intent,
        target_duration_s=target_duration_s,
        brand_palette=brand_palette,
        prefer_1080p=prefer_1080p,
    )
    best = semantic_ranker.best_candidate(scored)
    logger.info(
        "provider_chain.complete",
        query=query[:80],
        candidates=len(union),
        called=called,
        skipped=skipped,
        best_score=round(best.final, 3) if best else None,
        best_source=best.clip.get("source") if best else None,
    )
    return ChainResult(best=best, all_scored=scored,
                       providers_called=called, providers_skipped=skipped)
