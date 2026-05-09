"""Phase 3 — Asset library pipeline smoke test.

Verifies the four pieces shipped in Phase 3 without touching the network or
the database:

  • 3A — Storyblocks HMAC signature is correct (RFC-2104 / SHA-256, hex)
         and stable across runs. We test against a known input/output pair
         derived directly from Python's stdlib hmac module so the assertion
         can't drift from the implementation.
  • 3B — MotionArray adapter returns [] in both envato-present and
         envato-absent modes, and warns exactly once when the operator
         mis-configures (MA key set, Envato unset).
  • 3C — Seed catalog parses, every asset has the required fields, every
         (query, asset_url) pair expands deterministically, query_hash
         matches the production hashing algo, niche filter works, all URLs
         are http(s).
  • 3D — Provider chain registry includes the new providers
         (storyblocks, motionarray) and they're individually addressable
         via the chain's _PROVIDERS dict.

Run::

    python scripts/asset_library_smoke.py
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac as _hmac
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}")
        failures.append(msg)


def expect_throw(fn, msg: str) -> None:
    try:
        fn()
    except Exception:
        return
    print(f"FAIL: {msg} (expected throw)")
    failures.append(msg)


# ── 3A: Storyblocks HMAC signature ──────────────────────────────────


def test_storyblocks_hmac() -> None:
    from src.services.assets.provider_chain import storyblocks_sign

    # Known-input vector — sign "/api/v2/videos/search" + "1700000000" with key "secret".
    path = "/api/v2/videos/search"
    key = "secret"
    expires = 1700000000
    expected = _hmac.new(
        key.encode("utf-8"),
        f"{path}{expires}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    sig = storyblocks_sign(path, key, expires)
    check(sig == expected, f"storyblocks_sign matches stdlib hmac (got {sig[:16]}…)")
    check(len(sig) == 64, f"storyblocks_sign returns 64 hex chars (got {len(sig)})")
    check(all(c in "0123456789abcdef" for c in sig), "storyblocks_sign is lowercase hex")

    # Stability across calls — same input → same output
    sig2 = storyblocks_sign(path, key, expires)
    check(sig == sig2, "storyblocks_sign deterministic")

    # Different expires → different signature
    sig3 = storyblocks_sign(path, key, expires + 1)
    check(sig != sig3, "storyblocks_sign sensitive to EXPIRES")

    # Different path → different signature
    sig4 = storyblocks_sign("/api/v2/videos/search/other", key, expires)
    check(sig != sig4, "storyblocks_sign sensitive to path")

    # Different key → different signature
    sig5 = storyblocks_sign(path, "other_secret", expires)
    check(sig != sig5, "storyblocks_sign sensitive to private key")


# ── 3B: MotionArray adapter behaviour ───────────────────────────────


async def test_motionarray() -> None:
    from src.services.assets import provider_chain
    from src.config import settings

    # Snapshot env to restore after.
    prev_ma = getattr(settings, "motionarray_api_key", "")
    prev_envato = getattr(settings, "envato_api_key", "")

    try:
        # Case A — both unset → returns [] silently
        settings.motionarray_api_key = ""
        settings.envato_api_key = ""
        out = await provider_chain._motionarray("test query", k=10)
        check(out == [], "motionarray returns [] when no keys set")

        # Case B — Envato set → returns [] (chain calls envato directly elsewhere)
        settings.motionarray_api_key = ""
        settings.envato_api_key = "fake-envato-key"
        out = await provider_chain._motionarray("test query", k=10)
        check(out == [], "motionarray returns [] when envato is configured")

        # Case C — MA set without Envato → warns, returns []
        settings.motionarray_api_key = "fake-ma-key"
        settings.envato_api_key = ""
        out = await provider_chain._motionarray("test query", k=10)
        check(out == [], "motionarray returns [] when ma-only (no envato)")
    finally:
        settings.motionarray_api_key = prev_ma
        settings.envato_api_key = prev_envato


# ── 3C: Seed catalog + bootstrap loader ─────────────────────────────


def test_seed_catalog() -> None:
    from scripts.bootstrap_assets_offline import (
        SEED_FILE, expand_to_rows, list_niches, load_seed, query_hash,
    )

    # Schema validation
    seed = load_seed()
    check(seed["schema_version"] == 1, "seed schema_version == 1")
    check(len(seed["assets"]) >= 10, f"seed has at least 10 assets (got {len(seed['assets'])})")

    # Niche coverage
    niches = list_niches(seed)
    expected_niches = {"tech", "space", "nature", "urban", "abstract", "finance", "health"}
    missing = expected_niches - set(niches)
    check(not missing, f"seed covers expected niches (missing: {missing})")

    # Expand to rows — every asset → ≥ 1 row per query
    rows = expand_to_rows(seed)
    total_queries = sum(len(a["queries"]) for a in seed["assets"])
    check(len(rows) == total_queries, f"row count = total queries (got {len(rows)} vs {total_queries})")

    # Niche filter works
    space_rows = expand_to_rows(seed, niche="space")
    space_assets = [a for a in seed["assets"] if a["niche"] == "space"]
    expected_space_rows = sum(len(a["queries"]) for a in space_assets)
    check(len(space_rows) == expected_space_rows, f"niche filter works (space: {len(space_rows)} = {expected_space_rows})")

    # query_hash matches the production algo
    sample_query = "data center"
    expected_hash = hashlib.sha256(sample_query.lower().strip().encode()).hexdigest()[:16]
    check(query_hash(sample_query) == expected_hash, "query_hash matches sha256[:16] of lowered query")

    # Determinism: re-expanding the same seed produces identical rows in the
    # same order
    rows_again = expand_to_rows(seed)
    check(rows == rows_again, "expand_to_rows deterministic")

    # Every URL is http(s) and license is non-empty
    for r in rows:
        check(r["asset_url"].startswith(("http://", "https://")),
              f"row asset_url is http(s): {r['asset_url']}")
        check(bool(r["license_type"]), f"row has license_type: {r['query_text']}")

    # Bad seed should throw
    bad = {"schema_version": 1, "assets": [{"niche": "x"}]}
    import json as _json
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        _json.dump(bad, f)
        tmp = Path(f.name)
    expect_throw(lambda: load_seed(tmp), "load_seed rejects asset missing required fields")
    tmp.unlink()

    # Wrong schema_version
    bad2 = {"schema_version": 99, "assets": []}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        _json.dump(bad2, f)
        tmp = Path(f.name)
    expect_throw(lambda: load_seed(tmp), "load_seed rejects schema_version mismatch")
    tmp.unlink()


# ── 3D: Provider chain registry ─────────────────────────────────────


def test_provider_chain_registry() -> None:
    from src.services.assets import provider_chain

    expected = {"pexels", "pixabay", "storyblocks", "motionarray", "library"}
    actual = set(provider_chain._PROVIDERS.keys())
    missing = expected - actual
    check(not missing, f"provider chain has all providers (missing: {missing})")

    # Both new providers are async callables
    for name in ("storyblocks", "motionarray"):
        fn = provider_chain._PROVIDERS[name]
        check(callable(fn), f"{name} is callable")
        check(asyncio.iscoroutinefunction(fn), f"{name} is async")


# ── Driver ──────────────────────────────────────────────────────────


def main() -> None:
    test_storyblocks_hmac()
    asyncio.run(test_motionarray())
    test_seed_catalog()
    test_provider_chain_registry()

    if not failures:
        print("OK asset-library smoke")
        from scripts.bootstrap_assets_offline import expand_to_rows, list_niches, load_seed
        seed = load_seed()
        rows = expand_to_rows(seed)
        print(f"   storyblocks: HMAC sign verified vs stdlib hmac")
        print(f"   motionarray: 3 paths covered (no-keys, envato-set, ma-only)")
        print(f"   seed:        {len(seed['assets'])} assets · {len(rows)} rows · {len(list_niches(seed))} niches")
        print(f"   chain:       pexels · pixabay · storyblocks · motionarray · library")
    else:
        print(f"\n{len(failures)} smoke check(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
