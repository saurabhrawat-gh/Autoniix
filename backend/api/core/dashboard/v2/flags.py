"""Feature flag CRUD (read-only for non-admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from core.db import get_pool

from ._deps import Principal, audit, principal_dep, require_role

router = APIRouter()


@router.get("")
async def list_flags(_: Principal = Depends(principal_dep)):
    pool = await get_pool()
    rows = await pool.fetch("SELECT key, enabled, description, payload, updated_at FROM feature_flags ORDER BY key")
    return {"data": [dict(r) for r in rows]}


@router.put("/{key}")
async def set_flag(
    key: str,
    body: dict,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    enabled = bool(body.get("enabled", False))
    payload = body.get("payload") or {}
    before = await pool.fetchrow("SELECT enabled, payload FROM feature_flags WHERE key=$1", key)
    if not before:
        raise HTTPException(404, "Unknown flag")
    await pool.execute(
        "UPDATE feature_flags SET enabled=$1, payload=$2::jsonb, updated_at=NOW() WHERE key=$3",
        enabled,
        payload,
        key,
    )
    await audit(
        actor=actor,
        action="flag.update",
        target_type="feature_flag",
        target_id=key,
        before=dict(before),
        after={"enabled": enabled, "payload": payload},
        request=request,
    )
    return {"status": "ok"}
