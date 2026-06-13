"""License catalogue + expiry endpoints (AE-363 / Library Sprint).

Wires the existing ``dam_assets.license`` / ``license_url`` / ``expires_at``
columns into the dashboard:

* ``GET /library/dam/license-catalogue`` — returns the locked vocabulary
  (seeded in ``system_config`` by the 202606131930 migration) so the
  upload form can render a controlled dropdown.

* ``GET /library/dam/licenses/expiring`` — assets whose license expires
  in the next ``within_days`` (default 30) so the dashboard can show a
  warning banner and the ops team can plan replacements.

* ``GET /library/dam/licenses/audit`` — group-by-license counts +
  unknown-license count for the audit page.
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query

from src.db import get_pool

from ._deps import Principal, principal_dep

logger = structlog.get_logger()


def _catalogue_fallback() -> list[dict]:
    """Default vocabulary used when system_config row is missing."""
    return [
        {"id": "creative-commons-0",   "label": "CC0 (Public Domain)", "commercial": True, "attribution": False},
        {"id": "creative-commons-by",  "label": "CC BY", "commercial": True, "attribution": True},
        {"id": "royalty-free",         "label": "Royalty-Free", "commercial": True, "attribution": False},
        {"id": "proprietary-internal", "label": "Proprietary / Internal", "commercial": True, "attribution": False},
        {"id": "unknown",              "label": "Unknown (Flagged)", "commercial": False, "attribution": True},
    ]


router = APIRouter()


@router.get("/dam/license-catalogue")
async def license_catalogue(_: Principal = Depends(principal_dep)):
    """Locked vocabulary for the upload form's license dropdown (AE-363)."""
    pool = await get_pool()
    try:
        row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = $1",
            "library.license_catalogue",
        )
    except Exception as exc:
        logger.warning("license_catalogue.lookup_failed", error=str(exc))
        return {"data": _catalogue_fallback(), "source": "fallback"}
    if not row:
        return {"data": _catalogue_fallback(), "source": "fallback"}
    try:
        return {"data": json.loads(row["config_value"]), "source": "system_config"}
    except json.JSONDecodeError:
        logger.warning("license_catalogue.invalid_json")
        return {"data": _catalogue_fallback(), "source": "fallback"}


@router.get("/dam/licenses/expiring")
async def licenses_expiring(
    within_days: int = Query(30, ge=1, le=365),
    scope: str = Query("workspace"),
    scope_id: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    _: Principal = Depends(principal_dep),
):
    """Assets whose license expires in the next ``within_days``.

    Returns rows already-expired (``expires_at <= NOW()``) PLUS those
    expiring within the configured window. The dashboard renders both
    groups so reviewers can react to both immediately-stale and
    soon-to-be-stale assets.
    """
    pool = await get_pool()
    args: list[Any] = [scope, within_days]
    cond_scope = ""
    if scope_id:
        args.append(scope_id)
        cond_scope = f" AND scope_id = ${len(args)}"
    args.append(limit)
    rows = await pool.fetch(
        f"""
        SELECT id, scope, scope_id, kind, display_name, license, license_url,
               expires_at, tags, created_at,
               (expires_at <= NOW())                                       AS expired,
               GREATEST(0, EXTRACT(EPOCH FROM (expires_at - NOW())) / 86400.0)::int
                                                                           AS days_until_expiry
          FROM dam_assets
         WHERE deleted_at IS NULL
           AND scope = $1
           AND expires_at IS NOT NULL
           AND expires_at <= (NOW() + ($2 || ' days')::interval)
           {cond_scope}
         ORDER BY expires_at ASC
         LIMIT ${len(args)}
        """,
        *args,
    )
    return {
        "data": [dict(r) for r in rows],
        "count": len(rows),
        "within_days": within_days,
    }


@router.get("/dam/licenses/audit")
async def licenses_audit(
    scope: str = Query("workspace"),
    scope_id: str | None = Query(None),
    _: Principal = Depends(principal_dep),
):
    """Group-by-license counts + unknown-license count for the audit page."""
    pool = await get_pool()
    args: list[Any] = [scope]
    cond_scope = ""
    if scope_id:
        args.append(scope_id)
        cond_scope = f" AND scope_id = ${len(args)}"
    rows = await pool.fetch(
        f"""
        SELECT COALESCE(NULLIF(license, ''), 'unspecified') AS license,
               COUNT(*)                                     AS asset_count,
               COALESCE(SUM(bytes), 0)::bigint              AS total_bytes,
               COUNT(*) FILTER (WHERE expires_at IS NOT NULL AND expires_at <= NOW())
                                                            AS expired_count,
               COUNT(*) FILTER (
                   WHERE expires_at IS NOT NULL
                     AND expires_at >  NOW()
                     AND expires_at <= NOW() + INTERVAL '30 days'
               )                                            AS expiring_30d
          FROM dam_assets
         WHERE deleted_at IS NULL
           AND scope = $1
           {cond_scope}
         GROUP BY COALESCE(NULLIF(license, ''), 'unspecified')
         ORDER BY asset_count DESC
        """,
        *args,
    )
    return {"data": [dict(r) for r in rows], "count": len(rows)}
