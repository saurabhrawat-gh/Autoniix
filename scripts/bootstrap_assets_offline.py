"""Phase 3 — Offline free-tier bootstrap for the local asset_library.

Loads ``scripts/seeds/public_domain_assets.json`` (a curated catalog of CC0 /
public-domain stock clips) into the ``asset_library`` Postgres table so that
fresh deployments with **zero API keys** still get a usable local-library
provider out of the box. Combined with the existing ``curate_library.py``
(which uses Pexels/Pixabay APIs when keys are present), this gives operators
a reliable progression:

    no keys      →  bootstrap_assets_offline.py            (15+ clips, free)
    free keys    →  curate_library.py                      (~100s of clips)
    paid keys    →  Storyblocks/Envato via the live chain  (unlimited)

Every seed entry is materialised to ``asset_library`` with one row per
(query, asset). The query→hash mapping uses the same algorithm the live
provider chain uses (``_query_hash`` in query_optimizer), so cache lookups
hit on the first run.

Run::

    python scripts/bootstrap_assets_offline.py                # all niches
    python scripts/bootstrap_assets_offline.py --niche space  # one niche
    python scripts/bootstrap_assets_offline.py --check        # dry-run, no DB writes
    python scripts/bootstrap_assets_offline.py --validate-urls
        # also HEAD each URL and report unreachable rows (slow; CI-only)

Idempotent: ``ON CONFLICT DO NOTHING`` against (query_hash, provider, asset_url).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SEED_FILE = ROOT / "scripts" / "seeds" / "public_domain_assets.json"

# ── Pure functions (testable without DB) ────────────────────────────


def query_hash(q: str) -> str:
    """Stable hash matching the production chain's ``_query_hash``.

    sha256 of the lowercased trimmed query, hex-encoded, truncated to 16
    chars (which is what asset_library.query_hash stores; the column is
    sized for 64 hex chars but production code only uses the first 16).
    """
    return hashlib.sha256(q.lower().strip().encode("utf-8")).hexdigest()[:16]


def load_seed(seed_path: Path = SEED_FILE) -> dict[str, Any]:
    """Read + parse the JSON catalog. Validates schema_version + required
    fields per asset; raises on first violation."""
    if not seed_path.exists():
        raise FileNotFoundError(f"seed catalog missing: {seed_path}")
    data = json.loads(seed_path.read_text("utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(
            f"seed catalog schema_version mismatch: expected 1, got {data.get('schema_version')!r}"
        )
    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("seed catalog: 'assets' must be a non-empty list")

    required = {
        "niche", "queries", "provider", "asset_url", "asset_type",
        "duration_s", "resolution_width", "resolution_height",
        "license_type", "tags",
    }
    for i, a in enumerate(assets):
        missing = required - set(a)
        if missing:
            raise ValueError(f"seed asset[{i}]: missing fields {sorted(missing)}")
        if not isinstance(a["queries"], list) or not a["queries"]:
            raise ValueError(f"seed asset[{i}]: 'queries' must be a non-empty list")
        if not str(a["asset_url"]).startswith(("http://", "https://")):
            raise ValueError(f"seed asset[{i}]: asset_url must be http(s)")
    return data


def expand_to_rows(seed: dict[str, Any], niche: str | None = None) -> list[dict[str, Any]]:
    """Expand each (asset, queries[]) into 1 row per query.

    Returns rows shaped for the ``asset_library`` INSERT — every row carries
    ``query_text``, ``query_hash``, ``provider``, ``asset_url``, etc. with
    quality + relevance scores set to a deliberately conservative 6.5/10 so
    the local-library provider only wins on cache hits, not on raw rank.
    """
    rows: list[dict[str, Any]] = []
    for a in seed["assets"]:
        if niche and a["niche"] != niche:
            continue
        for q in a["queries"]:
            rows.append({
                "query_hash": query_hash(q),
                "query_text": q,
                "provider": a["provider"],
                "asset_url": a["asset_url"],
                "asset_type": a["asset_type"],
                "duration_s": float(a["duration_s"]),
                "resolution_width": int(a["resolution_width"]),
                "resolution_height": int(a["resolution_height"]),
                "license_type": a["license_type"],
                "tags": a["tags"],
                # 6.5 means: above the 6.0 cache hit threshold (so reuses)
                # but below typical Pexels/Pixabay scores (7.0+) so live
                # search wins when free APIs are configured.
                "quality_score": 6.5,
                "relevance_score": 6.5,
            })
    return rows


def list_niches(seed: dict[str, Any]) -> list[str]:
    return sorted({a["niche"] for a in seed["assets"]})


# ── DB sink (lazy import so the pure logic stays testable) ──────────


async def insert_rows(rows: list[dict[str, Any]]) -> int:
    """Insert rows idempotently. Returns the number actually inserted
    (excluding ON CONFLICT skips)."""
    sys.path.insert(0, str(ROOT))
    from src.db import get_pool  # noqa: E402

    pool = await get_pool()
    inserted = 0
    for r in rows:
        # asset_library lacks an explicit unique constraint, but
        # (query_hash, provider, asset_url) collectively identify a row;
        # we emulate ON CONFLICT via a SELECT-then-INSERT under advisory
        # locking in production, but for the offline bootstrap a simple
        # "skip if exists" loop is sufficient and keeps the SQL simple.
        existing = await pool.fetchval(
            "SELECT 1 FROM asset_library "
            "WHERE query_hash = $1 AND provider = $2 AND asset_url = $3 LIMIT 1",
            r["query_hash"], r["provider"], r["asset_url"],
        )
        if existing:
            continue
        await pool.execute(
            """
            INSERT INTO asset_library (
                query_hash, query_text, provider, asset_url,
                asset_type, resolution_width, resolution_height, duration_s,
                quality_score, relevance_score, license_type, tags
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
            r["query_hash"], r["query_text"], r["provider"], r["asset_url"],
            r["asset_type"], r["resolution_width"], r["resolution_height"],
            r["duration_s"], r["quality_score"], r["relevance_score"],
            r["license_type"], r["tags"],
        )
        inserted += 1
    return inserted


