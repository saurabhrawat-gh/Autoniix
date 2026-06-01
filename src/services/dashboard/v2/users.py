"""User management — Phase 4 (S7)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.db import get_pool

from ._deps import Principal, audit, principal_dep, require_global_role

router = APIRouter()

_GLOBAL_ROLES = ("superadmin", "user")


class RoleIn(BaseModel):
    role: str


@router.get("")
async def list_users(_: Principal = Depends(require_global_role("superadmin"))):
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT u.id, u.email, u.display_name, u.role AS global_role,
                  u.mfa_enabled, u.email_verified, u.disabled,
                  u.last_login_at, u.created_at,
                  COALESCE(
                      JSON_AGG(
                          JSON_BUILD_OBJECT(
                              'workspace_id',   wm.workspace_id,
                              'workspace_name',  w.name,
                              'workspace_role',  wm.role
                          ) ORDER BY w.name
                      ) FILTER (WHERE wm.workspace_id IS NOT NULL),
                      '[]'::json
                  ) AS workspaces
             FROM users u
             LEFT JOIN workspace_members wm ON wm.user_id = u.id
             LEFT JOIN workspaces w ON w.id = wm.workspace_id
            GROUP BY u.id
            ORDER BY u.id"""
    )
    import json as _json
    result = []
    for r in rows:
        row = dict(r)
        if isinstance(row.get("workspaces"), str):
            row["workspaces"] = _json.loads(row["workspaces"])
        result.append(row)
    return {"data": result}


@router.put("/{user_id}/role")
async def set_role(
    user_id: int, body: RoleIn, request: Request,
    actor: Principal = Depends(require_global_role("superadmin")),
):
    if body.role not in _GLOBAL_ROLES:
        raise HTTPException(400, f"role must be one of {_GLOBAL_ROLES}")
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
    actor: Principal = Depends(require_global_role("superadmin")),
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
    actor: Principal = Depends(require_global_role("superadmin")),
):
    pool = await get_pool()
    await pool.execute("UPDATE users SET disabled=FALSE WHERE id=$1", user_id)
    await audit(actor=actor, action="user.enable", target_type="user",
                target_id=str(user_id), request=request)
    return {"status": "ok"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int, request: Request,
    actor: Principal = Depends(require_global_role("superadmin")),
):
    if actor.user_id == user_id:
        raise HTTPException(400, "Cannot delete your own account — use the profile page to delete it")
    pool = await get_pool()
    target = await pool.fetchrow("SELECT role FROM users WHERE id=$1", user_id)
    if not target:
        raise HTTPException(404, "User not found")
    if target["role"] == "superadmin":
        owner_count = await pool.fetchval("SELECT COUNT(*) FROM users WHERE role='superadmin' AND disabled=FALSE")
        if (owner_count or 0) <= 1:
            raise HTTPException(409, "Cannot delete the last superadmin")
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE sessions SET revoked_at=NOW() WHERE user_id=$1 AND revoked_at IS NULL", user_id
            )
            await conn.execute("DELETE FROM workspace_members WHERE user_id=$1", user_id)
            await conn.execute(
                """UPDATE users SET
                   email=$1, password_hash=NULL, display_name='Deleted User',
                   disabled=TRUE, mfa_enabled=FALSE, mfa_secret=NULL
                   WHERE id=$2""",
                f"deleted-{user_id}@deleted.local", user_id,
            )
    await audit(actor=actor, action="user.delete", target_type="user",
                target_id=str(user_id), request=request)
    return {"status": "ok"}
