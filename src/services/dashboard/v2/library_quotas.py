"""Storage quota endpoints + helpers (AE-364 / Library Sprint).

Three responsibilities:

1. **Aggregator** — refresh ``storage_quotas.used_bytes`` for every scope
   that has assets. Called on demand from the dashboard; a scheduled
   trigger is a follow-up ticket.
2. **Pre-upload check** — :func:`check_quota_before_upload` returns the
   remaining headroom for a (scope, scope_id) so the upload endpoint can
   reject early with a 413 if a payload would push the scope over its
   quota.
3. **Read API** — ``GET /library/dam/quotas`` and
   ``POST /library/dam/quotas/recalculate`` so the dashboard can show
   usage meters and let an operator force-refresh.

The aggregator does NOT auto-create quota rows on first sight — that
would force ops to remember to set sensible values per workspace. Instead
it falls back to the ``library.default_quotas`` system_config row when a
(scope, scope_id) has no explicit quota.
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from src.db import get_pool

from ._deps import Principal, principal_dep, require_role

logger = structlog.get_logger()


_DEFAULT_QUOTAS = {
    "workspace_bytes": 100 * 1024 ** 3,
    "brand_bytes":      25 * 1024 ** 3,
    "channel_bytes":    10 * 1024 ** 3,
    "project_bytes":     5 * 1024 ** 3,
}


async def _load_default_quotas() -> dict:
    pool = await get_pool()
    try:
        row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = $1",
            "library.default_quotas",
        )
    except Exception:
        return _DEFAULT_QUOTAS
    if not row:
        return _DEFAULT_QUOTAS
    try:
        merged = dict(_DEFAULT_QUOTAS)
        merged.update(json.loads(row["config_value"]) or {})
        return merged
    except json.JSONDecodeError:
        return _DEFAULT_QUOTAS


def _default_quota_for(scope: str, defaults: dict) -> int:
    return int(defaults.get(f"{scope}_bytes", 0))


async def recalculate_quotas() -> int:
    """Refresh ``used_bytes`` for every (scope, scope_id) that holds assets.

    Returns the number of (scope, scope_id) rows touched. Safe to call
    repeatedly; it UPSERTs into ``storage_quotas`` and never deletes.
    """
    pool = await get_pool()
    defaults = await _load_default_quotas()
    rows = await pool.fetch(
        """
        SELECT scope,
               COALESCE(scope_id, '')           AS scope_id,
               COALESCE(SUM(bytes), 0)::bigint  AS used_bytes
          FROM dam_assets
         WHERE deleted_at IS NULL
         GROUP BY scope, COALESCE(scope_id, '')
        """,
    )
    touched = 0
    for r in rows:
        await pool.execute(
            """
            INSERT INTO storage_quotas (scope, scope_id, quota_bytes, used_bytes, calculated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (scope, scope_id) DO UPDATE
                SET used_bytes    = EXCLUDED.used_bytes,
                    calculated_at = NOW()
            """,
            r["scope"],
            r["scope_id"],
            _default_quota_for(r["scope"], defaults),
            int(r["used_bytes"]),
        )
        touched += 1
    return touched


async def check_quota_before_upload(scope: str, scope_id: str | None,
                                    incoming_bytes: int) -> dict:
    """Return ``{ok: bool, remaining_bytes, quota_bytes, used_bytes}``.

    A scope with ``quota_bytes = 0`` is treated as unlimited. Operators
    use 0 to lift the cap for a specific scope without dropping the row.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT quota_bytes, used_bytes "
        "  FROM storage_quotas "
        " WHERE scope = $1 AND scope_id = $2",
        scope,
        scope_id or "",
    )
    if row is None:
        return {
            "ok": True,
            "quota_bytes": 0,
            "used_bytes": 0,
            "remaining_bytes": -1,
            "note": "no quota row — treat as unlimited",
        }
    quota = int(row["quota_bytes"])
    used = int(row["used_bytes"])
    if quota <= 0:
        return {
            "ok": True,
            "quota_bytes": quota,
            "used_bytes": used,
            "remaining_bytes": -1,
        }
    remaining = quota - used
    return {
        "ok": (incoming_bytes <= remaining),
        "quota_bytes": quota,
        "used_bytes": used,
        "remaining_bytes": remaining,
    }


router = APIRouter()


@router.get("/dam/quotas")
async def list_quotas(
    scope: str | None = Query(None),
    _: Principal = Depends(principal_dep),
):
    """Current per-scope quota and usage."""
    pool = await get_pool()
    if scope:
        rows = await pool.fetch(
            "SELECT * FROM storage_quotas WHERE scope = $1 ORDER BY scope_id",
            scope,
        )
    else:
        rows = await pool.fetch("SELECT * FROM storage_quotas ORDER BY scope, scope_id")
    return {"data": [dict(r) for r in rows], "count": len(rows)}


@router.post("/dam/quotas/recalculate")
async def recalculate(
    _: Principal = Depends(require_role("owner", "member")),
):
    """Refresh ``used_bytes`` for every scope — owner / member only."""
    try:
        touched = await recalculate_quotas()
    except Exception as exc:
        logger.warning("quotas.recalculate_failed", error=str(exc))
        raise HTTPException(500, "quota recalculation failed")
    return {"status": "ok", "touched": touched}
