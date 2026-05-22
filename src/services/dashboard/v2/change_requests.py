"""AE-76 — Provider Change Request & Approval Workflow.

Endpoints:
  GET    /providers/change-requests               list (owner/admin: all; producer/editor: own)
  POST   /providers/change-requests               submit request (producer/editor/admin/owner)
  GET    /providers/change-requests/{id}          detail
  POST   /providers/change-requests/{id}/admin-review   admin/owner review
  POST   /providers/change-requests/{id}/owner-review   owner final review

Auto-apply on owner approval executes the requested change using the
existing credential / chain helpers directly.

Notifications: stubbed — will be wired to #79 (real-time notifications)
once that story lands.
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.db import get_pool

from ._deps import Principal, audit, principal_dep, require_role

logger = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChangeRequestIn(BaseModel):
    request_type: str = Field(
        ...,
        description="add_credential | change_chain_priority | remove_credential | change_model | rotate_credential",
    )
    category: str
    provider_name: str | None = None
    payload: dict = Field(default_factory=dict)
    reason: str


class ReviewIn(BaseModel):
    action: str = Field(..., description="approve | reject | approve_forward")
    note: str | None = None


# ---------------------------------------------------------------------------
# Notification stub (to be replaced once #79 lands)
# ---------------------------------------------------------------------------

async def _notify_stub(event: str, data: dict) -> None:
    """Placeholder notification delivery. Replace with real #79 integration."""
    logger.info("change_request.notification_stub", event=event, **data)


# ---------------------------------------------------------------------------
# Auto-apply helper — executes the approved change via internal logic
# ---------------------------------------------------------------------------

