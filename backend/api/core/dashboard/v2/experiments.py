"""A/B testing — proxy to the Admin service's experiments API.

The Admin service (``http://admin:8009``) owns the canonical endpoints
under :pyfunc:`services_api.experiments.ab_framework`. We expose a thin
v2 wrapper so the dashboard UI can use a single ``/api/v2/...`` namespace
and benefit from the principal/role checks and audit logging.
"""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ._deps import Principal, audit, principal_dep, require_role

router = APIRouter()

ADMIN_BASE = "http://admin:8009"


class ExperimentCreateIn(BaseModel):
    name: str
    description: str = ""
    variants: list[dict] = Field(default_factory=list)
    traffic_pct: float = 100.0
    target_metric: str = "views"


async def _admin_call(method: str, path: str, **kwargs) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.request(method, ADMIN_BASE + path, **kwargs)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"admin upstream error: {exc}")


@router.get("")
async def list_experiments(
    status: str = Query("", description="filter: draft|active|paused|completed"),
    _: Principal = Depends(principal_dep),
):
    payload = await _admin_call("GET", f"/experiments?status={status}")
    return {"data": (payload.get("data") or {}).get("experiments", [])}


@router.post("")
async def create_experiment(
    body: ExperimentCreateIn, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    payload = await _admin_call("POST", "/experiments", json=body.model_dump())
    await audit(actor=actor, action="experiment.create", target_type="experiment",
                target_id=body.name, after=body.model_dump(), request=request)
    return payload


@router.post("/{name}/activate")
async def activate(
    name: str, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    payload = await _admin_call("POST", f"/experiments/{name}/activate")
    await audit(actor=actor, action="experiment.activate", target_type="experiment",
                target_id=name, request=request)
    return payload


@router.post("/{name}/pause")
async def pause(
    name: str, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    payload = await _admin_call("POST", f"/experiments/{name}/pause")
    await audit(actor=actor, action="experiment.pause", target_type="experiment",
                target_id=name, request=request)
    return payload


@router.post("/{name}/complete")
async def complete(
    name: str, request: Request,
    winner: str = Query("", description="Variant name of the winner (optional)"),
    actor: Principal = Depends(require_role("owner", "member")),
):
    payload = await _admin_call("POST", f"/experiments/{name}/complete?winner={winner}")
    await audit(actor=actor, action="experiment.complete", target_type="experiment",
                target_id=name, after={"winner": winner}, request=request)
    return payload


@router.get("/{name}/results")
async def results(name: str, _: Principal = Depends(principal_dep)):
    return await _admin_call("GET", f"/experiments/{name}/results")
