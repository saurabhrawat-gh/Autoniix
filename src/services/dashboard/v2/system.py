"""System v2 — config management, emergency stop/resume, fleet health.

Endpoints:
  GET  /system/config               List all system_config entries
  PUT  /system/config               Update a single config key
  POST /system/emergency-stop       Freeze system + pause all workflows
  POST /system/emergency-resume     Un-freeze + resume all workflows
  GET  /system/fleet-health         Aggregate live health across fleet
  GET  /system/environment          Current environment mode
"""
from __future__ import annotations

import os

from pydantic import BaseModel
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from core.db import get_pool

from ._deps import Principal, audit, principal_dep, require_role

router = APIRouter()

_LEGACY = "http://localhost:8020"


async def _proxy(request: Request, method: str, path: str, **kwargs) -> dict:
    token = request.headers.get("Authorization", "")
    if not token:
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            token = f"Bearer {cookie_token}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(
                method,
                f"{_LEGACY}{path}",
                headers={"Authorization": token} if token else {},
                **kwargs,
            )
        if resp.status_code >= 400:
            detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise HTTPException(resp.status_code, detail)
        return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(502, f"Legacy BFF unreachable: {exc}") from exc




@router.get("/config")
async def get_config(_: Principal = Depends(principal_dep)):
    """List all system_config entries."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT config_key, config_value, description FROM system_config ORDER BY config_key"
    )
    return {
        "status": "ok",
        "data": [
            {"key": r["config_key"], "value": r["config_value"], "description": r["description"]}
            for r in rows
        ],
    }


class ConfigUpdateRequest(BaseModel):
    config_key: str
    config_value: str


@router.put("/config")
async def update_config(
    body: ConfigUpdateRequest,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    """Update a single system_config key."""
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE system_config SET config_value = $1, updated_at = NOW() WHERE config_key = $2",
        body.config_value, body.config_key,
    )
    if "UPDATE 0" in result:
        raise HTTPException(404, "Config key not found")
    await audit(
        actor=actor, action="system.config.update", target_type="system_config",
        target_id=body.config_key,
        after={"key": body.config_key, "value": body.config_value},
        request=request,
    )
    return {"status": "ok", "data": {"key": body.config_key, "value": body.config_value}}




@router.post("/emergency-stop")
async def emergency_stop(
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    """Freeze system + pause all running Temporal workflows."""
    result = await _proxy(request, "POST", "/api/emergency-stop")
    await audit(actor=actor, action="system.emergency_stop", target_type="system",
                target_id="global", request=request)
    return result


@router.post("/emergency-resume")
async def emergency_resume(
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    """Un-freeze system + resume all paused Temporal workflows."""
    result = await _proxy(request, "POST", "/api/emergency-resume")
    await audit(actor=actor, action="system.emergency_resume", target_type="system",
                target_id="global", request=request)
    return result




@router.get("/fleet-health")
async def fleet_health(
    request: Request,
    _: Principal = Depends(principal_dep),
):
    """Aggregate live health across the fleet (proxied from legacy BFF)."""
    return await _proxy(request, "GET", "/api/fleet-health")




@router.get("/environment")
async def get_environment(
    _: Principal = Depends(principal_dep),
):
    """Current environment mode — DB override first, then ENVIRONMENT_MODE env var."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'environment_mode'"
    )
    mode = row["config_value"] if row else os.getenv("ENVIRONMENT_MODE", "production")
    return {"status": "ok", "data": {"mode": mode}}


class EnvSwitchIn(BaseModel):
    mode: str
    confirm: bool = False


@router.put("/environment")
async def set_environment(
    body: EnvSwitchIn,
    actor: Principal = Depends(require_role("owner")),
):
    """Switch environment mode (owner-only). Persists to system_config."""
    if body.mode not in ("test", "production"):
        raise HTTPException(400, "mode must be 'test' or 'production'")
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO system_config (config_key, config_value, updated_at)
           VALUES ('environment_mode', $1, NOW())
           ON CONFLICT (config_key) DO UPDATE
               SET config_value = EXCLUDED.config_value,
                   updated_at   = NOW()""",
        body.mode,
    )
    return {"status": "ok", "data": {"mode": body.mode}}




@router.post("/clean-slate")
async def clean_slate(
    request: Request,
    actor: Principal = Depends(require_role("owner")),
):
    """Full reset: cancel workflows, truncate job tables, wipe storage. Owner-only."""
    result = await _proxy(
        request, "POST", "/api/admin/clean-slate",
        json={"confirm": "RESET"},
    )
    await audit(actor=actor, action="system.clean_slate", target_type="system",
                target_id="global", request=request)
    return result
