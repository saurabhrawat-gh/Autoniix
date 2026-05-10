"""Generated Content browser — Phase 3 (S2).

Endpoints:
  GET  /content                      Time-grouped list with filters + cursor
  GET  /content/search               FTS + (optional) pgvector
  POST /content/bulk                 Bulk action: archive/retry/approve/reject/regenerate
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.db import get_pool

from ._deps import Principal, audit, principal_dep, require_role

router = APIRouter()

_GROUP_TRUNC = {
    "day":     "day",
    "week":    "week",
    "month":   "month",
    "quarter": "quarter",
    "year":    "year",
}


class BulkActionIn(BaseModel):
    action: str  # archive|retry|approve|reject|regenerate|delete
    ids: list[str]
    note: str | None = None


@router.get("")
async def list_content(
    channel_id: str | None = Query(None),
    group: str = Query("week"),
    status: str | None = Query(None),
    review_state: str | None = Query(None),
    content_mode: str | None = Query(None),
    cursor: str | None = Query(None, description="ISO datetime to paginate before"),
    limit: int = Query(50, ge=1, le=500),
    _: Principal = Depends(principal_dep),
):
    if group not in _GROUP_TRUNC:
        raise HTTPException(400, f"group must be one of {list(_GROUP_TRUNC)}")

    where: list[str] = ["1=1"]
    args: list[Any] = []
    if channel_id:
        args.append(channel_id); where.append(f"channel_id=${len(args)}")
    if status:
        args.append(status); where.append(f"status=${len(args)}")
    if review_state:
        args.append(review_state); where.append(f"review_state=${len(args)}")
    if content_mode:
        args.append(content_mode); where.append(f"content_mode=${len(args)}")
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except Exception:
            raise HTTPException(400, "cursor must be ISO datetime")
        args.append(cursor_dt); where.append(f"created_at < ${len(args)}")

    args.append(limit + 1)
    sql = f"""
        SELECT content_id, channel_id, status, content_mode, title,
               topic, selected_hook, review_state, authenticity_score,
               uniqueness_score, thumbnail_variants_urls, rendered_video_url,
               youtube_video_id, total_cost, final_composite_score,
               created_at, scheduled_at, published_at,
               date_trunc('{_GROUP_TRUNC[group]}', created_at)::date AS bucket
          FROM videos
         WHERE {' AND '.join(where)}
         ORDER BY created_at DESC
         LIMIT ${len(args)}
    """
    pool = await get_pool()
    rows = await pool.fetch(sql, *args)

    has_more = len(rows) > limit
    rows = rows[:limit]

    # Group in Python — keep DB simple
    from collections import OrderedDict
    grouped: "OrderedDict[str, list[dict]]" = OrderedDict()
    for r in rows:
        b = r["bucket"].isoformat()
        grouped.setdefault(b, []).append({
            **{k: v for k, v in dict(r).items() if k != "bucket"}
        })

    next_cursor = rows[-1]["created_at"].isoformat() if has_more and rows else None
    return {
        "data": {
            "groups": [{"label": k, "items": v} for k, v in grouped.items()],
            "group_kind": group,
            "next_cursor": next_cursor,
            "count": len(rows),
        }
    }


@router.get("/search")
async def search_content(
    q: str = Query(..., min_length=2),
    channel_id: str | None = None,
    limit: int = Query(40, ge=1, le=200),
    _: Principal = Depends(principal_dep),
):
    where = ["title_tsv @@ plainto_tsquery('english', $1)"]
    args: list[Any] = [q]
    if channel_id:
        args.append(channel_id); where.append(f"channel_id=${len(args)}")
    args.append(limit)
    sql = f"""
        SELECT content_id, channel_id, title, topic, selected_hook, status,
               review_state, created_at,
               ts_rank(title_tsv, plainto_tsquery('english', $1)) AS rank
          FROM videos
         WHERE {' AND '.join(where)}
         ORDER BY rank DESC, created_at DESC
         LIMIT ${len(args)}
    """
    pool = await get_pool()
    rows = await pool.fetch(sql, *args)
    return {"data": [dict(r) for r in rows]}


@router.get("/calendar")
async def calendar(
    channel_id: str | None = Query(None),
    start: str = Query(..., description="ISO date YYYY-MM-DD"),
    end:   str = Query(..., description="ISO date YYYY-MM-DD (exclusive)"),
    _: Principal = Depends(principal_dep),
):
    """Return videos keyed by ISO date for the given range.

    Includes all videos whose ``scheduled_at``, ``published_at`` or
    ``created_at`` lands within [start, end). Useful for calendar views.
    """
    pool = await get_pool()
    args: list[Any] = [start, end]
    where_chan = ""
    if channel_id:
        args.append(channel_id)
        where_chan = " AND channel_id = $3"
    rows = await pool.fetch(
        f"""
        SELECT content_id, channel_id, content_mode, status, review_state,
               title, topic, authenticity_score,
               COALESCE(published_at, scheduled_at, created_at)::date AS day,
               published_at, scheduled_at, created_at
          FROM videos
         WHERE COALESCE(published_at, scheduled_at, created_at) >= $1::date
           AND COALESCE(published_at, scheduled_at, created_at) <  $2::date
           {where_chan}
         ORDER BY day ASC, created_at ASC
        """,
        *args,
    )
    out: dict[str, list[dict]] = {}
    for r in rows:
        d = r["day"].isoformat() if r["day"] else "unknown"
        out.setdefault(d, []).append({
            "content_id": r["content_id"], "channel_id": r["channel_id"],
            "content_mode": r["content_mode"], "status": r["status"],
            "review_state": r["review_state"],
            "title": r["title"] or r["topic"],
            "authenticity_score": float(r["authenticity_score"] or 0) if r["authenticity_score"] is not None else None,
            "published_at": r["published_at"].isoformat() if r["published_at"] else None,
            "scheduled_at": r["scheduled_at"].isoformat() if r["scheduled_at"] else None,
        })
    return {"data": out, "start": start, "end": end}


@router.post("/bulk")
async def bulk_action(
    body: BulkActionIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin", "editor")),
):
    if not body.ids:
        return {"status": "noop"}
    pool = await get_pool()
    affected = 0
    if body.action == "archive":
        affected = int((await pool.execute(
            "UPDATE videos SET status='archived', updated_at=NOW() "
            "WHERE content_id = ANY($1::text[]) AND status NOT IN ('archived','published')",
            body.ids,
        )).split()[-1])
    elif body.action == "approve":
        affected = int((await pool.execute(
            "UPDATE videos SET review_state='approved', updated_at=NOW() "
            "WHERE content_id = ANY($1::text[])",
            body.ids,
        )).split()[-1])
    elif body.action == "reject":
        affected = int((await pool.execute(
            "UPDATE videos SET review_state='rejected', updated_at=NOW() "
            "WHERE content_id = ANY($1::text[])",
            body.ids,
        )).split()[-1])
    elif body.action == "retry":
        affected = int((await pool.execute(
            "UPDATE videos SET status='pending', error_message=NULL, updated_at=NOW() "
            "WHERE content_id = ANY($1::text[]) AND status IN ('failed','stopped')",
            body.ids,
        )).split()[-1])
    elif body.action == "regenerate":
        affected = int((await pool.execute(
            "UPDATE videos SET review_state='regenerating', status='pending', updated_at=NOW() "
            "WHERE content_id = ANY($1::text[])",
            body.ids,
        )).split()[-1])
    elif body.action == "delete":
        affected = int((await pool.execute(
            "UPDATE videos SET status='archived', updated_at=NOW() "
            "WHERE content_id = ANY($1::text[])",
            body.ids,
        )).split()[-1])
    else:
        raise HTTPException(400, f"Unknown action {body.action!r}")

    await audit(actor=actor, action=f"content.bulk.{body.action}",
                target_type="video", target_id=f"{len(body.ids)} items",
                after={"ids": body.ids, "affected": affected, "note": body.note},
                request=request)
    return {"status": "ok", "affected": affected}
