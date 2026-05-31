"""Workspace / Brand / Series / Campaign / Project hierarchy — Wave 1.

Endpoints
---------
Workspaces
  GET    /workspace                           current workspace info
  PUT    /workspace                           update workspace settings

Brands
  GET    /workspace/brands
  POST   /workspace/brands
  GET    /workspace/brands/{id}
  PUT    /workspace/brands/{id}

Series
  GET    /workspace/series?channel_id=
  POST   /workspace/series
  PUT    /workspace/series/{id}
  DELETE /workspace/series/{id}

Campaigns
  GET    /workspace/campaigns
  POST   /workspace/campaigns
  PUT    /workspace/campaigns/{id}

Projects
  GET    /workspace/projects?channel_id=&status=&series_id=&campaign_id=
  POST   /workspace/projects
  GET    /workspace/projects/{id}
  PUT    /workspace/projects/{id}
  DELETE /workspace/projects/{id}

Members
  GET    /workspace/members
  PUT    /workspace/members/{user_id}/role
  DELETE /workspace/members/{user_id}

Invitations
  GET    /workspace/invites
  POST   /workspace/invites
  DELETE /workspace/invites/{id}

Entity settings
  GET    /workspace/settings?scope=&scope_id=
  PUT    /workspace/settings          (upsert key/value)
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from src.db import get_pool
from ._deps import Principal, audit, principal_dep, require_permission, require_role

router = APIRouter()

# Plan member limits (None = unlimited)
_PLAN_MEMBER_LIMITS: dict[str, int | None] = {
    "starter":    3,
    "growth":     10,
    "scale":      None,
    "enterprise": None,
}


async def _notify_slack(webhook_url: str, message: str) -> None:
    """Best-effort Slack notification — never raises."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(webhook_url, json={"text": message})
    except Exception:
        pass


# Pydantic models

class WorkspacePatch(BaseModel):
    name: str | None = None
    timezone: str | None = None
    monthly_budget_usd: float | None = None
    logo_url: str | None = None
    settings: dict | None = None


class BrandIn(BaseModel):
    name: str
    slug: str | None = None
    description: str | None = None
    legal_name: str | None = None
    website: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    logo_url: str | None = None
    voice_summary: str | None = None
    settings: dict = Field(default_factory=dict)


class BrandPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    legal_name: str | None = None
    website: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    logo_url: str | None = None
    voice_summary: str | None = None
    settings: dict | None = None


class SeriesIn(BaseModel):
    channel_id: str
    name: str
    description: str | None = None
    format: str | None = None
    target_duration_s: int | None = None
    cadence: str | None = None
    thumbnail_style: str | None = None
    settings: dict = Field(default_factory=dict)


class SeriesPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    format: str | None = None
    target_duration_s: int | None = None
    cadence: str | None = None
    thumbnail_style: str | None = None
    is_active: bool | None = None
    settings: dict | None = None


class CampaignIn(BaseModel):
    brand_id: int
    name: str
    description: str | None = None
    theme: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    kpi_targets: dict = Field(default_factory=dict)


class CampaignPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    theme: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    kpi_targets: dict | None = None
    status: str | None = None


class ProjectIn(BaseModel):
    channel_id: str
    title: str
    brief: str | None = None
    series_id: int | None = None
    campaign_id: int | None = None
    parent_project_id: int | None = None
    branch_label: str | None = None
    status: str = "idea"
    priority: int = 5
    target_publish_at: str | None = None
    tags: list[str] = Field(default_factory=list)
    settings: dict = Field(default_factory=dict)


class ProjectPatch(BaseModel):
    title: str | None = None
    brief: str | None = None
    status: str | None = None
    priority: int | None = None
    target_publish_at: str | None = None
    tags: list[str] | None = None
    series_id: int | None = None
    campaign_id: int | None = None
    settings: dict | None = None


class MemberRolePatch(BaseModel):
    role: str


class EntitySettingUpsert(BaseModel):
    scope: str
    scope_id: str
    key: str
    value: Any
    locked: bool = False


# Workspace

@router.get("")
async def get_workspace(p: Principal = Depends(principal_dep)):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, slug, plan, billing_email, monthly_budget_usd, timezone, logo_url, settings, created_at, updated_at "
        "FROM workspaces WHERE id = $1",
        p.workspace_id,
    )
    if not row:
        return {"data": None}
    w = dict(row)
    w["settings"] = json.loads(w["settings"]) if isinstance(w["settings"], str) else w["settings"]
    return {"data": w}


