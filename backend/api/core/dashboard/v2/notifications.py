"""Notification center — Phase 4 (S4)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core.db import get_pool

from ._deps import Principal, audit, principal_dep, require_role

router = APIRouter()


class NotifyIn(BaseModel):
    event_type: str
    severity: str = "info"
    title: str
    body: str | None = None
    payload: dict = Field(default_factory=dict)
    channel_id: str | None = None
    video_id: str | None = None
    dedupe_key: str | None = None


class RouteIn(BaseModel):
    name: str
    event_pattern: str
    severity_min: str = "info"
    channels: list[str]
    filter: dict = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)
    enabled: bool = True


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    severity: str | None = None,
    limit: int = 100,
    p: Principal = Depends(principal_dep),
):
    where = ["1=1"]
    args: list = []
    if severity:
        args.append(severity)
        where.append(f"severity=${len(args)}")
    if unread_only and p.user_id is not None:
        args.append(p.user_id)
        where.append(f"NOT (${len(args)} = ANY(read_by))")
    args.append(limit)
    pool = await get_pool()
    rows = await pool.fetch(
        f"""SELECT id, event_type, severity, title, body, payload, channel_id, video_id,
                   dedupe_key, created_at, read_by
              FROM notifications
             WHERE {" AND ".join(where)}
             ORDER BY created_at DESC LIMIT ${len(args)}""",
        *args,
    )
    return {"data": [dict(r) for r in rows]}


@router.post("")
async def create_notification(
    body: NotifyIn,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    if body.dedupe_key:
        existing = await pool.fetchval(
            "SELECT id FROM notifications WHERE dedupe_key=$1 AND created_at > NOW() - INTERVAL '60 seconds'",
            body.dedupe_key,
        )
        if existing:
            return {"status": "ok", "id": existing, "deduped": True}
    nid = await pool.fetchval(
        """INSERT INTO notifications
            (event_type, severity, title, body, payload, channel_id, video_id, dedupe_key)
           VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8) RETURNING id""",
        body.event_type,
        body.severity,
        body.title,
        body.body,
        json.dumps(body.payload),
        body.channel_id,
        body.video_id,
        body.dedupe_key,
    )
    try:
        from services_api.dashboard.v2._notify import dispatch_routes

        await dispatch_routes(nid, body.model_dump())
    except Exception:
        pass
    return {"status": "ok", "id": nid}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    p: Principal = Depends(principal_dep),
):
    if p.user_id is None:
        return {"status": "noop"}
    pool = await get_pool()
    await pool.execute(
        "UPDATE notifications SET read_by = array_append(read_by, $1) WHERE id=$2 AND NOT ($1 = ANY(read_by))",
        p.user_id,
        notification_id,
    )
    return {"status": "ok"}


@router.get("/routes")
async def list_routes(_: Principal = Depends(require_role("owner", "member"))):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, name, event_pattern, severity_min, channels, filter, config, enabled "
        "FROM notification_routes ORDER BY id"
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/routes")
async def upsert_route(
    body: RouteIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    rid = await pool.fetchval(
        """INSERT INTO notification_routes
            (name, event_pattern, severity_min, channels, filter, config, enabled)
           VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7) RETURNING id""",
        body.name,
        body.event_pattern,
        body.severity_min,
        body.channels,
        json.dumps(body.filter),
        json.dumps(body.config),
        body.enabled,
    )
    await audit(
        actor=actor,
        action="notification.route.create",
        target_type="notification_route",
        target_id=str(rid),
        after=body.model_dump(),
        request=request,
    )
    return {"status": "ok", "id": rid}


@router.put("/routes/{route_id}")
async def update_route(
    route_id: int,
    body: RouteIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    res = await pool.execute(
        """UPDATE notification_routes
              SET name=$1, event_pattern=$2, severity_min=$3, channels=$4,
                  filter=$5::jsonb, config=$6::jsonb, enabled=$7
            WHERE id=$8""",
        body.name,
        body.event_pattern,
        body.severity_min,
        body.channels,
        json.dumps(body.filter),
        json.dumps(body.config),
        body.enabled,
        route_id,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Route not found")
    return {"status": "ok"}


@router.delete("/routes/{route_id}")
async def delete_route(
    route_id: int,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    await pool.execute("DELETE FROM notification_routes WHERE id=$1", route_id)
    await audit(
        actor=actor,
        action="notification.route.delete",
        target_type="notification_route",
        target_id=str(route_id),
        request=request,
    )
    return {"status": "ok"}


@router.get("/deliveries")
async def list_deliveries(
    notification_id: int | None = None,
    limit: int = 100,
    _: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    if notification_id is not None:
        rows = await pool.fetch(
            """SELECT id, notification_id, route_id, channel, status, attempts,
                      response, error, sent_at, created_at
                 FROM notification_deliveries WHERE notification_id=$1
                 ORDER BY created_at DESC LIMIT $2""",
            notification_id,
            limit,
        )
    else:
        rows = await pool.fetch(
            """SELECT id, notification_id, route_id, channel, status, attempts,
                      response, error, sent_at, created_at
                 FROM notification_deliveries
                 ORDER BY created_at DESC LIMIT $1""",
            limit,
        )
    return {"data": [dict(r) for r in rows]}