async def validate_urls(rows: list[dict[str, Any]], timeout_s: float = 8.0) -> list[tuple[dict, str]]:
    """HEAD each unique asset_url; return [(row, error)] for unreachable ones.

    Slow — meant for periodic CI runs, not the per-deploy bootstrap.
    """
    import httpx  # noqa: E402

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in rows:
        if r["asset_url"] in seen:
            continue
        seen.add(r["asset_url"])
        unique.append(r)

    bad: list[tuple[dict, str]] = []
    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
        async def _check(r: dict) -> None:
            try:
                resp = await client.head(r["asset_url"])
                if resp.status_code >= 400:
                    bad.append((r, f"HTTP {resp.status_code}"))
            except Exception as exc:
                bad.append((r, str(exc)[:160]))

        await asyncio.gather(*(_check(r) for r in unique))
    return bad


# ── CLI ─────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(description="Offline free-tier asset_library bootstrap")
    ap.add_argument("--niche", help="Limit to one niche (e.g. space, tech)")
    ap.add_argument("--check", action="store_true",
                    help="Parse + expand only; no DB writes")
    ap.add_argument("--validate-urls", action="store_true",
                    help="Also HEAD every asset_url and report unreachable rows")
    ap.add_argument("--seed", default=str(SEED_FILE),
                    help=f"Seed JSON path (default: {SEED_FILE})")
    args = ap.parse_args()

    seed = load_seed(Path(args.seed))
    rows = expand_to_rows(seed, niche=args.niche)
    print(f"loaded {len(seed['assets'])} assets · expanded to {len(rows)} (query, asset) rows")
    print(f"niches: {', '.join(list_niches(seed))}")

    if args.validate_urls:
        bad = asyncio.run(validate_urls(rows))
        if bad:
            print(f"\n{len(bad)} unreachable URL(s):")
            for r, err in bad:
                print(f"  - {r['asset_url']}  [{err}]")
        else:
            print("all URLs reachable")
        if args.check:
            return

    if args.check:
        # Print a couple rows for visual sanity
        for r in rows[:3]:
            print(f"  · {r['provider']:14s} {r['query_text']:30s} → {r['asset_url']}")
        if len(rows) > 3:
            print(f"  · …and {len(rows) - 3} more")
        return

    inserted = asyncio.run(insert_rows(rows))
    print(f"inserted {inserted} new rows ({len(rows) - inserted} already present)")


if __name__ == "__main__":
    main()
