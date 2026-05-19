"""User management — Phase 4 (S7)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.db import get_pool

from ._deps import Principal, audit, principal_dep, require_role

router = APIRouter()

_ROLES = ("owner", "admin", "producer", "editor", "viewer")


class RoleIn(BaseModel):
    role: str


@router.get("")
async def list_users(_: Principal = Depends(require_role("owner", "admin"))):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, email, display_name, role, mfa_enabled, email_verified, "
        "disabled, last_login_at, created_at FROM users ORDER BY id"
    )
    return {"data": [dict(r) for r in rows]}


@router.put("/{user_id}/role")
async def set_role(
    user_id: int, body: RoleIn, request: Request,
    actor: Principal = Depends(require_role("owner")),
):
    if body.role not in _ROLES:
        raise HTTPException(400, f"role must be one of {_ROLES}")
    pool = await get_pool()
    res = await pool.execute(
        "UPDATE users SET role=$1 WHERE id=$2", body.role, user_id
    )
    if res.endswith("0"):
        raise HTTPException(404, "User not found")
    await audit(actor=actor, action="user.role.set", target_type="user",
                target_id=str(user_id), after={"role": body.role}, request=request)
    return {"status": "ok"}


@router.put("/{user_id}/disable")
async def disable_user(
    user_id: int, request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    pool = await get_pool()
    await pool.execute("UPDATE users SET disabled=TRUE WHERE id=$1", user_id)
    await pool.execute("UPDATE sessions SET revoked_at=NOW() "
                       "WHERE user_id=$1 AND revoked_at IS NULL", user_id)
    await audit(actor=actor, action="user.disable", target_type="user",
                target_id=str(user_id), request=request)
    return {"status": "ok"}


@router.put("/{user_id}/enable")
async def enable_user(
    user_id: int, request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    pool = await get_pool()
    await pool.execute("UPDATE users SET disabled=FALSE WHERE id=$1", user_id)
    await audit(actor=actor, action="user.enable", target_type="user",
                target_id=str(user_id), request=request)
    return {"status": "ok"}