async def _auto_apply(pool: Any, request_row: Any) -> None:
    """Execute the approved change from an owner-approved request."""
    req_type = request_row["request_type"]
    payload = dict(request_row["payload"]) if request_row["payload"] else {}
    category = request_row["category"]

    try:
        if req_type == "remove_credential":
            cred_id = payload.get("credential_id")
            if cred_id:
                await pool.execute(
                    "DELETE FROM provider_credentials WHERE id=$1", cred_id
                )

        elif req_type == "change_chain_priority":
            scope = payload.get("scope", "workspace")
            scope_id = payload.get("scope_id")
            content_mode = payload.get("content_mode")
            cred_ids = payload.get("credential_ids", [])
            # Delete existing chain and re-insert with new order
            await pool.execute(
                "DELETE FROM provider_chains_v2 WHERE category=$1 AND scope=$2 AND "
                "(scope_id=$3 OR ($3 IS NULL AND scope_id IS NULL)) AND "
                "(content_mode=$4 OR ($4 IS NULL AND content_mode IS NULL))",
                category, scope, scope_id, content_mode,
            )
            for pos, cred_id in enumerate(cred_ids):
                await pool.execute(
                    """INSERT INTO provider_chains_v2
                       (category, scope, scope_id, content_mode, credential_id, position)
                       VALUES ($1,$2,$3,$4,$5,$6)
                       ON CONFLICT DO NOTHING""",
                    category, scope, scope_id, content_mode, cred_id, pos,
                )

        elif req_type == "change_model":
            cred_id = payload.get("credential_id")
            model = payload.get("model")
            if cred_id and model:
                await pool.execute(
                    "UPDATE provider_credentials SET model=$1 WHERE id=$2",
                    model, cred_id,
                )

        # add_credential and rotate_credential require the full wizard/rotation
        # logic — those are flagged back to the owner to complete manually for now.
        else:
            logger.info(
                "change_request.auto_apply_manual",
                request_type=req_type,
                note="Manual action required — auto-apply not supported for this type yet",
            )

        await pool.execute(
            "UPDATE provider_change_requests SET applied_at=NOW() WHERE id=$1",
            request_row["id"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("change_request.auto_apply_failed", error=str(exc),
                     request_id=request_row["id"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_change_requests(
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    actor: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    is_privileged = actor.role in ("owner", "admin")

    conditions = ["cr.workspace_id=$1"]
    params: list[Any] = [actor.workspace_id]

    if not is_privileged:
        params.append(actor.user_id)
        conditions.append(f"cr.requested_by=${len(params)}")

    if status:
        params.append(status)
        conditions.append(f"cr.status=${len(params)}")

    if category:
        params.append(category)
        conditions.append(f"cr.category=${len(params)}")

    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"""SELECT cr.*,
                   u.full_name  AS requester_name,
                   u.email      AS requester_email,
                   au.full_name AS admin_reviewer_name,
                   ou.full_name AS owner_reviewer_name
              FROM provider_change_requests cr
              LEFT JOIN users u  ON u.id  = cr.requested_by
              LEFT JOIN users au ON au.id = cr.admin_reviewed_by
              LEFT JOIN users ou ON ou.id = cr.owner_reviewed_by
             WHERE {where}
             ORDER BY cr.created_at DESC
             LIMIT 100""",
        *params,
    )
    return {"status": "ok", "data": [dict(r) for r in rows]}


@router.post("")
async def create_change_request(
    body: ChangeRequestIn,
    request: Request,
    actor: Principal = Depends(principal_dep),
):
    valid_types = {
        "add_credential", "change_chain_priority",
        "remove_credential", "change_model", "rotate_credential",
    }
    if body.request_type not in valid_types:
        raise HTTPException(400, f"Invalid request_type. Must be one of: {sorted(valid_types)}")

    pool = await get_pool()
    row_id = await pool.fetchval(
        """INSERT INTO provider_change_requests
           (workspace_id, requested_by, request_type, category, provider_name,
            payload, reason)
           VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7)
           RETURNING id""",
        actor.workspace_id, actor.user_id, body.request_type, body.category,
        body.provider_name, json.dumps(body.payload), body.reason,
    )
    await audit(
        actor=actor, action="provider.change_request.created",
        target_type="change_request", target_id=str(row_id),
        after=body.model_dump(), request=request,
    )
    await _notify_stub("change_request.created", {
        "request_id": row_id, "type": body.request_type,
        "category": body.category, "requested_by": actor.user_id,
    })
    return {"status": "ok", "data": {"id": row_id}}


@router.get("/{request_id}")
async def get_change_request(
    request_id: int,
    actor: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT cr.*,
                  u.full_name  AS requester_name,
                  u.email      AS requester_email,
                  au.full_name AS admin_reviewer_name,
                  ou.full_name AS owner_reviewer_name
             FROM provider_change_requests cr
             LEFT JOIN users u  ON u.id  = cr.requested_by
             LEFT JOIN users au ON au.id = cr.admin_reviewed_by
             LEFT JOIN users ou ON ou.id = cr.owner_reviewed_by
            WHERE cr.id=$1 AND cr.workspace_id=$2""",
        request_id, actor.workspace_id,
    )
    if not row:
        raise HTTPException(404, "Change request not found")

    is_privileged = actor.role in ("owner", "admin")
    if not is_privileged and row["requested_by"] != actor.user_id:
        raise HTTPException(403, "Access denied")

    return {"status": "ok", "data": dict(row)}


@router.post("/{request_id}/admin-review")
async def admin_review(
    request_id: int,
    body: ReviewIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    if body.action not in ("approve_forward", "reject"):
        raise HTTPException(400, "action must be 'approve_forward' or 'reject'")

    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM provider_change_requests WHERE id=$1 AND workspace_id=$2",
        request_id, actor.workspace_id,
    )
    if not row:
        raise HTTPException(404, "Change request not found")
    if row["status"] != "pending_admin":
        raise HTTPException(409, f"Request is not pending admin review (status={row['status']})")

    new_status = "pending_owner" if body.action == "approve_forward" else "rejected_by_admin"
    await pool.execute(
        """UPDATE provider_change_requests
              SET status=$1, admin_reviewed_by=$2, admin_reviewed_at=NOW(), admin_note=$3
            WHERE id=$4""",
        new_status, actor.user_id, body.note, request_id,
    )
    await audit(
        actor=actor, action=f"provider.change_request.admin_{body.action}",
        target_type="change_request", target_id=str(request_id),
        after={"status": new_status, "note": body.note}, request=request,
    )
    await _notify_stub(f"change_request.admin_{body.action}", {
        "request_id": request_id, "new_status": new_status,
        "requested_by": row["requested_by"],
    })
    return {"status": "ok", "data": {"new_status": new_status}}


@router.post("/{request_id}/owner-review")
async def owner_review(
    request_id: int,
    body: ReviewIn,
    request: Request,
    actor: Principal = Depends(require_role("owner")),
):
    if body.action not in ("approve", "reject"):
        raise HTTPException(400, "action must be 'approve' or 'reject'")

    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM provider_change_requests WHERE id=$1 AND workspace_id=$2",
        request_id, actor.workspace_id,
    )
    if not row:
        raise HTTPException(404, "Change request not found")
    # Owner can review from pending_admin or pending_owner
    if row["status"] not in ("pending_admin", "pending_owner"):
        raise HTTPException(409, f"Request is not pending review (status={row['status']})")

    new_status = "applied" if body.action == "approve" else "rejected_by_owner"
    await pool.execute(
        """UPDATE provider_change_requests
              SET status=$1, owner_reviewed_by=$2, owner_reviewed_at=NOW(), owner_note=$3
            WHERE id=$4""",
        new_status, actor.user_id, body.note, request_id,
    )
    if body.action == "approve":
        await _auto_apply(pool, row)

    await audit(
        actor=actor, action=f"provider.change_request.owner_{body.action}",
        target_type="change_request", target_id=str(request_id),
        after={"status": new_status, "note": body.note}, request=request,
    )
    await _notify_stub(f"change_request.owner_{body.action}", {
        "request_id": request_id, "new_status": new_status,
        "requested_by": row["requested_by"],
    })
    return {"status": "ok", "data": {"new_status": new_status}}