@router.put("")
async def update_workspace(
    body: WorkspacePatch,
    request: Request,
    actor: Principal = Depends(require_permission("workspace.settings.edit")),
):
    pool = await get_pool()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return {"status": "noop"}
    sets, vals = [], []
    for k, v in updates.items():
        sets.append(f"{k}=${len(vals)+1}" + ("::jsonb" if k == "settings" else ""))
        vals.append(json.dumps(v) if k == "settings" else v)
    vals.append(actor.workspace_id)
    await pool.execute(
        f"UPDATE workspaces SET {', '.join(sets)}, updated_at=NOW() WHERE id=${len(vals)}",
        *vals,
    )
    await audit(actor=actor, action="workspace.update", target_type="workspace",
                target_id=str(actor.workspace_id), after=updates, request=request)
    return {"status": "ok"}


# Brands

@router.get("/brands")
async def list_brands(p: Principal = Depends(principal_dep)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, name, slug, description, legal_name, website, primary_color, secondary_color, "
        "logo_url, voice_summary, settings, created_at, updated_at "
        "FROM brands WHERE workspace_id = $1 ORDER BY name",
        p.workspace_id,
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/brands")
async def create_brand(
    body: BrandIn,
    request: Request,
    actor: Principal = Depends(require_permission("channel.create")),
):
    pool = await get_pool()
    slug = body.slug or "".join(c for c in body.name.lower().replace(" ", "-") if c.isalnum() or c == "-")
    bid = await pool.fetchval(
        """INSERT INTO brands (workspace_id, name, slug, description, legal_name, website,
               primary_color, secondary_color, logo_url, voice_summary, settings, created_by)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12) RETURNING id""",
        actor.workspace_id, body.name, slug, body.description, body.legal_name, body.website,
        body.primary_color, body.secondary_color, body.logo_url, body.voice_summary,
        json.dumps(body.settings), actor.user_id,
    )
    await audit(actor=actor, action="brand.create", target_type="brand",
                target_id=str(bid), after={"name": body.name}, request=request)
    return {"status": "ok", "id": bid}


@router.get("/brands/{brand_id}")
async def get_brand(brand_id: int, p: Principal = Depends(principal_dep)):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, slug, description, legal_name, website, primary_color, secondary_color, "
        "logo_url, voice_summary, settings, created_at, updated_at FROM brands WHERE id=$1 AND workspace_id=$2",
        brand_id, p.workspace_id,
    )
    if not row:
        raise HTTPException(404, "Brand not found")
    return {"data": dict(row)}


