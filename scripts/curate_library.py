"""Pre-seed the local ``asset_library`` table with high-quality clips for a
given niche.

Each niche gets a hand-picked seed query list (defined inline below — extend
when onboarding a new niche). For every query we hit Pexels + Pixabay, pick
clips that pass a minimum-quality bar (≥ 720p, ≥ 5s, license_free), download
them once into MinIO under ``library/<niche>/``, embed the query text via
SBERT, and insert into ``asset_library`` so the chain's local-library
provider can serve them as a zero-cost top tier.

Run::

    python scripts/curate_library.py --niche tech --limit 20
    python scripts/curate_library.py --all --limit 30

Idempotent: existing ``(query_hash, provider, asset_url)`` triples are
skipped via the unique constraint already on the table.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

import httpx
import structlog

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import settings  # noqa: E402
from core.db import get_pool, close_pool  # noqa: E402
from providers.boot import boot_providers  # noqa: E402  (registers storage)
from providers.registry import ProviderRegistry  # noqa: E402
from providers.storage.base import StorageUpload  # noqa: E402
from src.services.assets import semantic_ranker  # noqa: E402

logger = structlog.get_logger()

# Niche → seed-query catalogue
NICHE_SEEDS: dict[str, list[str]] = {
    "tech": [
        "code editor screen",
        "data center server room",
        "circuit board macro",
        "futuristic interface",
        "smartphone hands typing",
        "developer working night",
        "AI neural network",
        "office tech meeting",
    ],
    "health": [
        "running outdoor sunrise",
        "yoga meditation",
        "healthy meal preparation",
        "doctor patient consultation",
        "fresh vegetables",
        "fitness gym training",
        "nature walk forest",
    ],
    "finance": [
        "stock market chart rising",
        "money currency macro",
        "trader monitor screens",
        "calculator paperwork",
        "city financial district",
        "bitcoin cryptocurrency",
    ],
    "education": [
        "student studying laptop",
        "library books reading",
        "classroom teaching",
        "writing notes notebook",
        "graduation ceremony",
    ],
    "entertainment": [
        "concert crowd lights",
        "festival celebration",
        "cinema theatre seats",
        "fireworks night sky",
        "stage performance",
    ],
    "gaming": [
        "esports tournament",
        "gaming setup neon",
        "controller hands action",
        "computer rgb keyboard",
    ],
    "travel": [
        "aerial drone landscape",
        "tropical beach paradise",
        "city street timelapse",
        "mountain peak sunrise",
        "airplane window clouds",
    ],
    "food": [
        "chef cooking kitchen",
        "restaurant plating",
        "fresh ingredients board",
        "coffee pour macro",
    ],
    "sports": [
        "stadium crowd cheering",
        "athlete training",
        "soccer match goal",
        "basketball court action",
    ],
}


def _qhash(q: str) -> str:
    return hashlib.sha256(q.lower().strip().encode()).hexdigest()[:16]


async def _fetch_pexels(query: str, k: int = 5) -> list[dict]:
    if not settings.pexels_api_key:
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://api.pexels.com/videos/search",
            params={"query": query, "per_page": k, "size": "medium"},
            headers={"Authorization": settings.pexels_api_key},
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
    out = []
    for v in videos:
        files = v.get("video_files", [])
        best = next((f for f in files if (f.get("height") or 0) >= 720), files[0] if files else None)
        if not best:
            continue
        out.append({
            "provider": "pexels",
            "url": best["link"],
            "duration": float(v.get("duration", 0) or 0),
            "width": int(best.get("width", 0) or 0),
            "height": int(best.get("height", 0) or 0),
            "tags": v.get("user", {}).get("name", ""),
            "license": "pexels_free",
        })
    return out


async def _fetch_pixabay(query: str, k: int = 5) -> list[dict]:
    if not settings.pixabay_api_key:
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://pixabay.com/api/videos/",
            params={"key": settings.pixabay_api_key, "q": query, "per_page": k, "min_width": 1280},
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
    out = []
    for h in hits:
        m = h.get("videos", {}).get("medium", {})
        if not m.get("url"):
            continue
        out.append({
            "provider": "pixabay",
            "url": m["url"],
            "duration": float(h.get("duration", 0) or 0),
            "width": int(m.get("width", 0) or 0),
            "height": int(m.get("height", 0) or 0),
            "tags": h.get("tags", ""),
            "license": "pixabay_free",
        })
    return out


async def _embed(query: str) -> list[float] | None:
    model = semantic_ranker._get_model()
    if model is None:
        return None
    import numpy as np
    vec = model.encode([query], normalize_embeddings=True)[0]
    return [float(x) for x in np.asarray(vec).tolist()]


async def curate_niche(niche: str, limit_per_query: int = 5, max_total: int = 30) -> int:
    """Curate ``max_total`` clips for a niche. Returns count actually inserted."""
    queries = NICHE_SEEDS.get(niche)
    if not queries:
        logger.warning("curate.unknown_niche", niche=niche)
        return 0

    boot_providers()
    storage = ProviderRegistry.get("storage")
    pool = await get_pool()

    inserted = 0
    for query in queries:
        if inserted >= max_total:
            break
        candidates = []
        for fetched in await asyncio.gather(
            _fetch_pexels(query, limit_per_query),
            _fetch_pixabay(query, limit_per_query),
            return_exceptions=True,
        ):
            if isinstance(fetched, Exception):
                logger.warning("curate.fetch_failed", error=str(fetched))
                continue
            candidates.extend(fetched)

        if not candidates:
            continue

        emb = await _embed(query)
        qh = _qhash(query)

        for c in candidates:
            if inserted >= max_total:
                break
            # Quality bar
            if c["height"] < 720 or c["duration"] < 5:
                continue
            # Idempotency: does this asset_url already exist?
            existing = await pool.fetchval(
                "SELECT id FROM asset_library WHERE asset_url = $1 LIMIT 1",
                c["url"],
            )
            if existing:
                continue
            # Download → MinIO under library/<niche>/<qh>/<idx>.mp4
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.get(c["url"])
                    r.raise_for_status()
                    data = r.content
                key = f"library/{niche}/{qh}/{c['provider']}_{abs(hash(c['url'])) % 10**8}.mp4"
                up = await storage.upload(StorageUpload(key=key, data=data, content_type="video/mp4"))
            except Exception as exc:
                logger.warning("curate.download_failed", url=c["url"], error=str(exc))
                continue

            await pool.execute(
                """
                INSERT INTO asset_library (
                    query_hash, query_text, provider, asset_url, minio_key,
                    asset_type, resolution_width, resolution_height,
                    duration_s, dominant_colors, quality_score, relevance_score,
                    use_count, query_embedding, license_type, tags
                )
                VALUES ($1,$2,$3,$4,$5,'stock_video',$6,$7,$8,$9,$10,$11,0,$12,$13,$14)
                ON CONFLICT DO NOTHING
                """,
                qh, query, c["provider"], c["url"], up.key,
                c["width"], c["height"], c["duration"],
                json.dumps([]),  # dominant_colors filled later by analytics
                8.0, 8.0,
                emb, c["license"], c["tags"][:500],
            )
            inserted += 1
            logger.info("curate.inserted", niche=niche, query=query,
                        provider=c["provider"], height=c["height"], idx=inserted)

    await close_pool()
    return inserted


def main() -> None:
    ap = argparse.ArgumentParser(description="Curate the local asset_library")
    ap.add_argument("--niche", help="Niche key (see NICHE_SEEDS)")
    ap.add_argument("--all", action="store_true", help="Curate every niche")
    ap.add_argument("--limit", type=int, default=20, help="Max clips per niche")
    args = ap.parse_args()

    targets = list(NICHE_SEEDS) if args.all else [args.niche] if args.niche else []
    if not targets:
        ap.error("provide --niche <name> or --all")

    for niche in targets:
        n = asyncio.run(curate_niche(niche, max_total=args.limit))
        print(f"[curate] {niche}: {n} inserted")


if __name__ == "__main__":
    main()
