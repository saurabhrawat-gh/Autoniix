"""End-to-end providers flow: clean-slate → add credential → chain → toggle.

Integration test — requires a reachable Postgres (app DB) with the
provider schema. Skips automatically when DB env isn't available or the
required tables/columns don't exist.

Run with: pytest tests/test_providers_e2e.py -v
"""
from __future__ import annotations

import os
import uuid
from typing import Any

import pytest

pytestmark = pytest.mark.asyncio


async def _maybe_pool():
    """Return an asyncpg pool against the app DB, or None if unavailable."""
    try:
        from src.db import get_pool
        pool = await get_pool()
        # Probe required columns; if migrations haven't been applied, skip.
        await pool.fetchval(
            "SELECT is_enabled FROM provider_chains_v2 LIMIT 1"
        )
        return pool
    except Exception:
        return None


@pytest.fixture
async def db():
    pool = await _maybe_pool()
    if pool is None:
        pytest.skip(
            "App DB unavailable or migration 202605140002 not applied; "
            "run `make infra && make migrate` to enable this test."
        )
    yield pool


async def _ensure_category_and_credential(pool, category: str, label: str) -> int:
    # Category must exist
    cat = await pool.fetchrow(
        "SELECT name FROM provider_categories WHERE name=$1", category,
    )
    if not cat:
        await pool.execute(
            "INSERT INTO provider_categories (name, label, kind) VALUES ($1,$2,$3) "
            "ON CONFLICT DO NOTHING",
            category, category, "llm",
        )
    cid = await pool.fetchval(
        """INSERT INTO provider_credentials
              (category, provider_name, label, vault_path, enabled)
           VALUES ($1, 'openai', $2, $3, TRUE)
           RETURNING id""",
        category, label, f"providers/{category}/openai/{label}",
    )
    return int(cid)


async def test_clean_slate_then_seed_then_resolve(db):
    """End-to-end: wipe → add credential → push to workspace chain →
    resolver sees it → disable credential → resolver returns EMPTY_CHAIN."""
    from scripts.clean_slate_providers import run as run_wipe
    from src.providers import chain as chain_mod

    category = f"llm.test_{uuid.uuid4().hex[:8]}"

    # 1. Clean slate.
    await run_wipe(verbose=False)
    rows = await db.fetch("SELECT 1 FROM provider_credentials")
    assert len(rows) == 0, "clean-slate did not empty provider_credentials"

    # 2. Add one credential.
    cid = await _ensure_category_and_credential(db, category, "primary")

    # 3. Push it into the workspace + mode-agnostic chain.
    await db.execute(
        """INSERT INTO provider_chains_v2
              (scope, scope_id, content_mode, category, position, credential_id, is_enabled)
           VALUES ('workspace', NULL, NULL, $1, 0, $2, TRUE)""",
        category, cid,
    )

    # 4. Resolver should return one row.
    chain_mod.invalidate()
    rows = await chain_mod._load_chain(
        category, channel_id=None, content_mode=None,
    )
    assert [r["id"] for r in rows] == [cid]

    # 5. Disable the chain entry → resolver returns zero rows.
    await db.execute(
        "UPDATE provider_chains_v2 SET is_enabled=FALSE "
        "WHERE category=$1 AND credential_id=$2",
        category, cid,
    )
    chain_mod.invalidate()
    rows = await chain_mod._load_chain(
        category, channel_id=None, content_mode=None,
    )
    assert rows == [], "disabled chain entry must be skipped"

    # 6. Re-enable entry but disable the credential → still empty.
    await db.execute(
        "UPDATE provider_chains_v2 SET is_enabled=TRUE "
        "WHERE category=$1 AND credential_id=$2",
        category, cid,
    )
    await db.execute(
        "UPDATE provider_credentials SET enabled=FALSE WHERE id=$1", cid,
    )
    chain_mod.invalidate()
    rows = await chain_mod._load_chain(
        category, channel_id=None, content_mode=None,
    )
    assert rows == [], "disabled credential must be skipped"

    # Cleanup
    await db.execute("DELETE FROM provider_chains_v2 WHERE category=$1", category)
    await db.execute("DELETE FROM provider_credentials WHERE id=$1", cid)


async def test_channel_override_beats_workspace(db):
    """Channel-scoped chain entry should resolve before workspace entries."""
    from src.providers import chain as chain_mod
    category = f"llm.test_{uuid.uuid4().hex[:8]}"
    ws_cid = await _ensure_category_and_credential(db, category, "workspace")
    ch_cid = await _ensure_category_and_credential(db, category, "channel")
    channel_id = f"CH_{uuid.uuid4().hex[:6]}"

    try:
        await db.execute(
            """INSERT INTO provider_chains_v2
                  (scope, scope_id, content_mode, category, position, credential_id, is_enabled)
               VALUES ('workspace', NULL, NULL, $1, 0, $2, TRUE),
                      ('channel',   $3,   NULL, $1, 0, $4, TRUE)""",
            category, ws_cid, channel_id, ch_cid,
        )
        chain_mod.invalidate()
        rows = await chain_mod._load_chain(
            category, channel_id=channel_id, content_mode=None,
        )
        ids = [r["id"] for r in rows]
        assert ids == [ch_cid, ws_cid], f"unexpected order: {ids}"
    finally:
        await db.execute("DELETE FROM provider_chains_v2 WHERE category=$1", category)
        await db.execute("DELETE FROM provider_credentials WHERE id = ANY($1::int[])",
                         [ws_cid, ch_cid])