@router.put("/brands/{brand_id}")
async def update_brand(
    brand_id: int,
    body: BrandPatch,
    request: Request,
    actor: Principal = Depends(require_permission("channel.settings.edit")),
):
    pool = await get_pool()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return {"status": "noop"}
    sets, vals = [], []
    for k, v in updates.items():
        sets.append(f"{k}=${len(vals)+1}" + ("::jsonb" if k == "settings" else ""))
        vals.append(json.dumps(v) if k == "settings" else v)
    vals.extend([brand_id, actor.workspace_id])
    res = await pool.execute(
        f"UPDATE brands SET {', '.join(sets)}, updated_at=NOW() WHERE id=${len(vals)-1} AND workspace_id=${len(vals)}",
        *vals,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Brand not found")
    await audit(actor=actor, action="brand.update", target_type="brand",
                target_id=str(brand_id), after=updates, request=request)
    return {"status": "ok"}


# Series

@router.get("/series")
async def list_series(
    channel_id: str | None = Query(None),
    p: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    if channel_id:
        rows = await pool.fetch(
            "SELECT id, channel_id, name, description, format, target_duration_s, cadence, "
            "thumbnail_style, is_active, settings, created_at FROM series WHERE channel_id=$1 ORDER BY name",
            channel_id,
        )
    else:
        rows = await pool.fetch(
            "SELECT s.id, s.channel_id, s.name, s.description, s.format, s.target_duration_s, s.cadence, "
            "s.thumbnail_style, s.is_active, s.settings, s.created_at "
            "FROM series s JOIN channels c ON c.channel_id = s.channel_id "
            "WHERE c.workspace_id = $1 ORDER BY s.name",
            p.workspace_id,
        )
    return {"data": [dict(r) for r in rows]}


@router.post("/series")
async def create_series(
    body: SeriesIn,
    request: Request,
    actor: Principal = Depends(require_permission("project.create")),
):
    pool = await get_pool()
    sid = await pool.fetchval(
        """INSERT INTO series (channel_id, name, description, format, target_duration_s,
               cadence, thumbnail_style, settings, created_by)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9) RETURNING id""",
        body.channel_id, body.name, body.description, body.format,
        body.target_duration_s, body.cadence, body.thumbnail_style,
        json.dumps(body.settings), actor.user_id,
    )
    await audit(actor=actor, action="series.create", target_type="series",
                target_id=str(sid), after={"name": body.name}, request=request)
    return {"status": "ok", "id": sid}


@router.put("/series/{series_id}")
async def update_series(
    series_id: int,
    body: SeriesPatch,
    request: Request,
    actor: Principal = Depends(require_permission("project.edit")),
):
    pool = await get_pool()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return {"status": "noop"}
    sets, vals = [], []
    for k, v in updates.items():
        sets.append(f"{k}=${len(vals)+1}" + ("::jsonb" if k == "settings" else ""))
        vals.append(json.dumps(v) if k == "settings" else v)
    vals.append(series_id)
    res = await pool.execute(
        f"UPDATE series SET {', '.join(sets)}, updated_at=NOW() WHERE id=${len(vals)}",
        *vals,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Series not found")
    await audit(actor=actor, action="series.update", target_type="series",
                target_id=str(series_id), after=updates, request=request)
    return {"status": "ok"}


@router.delete("/series/{series_id}")
async def delete_series(
    series_id: int,
    request: Request,
    actor: Principal = Depends(require_permission("project.delete")),
):
    pool = await get_pool()
    res = await pool.execute("DELETE FROM series WHERE id=$1", series_id)
    if res.endswith("0"):
        raise HTTPException(404, "Series not found")
    await audit(actor=actor, action="series.delete", target_type="series",
                target_id=str(series_id), request=request)
    return {"status": "ok"}


# Campaigns

@router.get("/campaigns")
async def list_campaigns(
    brand_id: int | None = Query(None),
    status: str | None = Query(None),
    p: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    args = [p.workspace_id]
    where = ["b.workspace_id = $1"]
    if brand_id:
        args.append(brand_id)
        where.append(f"c.brand_id = ${len(args)}")
    if status:
        args.append(status)
        where.append(f"c.status = ${len(args)}")

    rows = await pool.fetch(
        f"""SELECT c.id, c.brand_id, c.name, c.description, c.theme, c.start_at, c.end_at,
                   c.kpi_targets, c.status, c.created_at
              FROM campaigns c JOIN brands b ON b.id = c.brand_id
             WHERE {' AND '.join(where)}
             ORDER BY c.created_at DESC""",
        *args,
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/campaigns")
async def create_campaign(
    body: CampaignIn,
    request: Request,
    actor: Principal = Depends(require_permission("project.create")),
):
    pool = await get_pool()
    cid = await pool.fetchval(
        """INSERT INTO campaigns (brand_id, name, description, theme, start_at, end_at,
               kpi_targets, created_by)
           VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8) RETURNING id""",
        body.brand_id, body.name, body.description, body.theme,
        body.start_at, body.end_at, json.dumps(body.kpi_targets), actor.user_id,
    )
    await audit(actor=actor, action="campaign.create", target_type="campaign",
                target_id=str(cid), after={"name": body.name}, request=request)
    return {"status": "ok", "id": cid}


@router.put("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: int,
    body: CampaignPatch,
    request: Request,
    actor: Principal = Depends(require_permission("project.edit")),
):
    pool = await get_pool()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return {"status": "noop"}
    sets, vals = [], []
    for k, v in updates.items():
        sets.append(f"{k}=${len(vals)+1}" + ("::jsonb" if k == "kpi_targets" else ""))
        vals.append(json.dumps(v) if k == "kpi_targets" else v)
    vals.append(campaign_id)
    res = await pool.execute(
        f"UPDATE campaigns SET {', '.join(sets)}, updated_at=NOW() WHERE id=${len(vals)}",
        *vals,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Campaign not found")
    await audit(actor=actor, action="campaign.update", target_type="campaign",
                target_id=str(campaign_id), after=updates, request=request)
    return {"status": "ok"}


# Projects

@router.get("/projects")
async def list_projects(
    channel_id: str | None = Query(None),
    status: str | None = Query(None),
    series_id: int | None = Query(None),
    campaign_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    p: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    args = [p.workspace_id]
    where = ["c.workspace_id = $1"]
    if channel_id:
        args.append(channel_id)
        where.append(f"p.channel_id = ${len(args)}")
    if status:
        args.append(status)
        where.append(f"p.status = ${len(args)}")
    if series_id:
        args.append(series_id)
        where.append(f"p.series_id = ${len(args)}")
    if campaign_id:
        args.append(campaign_id)
        where.append(f"p.campaign_id = ${len(args)}")
    args.append(limit)
    rows = await pool.fetch(
        f"""SELECT p.id, p.channel_id, p.series_id, p.campaign_id, p.parent_project_id,
                   p.branch_label, p.title, p.brief, p.status, p.priority,
                   p.target_publish_at, p.tags, p.estimated_cost_usd, p.actual_cost_usd,
                   p.settings, p.created_at, p.updated_at,
                   ch.channel_name,
                   (SELECT COUNT(*) FROM videos v WHERE v.project_id = p.id) AS video_count
              FROM projects p
              JOIN channels ch ON ch.channel_id = p.channel_id
              JOIN channels c  ON c.channel_id  = p.channel_id
             WHERE {' AND '.join(where)}
             ORDER BY p.priority DESC, p.created_at DESC
             LIMIT ${len(args)}""",
        *args,
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/projects")
async def create_project(
    body: ProjectIn,
    request: Request,
    actor: Principal = Depends(require_permission("project.create")),
):
    pool = await get_pool()
    pid = await pool.fetchval(
        """INSERT INTO projects (channel_id, title, brief, series_id, campaign_id,
               parent_project_id, branch_label, status, priority, target_publish_at,
               tags, settings, created_by)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13) RETURNING id""",
        body.channel_id, body.title, body.brief, body.series_id, body.campaign_id,
        body.parent_project_id, body.branch_label, body.status, body.priority,
        body.target_publish_at, body.tags, json.dumps(body.settings), actor.user_id,
    )
    await audit(actor=actor, action="project.create", target_type="project",
                target_id=str(pid), after={"title": body.title}, request=request)
    return {"status": "ok", "id": pid}


@router.get("/projects/{project_id}")
async def get_project(project_id: int, _: Principal = Depends(principal_dep)):
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT p.id, p.channel_id, p.series_id, p.campaign_id, p.parent_project_id,
                  p.branch_label, p.title, p.brief, p.status, p.priority,
                  p.target_publish_at, p.tags, p.estimated_cost_usd, p.actual_cost_usd,
                  p.settings, p.created_at, p.updated_at, ch.channel_name
             FROM projects p
             JOIN channels ch ON ch.channel_id = p.channel_id
            WHERE p.id = $1""",
        project_id,
    )
    if not row:
        raise HTTPException(404, "Project not found")
    # Fetch child branches
    branches = await pool.fetch(
        "SELECT id, branch_label, status, title FROM projects WHERE parent_project_id = $1",
        project_id,
    )
    # Fetch linked videos
    videos = await pool.fetch(
        "SELECT content_id, title, status, created_at FROM videos WHERE project_id = $1 ORDER BY created_at DESC LIMIT 20",
        project_id,
    )
    return {
        "data": {
            **dict(row),
            "branches": [dict(b) for b in branches],
            "videos": [dict(v) for v in videos],
        }
    }


@router.put("/projects/{project_id}")
async def update_project(
    project_id: int,
    body: ProjectPatch,
    request: Request,
    actor: Principal = Depends(require_permission("project.edit")),
):
    pool = await get_pool()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return {"status": "noop"}
    sets, vals = [], []
    for k, v in updates.items():
        if k == "tags":
            sets.append(f"{k}=${len(vals)+1}")
            vals.append(v)
        elif k == "settings":
            sets.append(f"{k}=${len(vals)+1}::jsonb")
            vals.append(json.dumps(v))
        else:
            sets.append(f"{k}=${len(vals)+1}")
            vals.append(v)
    vals.append(project_id)
    res = await pool.execute(
        f"UPDATE projects SET {', '.join(sets)}, updated_at=NOW() WHERE id=${len(vals)}",
        *vals,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Project not found")
    await audit(actor=actor, action="project.update", target_type="project",
                target_id=str(project_id), after=updates, request=request)
    return {"status": "ok"}


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    request: Request,
    actor: Principal = Depends(require_permission("project.delete")),
):
    pool = await get_pool()
    res = await pool.execute("DELETE FROM projects WHERE id=$1", project_id)
    if res.endswith("0"):
        raise HTTPException(404, "Project not found")
    await audit(actor=actor, action="project.delete", target_type="project",
                target_id=str(project_id), request=request)
    return {"status": "ok"}


# Members

@router.get("/members")
async def list_members(p: Principal = Depends(principal_dep)):
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT wm.user_id, wm.role, wm.joined_at,
                  u.email, u.display_name, u.last_login_at
             FROM workspace_members wm
             JOIN users u ON u.id = wm.user_id
            WHERE wm.workspace_id = $1
            ORDER BY wm.role, u.email""",
        p.workspace_id,
    )
    return {"data": [dict(r) for r in rows]}


@router.put("/members/{user_id}/role")
async def set_member_role(
    user_id: int,
    body: MemberRolePatch,
    request: Request,
    actor: Principal = Depends(require_permission("workspace.members.role.change")),
):
    pool = await get_pool()
    VALID_ROLES = {"owner", "member", "viewer"}
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}")
    if body.role == "owner" and actor.role != "owner":
        raise HTTPException(403, "Only an owner can assign the owner role")
    # Prevent demoting the last owner
    if body.role != "owner":
        current = await pool.fetchval(
            "SELECT role FROM workspace_members WHERE workspace_id=$1 AND user_id=$2",
            actor.workspace_id, user_id,
        )
        if current == "owner":
            owner_count = await pool.fetchval(
                "SELECT COUNT(*) FROM workspace_members WHERE workspace_id=$1 AND role='owner'",
                actor.workspace_id,
            )
            if (owner_count or 0) <= 1:
                raise HTTPException(400, "Cannot demote the last owner of a workspace")
    res = await pool.execute(
        "UPDATE workspace_members SET role=$1 WHERE workspace_id=$2 AND user_id=$3",
        body.role, actor.workspace_id, user_id,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Member not found")
    await audit(actor=actor, action="member.role_change", target_type="workspace_member",
                target_id=str(user_id), after={"role": body.role}, request=request)
    return {"status": "ok"}


@router.delete("/members/{user_id}")
async def remove_member(
    user_id: int,
    request: Request,
    actor: Principal = Depends(require_permission("workspace.members.remove")),
):
    pool = await get_pool()
    target_role = await pool.fetchval(
        "SELECT role FROM workspace_members WHERE workspace_id=$1 AND user_id=$2",
        actor.workspace_id, user_id,
    )
    if target_role == "owner":
        owner_count = await pool.fetchval(
            "SELECT COUNT(*) FROM workspace_members WHERE workspace_id=$1 AND role='owner'",
            actor.workspace_id,
        )
        if (owner_count or 0) <= 1:
            raise HTTPException(
                400,
                "Cannot remove the last owner of a workspace. "
                "Transfer ownership to another member first.",
            )
    removed_user = await pool.fetchrow(
        "SELECT email, display_name FROM users WHERE id=$1", user_id
    )
    ws_info = await pool.fetchrow(
        "SELECT name FROM workspaces WHERE id=$1", actor.workspace_id
    )
    res = await pool.execute(
        "DELETE FROM workspace_members WHERE workspace_id=$1 AND user_id=$2",
        actor.workspace_id, user_id,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Member not found")
    await audit(actor=actor, action="member.remove", target_type="workspace_member",
                target_id=str(user_id), request=request)
    # Invalidate membership cache immediately via Redis pub/sub
    from ._membership import publish_revoked
    await publish_revoked(user_id, actor.workspace_id)
    # member-removed email (fire-and-forget)
    if removed_user and removed_user["email"]:
        from ._resend import send_email as _resend_send
        _resend_send("member-removed", removed_user["email"], {
            "name": removed_user["display_name"] or removed_user["email"],
            "workspace_name": ws_info["name"] if ws_info else "your workspace",
        })
    return {"status": "ok"}


# Invitations

VALID_INVITE_ROLES = {"member", "viewer"}


class InviteIn(BaseModel):
    email: EmailStr
    role: str = "viewer"
    expires_days: int = Field(7, ge=1, le=30)


@router.get("/invites")
async def list_invites(p: Principal = Depends(principal_dep)):
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT id, email, role, accepted_at, expires_at, created_at, resent_at
             FROM workspace_invitations
            WHERE workspace_id = $1
            ORDER BY created_at DESC""",
        p.workspace_id,
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/invites")
async def create_invite(
    body: InviteIn,
    request: Request,
    actor: Principal = Depends(require_permission("workspace.members.invite")),
):
    if body.role not in VALID_INVITE_ROLES:
        raise HTTPException(400, f"Invalid role. Choose from: {', '.join(sorted(VALID_INVITE_ROLES))}")
    pool = await get_pool()
    # Read plan outside the lock — idempotent, no mutation.
    ws_row = await pool.fetchrow(
        "SELECT plan FROM workspaces WHERE id=$1", actor.workspace_id
    )
    plan = (ws_row["plan"] if ws_row else "starter") or "starter"
    limit = _PLAN_MEMBER_LIMITS.get(plan)  # None = unlimited

    # AE-277 race-condition hotfix: take an advisory transaction lock keyed on
    # workspace_id so that concurrent invite requests for the same workspace are
    # serialized.  This prevents multiple requests from both seeing
    # (current + pending) < limit and inserting more rows than the plan allows.
    # pg_advisory_xact_lock is released automatically when the transaction ends.
    raw = secrets.token_urlsafe(32)
    h = hashlib.sha256(raw.encode()).hexdigest()
    expires = datetime.utcnow() + timedelta(days=body.expires_days)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", actor.workspace_id)
            # Plan limit check (inside lock — counts are now authoritative)
            if limit is not None:
                member_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM workspace_members WHERE workspace_id=$1",
                    actor.workspace_id,
                ) or 0
                pending_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM workspace_invitations "
                    "WHERE workspace_id=$1 AND accepted_at IS NULL AND expires_at > NOW()",
                    actor.workspace_id,
                ) or 0
                if (member_count + pending_count) >= limit:
                    raise HTTPException(
                        402,
                        f"Plan limit reached: {plan!r} plan allows {limit} members "
                        f"({member_count} current + {pending_count} pending invites). "
                        "Upgrade your plan to invite more members.",
                    )
            # Check member doesn't already exist
            existing = await conn.fetchval(
                """SELECT wm.user_id FROM workspace_members wm
                     JOIN users u ON u.id = wm.user_id
                    WHERE wm.workspace_id=$1 AND lower(u.email)=lower($2)""",
                actor.workspace_id, body.email,
            )
            if existing:
                raise HTTPException(409, "User is already a member of this workspace")
            # Check no pending invite already exists for this email
            pending_inv = await conn.fetchval(
                """SELECT id FROM workspace_invitations
                    WHERE workspace_id=$1 AND lower(email)=lower($2)
                      AND accepted_at IS NULL AND expires_at > NOW()""",
                actor.workspace_id, body.email,
            )
            if pending_inv:
                raise HTTPException(409, "A pending invitation already exists for this email address. Revoke it first or wait for it to expire.")
            inv_id = await conn.fetchval(
                """INSERT INTO workspace_invitations
                       (workspace_id, email, role, token_hash, invited_by, expires_at)
                   VALUES ($1,$2,$3,$4,$5,$6) RETURNING id""",
                actor.workspace_id, body.email.lower(), body.role, h, actor.user_id, expires,
            )
    await audit(actor=actor, action="invite.create", target_type="workspace_invitation",
                target_id=str(inv_id), after={"email": body.email, "role": body.role}, request=request)
    frontend_url = os.getenv("FRONTEND_URL", "")
    invite_link = f"{frontend_url}/accept-invite?token={raw}" if frontend_url else f"/accept-invite?token={raw}"
    # Resend invite email (fire-and-forget). Skip the extra lookups when
    # Resend isn't configured to save DB roundtrips and keep tests deterministic.
    from ._resend import send_email as _resend_send, is_configured as _resend_configured
    if _resend_configured():
        ws_info = await pool.fetchrow("SELECT name FROM workspaces WHERE id=$1", actor.workspace_id)
        actor_info = await pool.fetchrow("SELECT display_name FROM users WHERE id=$1", actor.user_id)
        inviter_name = (actor_info["display_name"] if actor_info and actor_info["display_name"] else actor.email) or ""
        _resend_send("workspace-invite", body.email, {
            "inviter_name": inviter_name,
            "inviter_email": actor.email or "",
            "workspace_name": ws_info["name"] if ws_info else "a workspace",
            "role": body.role,
            "invite_url": invite_link,
            "expires_days": body.expires_days,
        })
    # Slack DM notification (best-effort)
    integration = await pool.fetchrow(
        "SELECT slack_webhook_url FROM workspace_integrations WHERE workspace_id=$1",
        actor.workspace_id,
    )
    if integration and integration["slack_webhook_url"]:
        await _notify_slack(
            integration["slack_webhook_url"],
            f":envelope: *Workspace invitation sent*\n"
            f"• *To:* {body.email}\n"
            f"• *Role:* {body.role}\n"
            f"• *Link:* {invite_link}",
        )
    return {"status": "ok", "id": inv_id, "token": raw,
            "invite_url": f"/accept-invite?token={raw}"}


@router.delete("/invites/{invite_id}")
async def revoke_invite(
    invite_id: int,
    request: Request,
    actor: Principal = Depends(require_permission("workspace.members.invite")),
):
    pool = await get_pool()
    res = await pool.execute(
        "DELETE FROM workspace_invitations WHERE id=$1 AND workspace_id=$2 AND accepted_at IS NULL",
        invite_id, actor.workspace_id,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Invitation not found or already accepted")
    await audit(actor=actor, action="invite.revoke", target_type="workspace_invitation",
                target_id=str(invite_id), request=request)
    return {"status": "ok"}


# Workspace integrations (Slack webhook, etc.)

class IntegrationPatch(BaseModel):
    slack_webhook_url: str | None = None


@router.get("/integrations")
async def get_integrations(actor: Principal = Depends(require_permission("workspace.integrations.view"))):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT slack_webhook_url FROM workspace_integrations WHERE workspace_id=$1",
        actor.workspace_id,
    )
    return {"data": {
        "slack_webhook_url": row["slack_webhook_url"] if row else None,
    }}


@router.put("/integrations")
async def update_integrations(
    body: IntegrationPatch,
    request: Request,
    actor: Principal = Depends(require_permission("workspace.integrations.manage")),
):
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO workspace_integrations (workspace_id, slack_webhook_url)
           VALUES ($1, $2)
           ON CONFLICT (workspace_id) DO UPDATE
           SET slack_webhook_url=$2, updated_at=NOW()""",
        actor.workspace_id, body.slack_webhook_url,
    )
    masked = (body.slack_webhook_url[:30] + "...") if body.slack_webhook_url else None
    await audit(actor=actor, action="workspace.integrations.update",
                target_type="workspace_integrations",
                target_id=str(actor.workspace_id),
                after={"slack_webhook_url": masked}, request=request)
    return {"status": "ok"}


# Entity settings

# Tenant-isolation hotfix (AE-276): every entity_settings access must verify
# that the (scope, scope_id) pair belongs to the caller's workspace.  The
# previous implementation accepted any scope_id and exposed both READ and
# WRITE to other workspaces' settings — a tenant-isolation breach.

_SETTINGS_TENANT_SCOPES: frozenset[str] = frozenset(
    {"workspace", "brand", "channel", "series", "campaign", "project"}
)
_SETTINGS_VALID_SCOPES: frozenset[str] = _SETTINGS_TENANT_SCOPES | {"system"}


async def _assert_settings_scope_in_workspace(
    pool: Any, scope: str, scope_id: str, workspace_id: int
) -> None:
    """Raise 403 unless ``(scope, scope_id)`` belongs to ``workspace_id``.

    For ``scope='system'`` no per-tenant check applies — system settings are
    cross-workspace by design (caller permission is the only gate).

    Returns silently on success; raises ``HTTPException`` on:
      * 400 — scope unrecognised, or scope_id has wrong type for the scope
      * 403 — entity belongs to a different workspace
      * 404 — entity does not exist
    """
    if scope == "system":
        return
    if scope not in _SETTINGS_TENANT_SCOPES:
        raise HTTPException(
            400,
            f"Invalid scope. Must be one of: {', '.join(sorted(_SETTINGS_VALID_SCOPES))}",
        )

    # Workspace scope: scope_id is the workspace id itself.
    if scope == "workspace":
        try:
            target_ws = int(scope_id)
        except (TypeError, ValueError):
            raise HTTPException(400, "Invalid scope_id (expected integer workspace id)")
        if target_ws != workspace_id:
            raise HTTPException(403, "Cross-workspace access denied")
        return

    # Channel scope: channels.channel_id is a TEXT primary key (e.g. 'UC...'),
    # so we look it up directly.
    if scope == "channel":
        owner = await pool.fetchval(
            "SELECT workspace_id FROM channels WHERE channel_id=$1", scope_id
        )
        if owner is None:
            raise HTTPException(404, "channel not found")
        if owner != workspace_id:
            raise HTTPException(403, "Cross-workspace access denied")
        return

    # Other tenant scopes use BIGINT primary keys; resolve workspace_id via the
    # appropriate JOIN where the table doesn't carry workspace_id directly.
    try:
        sid = int(scope_id)
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid scope_id (expected integer)")

    if scope == "brand":
        sql = "SELECT workspace_id FROM brands WHERE id=$1"
    elif scope == "series":
        sql = (
            "SELECT c.workspace_id FROM series s "
            "JOIN channels c ON c.channel_id = s.channel_id "
            "WHERE s.id=$1"
        )
    elif scope == "campaign":
        sql = (
            "SELECT b.workspace_id FROM campaigns c "
            "JOIN brands b ON b.id = c.brand_id "
            "WHERE c.id=$1"
        )
    elif scope == "project":
        sql = (
            "SELECT ch.workspace_id FROM projects p "
            "JOIN channels ch ON ch.channel_id = p.channel_id "
            "WHERE p.id=$1"
        )
    else:  # pragma: no cover — guarded by the membership check above
        raise HTTPException(400, f"Invalid scope: {scope}")

    owner = await pool.fetchval(sql, sid)
    if owner is None:
        raise HTTPException(404, f"{scope} not found")
    if owner != workspace_id:
        raise HTTPException(403, "Cross-workspace access denied")


@router.get("/settings")
async def get_settings(
    scope: str = Query(...),
    scope_id: str = Query(...),
    p: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    await _assert_settings_scope_in_workspace(pool, scope, scope_id, p.workspace_id)
    rows = await pool.fetch(
        "SELECT key, value, locked FROM entity_settings WHERE scope=$1 AND scope_id=$2",
        scope, scope_id,
    )
    return {"data": [dict(r) for r in rows]}


@router.put("/settings")
async def upsert_setting(
    body: EntitySettingUpsert,
    request: Request,
    actor: Principal = Depends(require_permission("workspace.settings.edit")),
):
    pool = await get_pool()
    if body.scope not in _SETTINGS_VALID_SCOPES:
        raise HTTPException(
            400,
            f"Invalid scope. Must be one of: {', '.join(sorted(_SETTINGS_VALID_SCOPES))}",
        )
    await _assert_settings_scope_in_workspace(pool, body.scope, body.scope_id, actor.workspace_id)
    await pool.execute(
        """INSERT INTO entity_settings (scope, scope_id, key, value, locked)
           VALUES ($1,$2,$3,$4::jsonb,$5)
           ON CONFLICT (scope, scope_id, key) DO UPDATE
           SET value=$4::jsonb, locked=$5, updated_at=NOW()""",
        body.scope, body.scope_id, body.key, json.dumps(body.value), body.locked,
    )
    await audit(actor=actor, action="settings.upsert", target_type="entity_settings",
                target_id=f"{body.scope}/{body.scope_id}/{body.key}",
                after={"value": body.value, "locked": body.locked}, request=request)
    return {"status": "ok"}


# Ownership Transfer

class TransferOwnershipIn(BaseModel):
    new_owner_user_id: int
    current_password: str


@router.post("/transfer-ownership")
async def transfer_ownership(
    body: TransferOwnershipIn,
    request: Request,
    actor: Principal = Depends(require_permission("workspace.ownership.transfer")),
):
    if not actor.user_id:
        raise HTTPException(403, "No user context")
    if body.new_owner_user_id == actor.user_id:
        raise HTTPException(400, "Cannot transfer ownership to yourself")
    pool = await get_pool()
    # Verify current password
    current_user = await pool.fetchrow(
        "SELECT password_hash, display_name, email FROM users WHERE id=$1", actor.user_id
    )
    if not current_user:
        raise HTTPException(404, "Current user not found")
    from .auth import _verify_pw
    if not _verify_pw(body.current_password, current_user["password_hash"] or ""):
        raise HTTPException(401, "Password is incorrect")
    # Verify new owner is an existing member
    new_owner_member = await pool.fetchrow(
        """SELECT wm.role, u.display_name, u.email
             FROM workspace_members wm JOIN users u ON u.id = wm.user_id
            WHERE wm.workspace_id=$1 AND wm.user_id=$2""",
        actor.workspace_id, body.new_owner_user_id,
    )
    if not new_owner_member:
        raise HTTPException(404, "Target user is not a member of this workspace")
    ws_info = await pool.fetchrow("SELECT name FROM workspaces WHERE id=$1", actor.workspace_id)
    workspace_name = ws_info["name"] if ws_info else "your workspace"
    old_owner_name = current_user["display_name"] or current_user["email"] or ""
    new_owner_name = new_owner_member["display_name"] or new_owner_member["email"] or ""
    # Atomic role swap
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE workspace_members SET role='owner' WHERE workspace_id=$1 AND user_id=$2",
                actor.workspace_id, body.new_owner_user_id,
            )
            await conn.execute(
                "UPDATE workspace_members SET role='member' WHERE workspace_id=$1 AND user_id=$2",
                actor.workspace_id, actor.user_id,
            )
    await audit(
        actor=actor,
        action="ownership.transfer",
        target_type="workspace_member",
        target_id=str(body.new_owner_user_id),
        before={"owner_user_id": actor.user_id},
        after={"owner_user_id": body.new_owner_user_id},
        request=request,
    )
    # Emails — fire-and-forget
    from ._resend import send_email as _resend_send
    if new_owner_member["email"]:
        _resend_send("ownership-transferred-new", new_owner_member["email"], {
            "name": new_owner_name,
            "workspace_name": workspace_name,
        })
    if current_user["email"]:
        _resend_send("ownership-transferred-old", current_user["email"], {
            "name": old_owner_name,
            "workspace_name": workspace_name,
            "new_owner_name": new_owner_name,
        })
    return {"status": "ok"}
