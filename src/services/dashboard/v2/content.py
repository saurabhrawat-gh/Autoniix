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
    action: str
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
               current_phase, created_at, scheduled_at, published_at,
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
    actor: Principal = Depends(require_role("owner", "member")),
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




@router.get("/triggers/history")
async def list_triggers(
    channel_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    if not await _table_exists(pool, "content_triggers"):
        return {"data": []}
    where = ["1=1"]
    args: list[Any] = []
    if channel_id:
        args.append(channel_id); where.append(f"channel_id=${len(args)}")
    args.append(limit)
    rows = await pool.fetch(
        f"""
        SELECT * FROM content_triggers
         WHERE {' AND '.join(where)}
         ORDER BY created_at DESC
         LIMIT ${len(args)}
        """,
        *args,
    )
    return {"data": [dict(r) for r in rows]}


@router.get("/stats")
async def content_stats(
    channel_id: str | None = Query(None),
    period: str = Query("week", description="day|week|month"),
    _: Principal = Depends(principal_dep),
):
    """Per-status + per-channel aggregates for the pipeline stat strip."""
    pool = await get_pool()
    where = ["1=1"]
    args: list[Any] = []
    if channel_id:
        args.append(channel_id); where.append(f"channel_id=${len(args)}")
    trunc = _GROUP_TRUNC.get(period, "week")
    args.append(30 if period == "day" else 12 if period == "week" else 12)
    rows = await pool.fetch(
        f"""
        SELECT
            status,
            content_mode,
            COUNT(*)                                       AS cnt,
            AVG(total_cost)                                AS avg_cost,
            AVG(final_composite_score)                     AS avg_score,
            date_trunc('{trunc}', created_at)::date        AS bucket
        FROM videos
        WHERE {' AND '.join(where)}
          AND created_at >= NOW() - (${len(args)} || ' {trunc}s')::INTERVAL
        GROUP BY status, content_mode, bucket
        ORDER BY bucket DESC
        """,
        *args,
    )
    chan_rows = await pool.fetch(
        f"""
        SELECT channel_id,
               COUNT(*) FILTER (WHERE status IN ('completed','published','delivered')) AS done,
               COUNT(*) FILTER (WHERE status = 'running')  AS running,
               COUNT(*) FILTER (WHERE status = 'failed')   AS failed,
               SUM(total_cost)                              AS total_cost
        FROM videos
        WHERE {' AND '.join(where)}
        GROUP BY channel_id
        """,
        *args[:-1],
    )
    return {
        "data": {
            "buckets": [dict(r) for r in rows],
            "by_channel": [dict(r) for r in chan_rows],
        }
    }


@router.get("/{content_id}")
async def get_content_detail(
    content_id: str,
    _: Principal = Depends(principal_dep),
):
    """Full metadata for a single content item including events timeline."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT content_id, channel_id, status, content_mode, title, topic,
               selected_hook, review_state, authenticity_score, uniqueness_score,
               thumbnail_variants_urls, rendered_video_url, youtube_video_id,
               total_cost, final_composite_score, error_message, checkpoint,
               created_at, scheduled_at, published_at, updated_at,
               environment
          FROM videos WHERE content_id = $1
        """,
        content_id,
    )
    if not row:
        raise HTTPException(404, "Content not found")

    events = await pool.fetch(
        """
        SELECT phase, status, started_at, completed_at, duration_ms, error_message
          FROM job_events
         WHERE content_id = $1
         ORDER BY started_at ASC
        """,
        content_id,
    )

    review = await pool.fetchrow(
        """
        SELECT rs.id, rs.state, rs.created_at, rs.due_at,
               COUNT(fc.id) AS comment_count,
               COUNT(ra.id) AS approval_count
          FROM review_sessions rs
          LEFT JOIN frame_comments fc ON fc.session_id = rs.id
          LEFT JOIN review_approvals ra ON ra.session_id = rs.id
         WHERE rs.content_id = $1
         GROUP BY rs.id
         ORDER BY rs.created_at DESC
         LIMIT 1
        """,
        content_id,
    ) if await _table_exists(pool, "review_sessions") else None

    result = dict(row)
    result["events"] = [dict(e) for e in events]
    result["review_session"] = dict(review) if review else None
    return {"data": result}


class TriggerIn(BaseModel):
    channel_id: str
    content_mode: str = Field("long_form", pattern="^(short|long_form)$")
    topic_hint: str | None = None
    scheduled_for: str | None = None


@router.post("/trigger")
async def trigger_content(
    body: TriggerIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    """Queue a content generation job for a channel."""
    pool = await get_pool()

    trigger_id: int | None = None
    if await _table_exists(pool, "content_triggers"):
        trigger_id = await pool.fetchval(
            """
            INSERT INTO content_triggers
                (channel_id, content_mode, topic_hint, scheduled_for, triggered_by, status)
            VALUES ($1, $2, $3, $4::timestamptz, $5, 'queued')
            RETURNING id
            """,
            body.channel_id,
            body.content_mode,
            body.topic_hint,
            body.scheduled_for,
            actor.user_id,
        )

    import httpx
    bff_base = "http://localhost:8020"
    try:
        token = request.headers.get("Authorization", "")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{bff_base}/api/channels/{body.channel_id}/trigger",
                headers={"Authorization": token},
                json={"content_mode": body.content_mode, "topic_hint": body.topic_hint},
            )
        triggered = resp.status_code < 400
        content_id = resp.json().get("content_id") if triggered else None
    except Exception:
        triggered = False
        content_id = None

    if trigger_id and await _table_exists(pool, "content_triggers"):
        await pool.execute(
            """
            UPDATE content_triggers
               SET status = $2, content_id = $3
             WHERE id = $1
            """,
            trigger_id,
            "running" if triggered else "failed",
            content_id,
        )

    await audit(actor=actor, action="content.trigger",
                target_type="channel", target_id=body.channel_id,
                after={"trigger_id": trigger_id, "triggered": triggered, "content_id": content_id},
                request=request)

    return {
        "status": "ok" if triggered else "queued",
        "trigger_id": trigger_id,
        "content_id": content_id,
    }



async def _table_exists(pool: Any, table: str) -> bool:
    return bool(await pool.fetchval(
        "SELECT 1 FROM information_schema.tables WHERE table_name=$1", table
    ))
