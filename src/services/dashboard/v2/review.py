"""Manual Review surface — Phase 3 (S5).

Endpoints:
  GET  /review/queue
  GET  /review/{video_id}
  POST /review/{video_id}/open
  POST /review/{video_id}/decide
  POST /review/{video_id}/script/edit
  POST /review/{video_id}/thumbnail/regenerate
  POST /review/{video_id}/comments
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.db import get_pool

from ._deps import Principal, audit, principal_dep, require_role

router = APIRouter()


class DecisionIn(BaseModel):
    decision: str    # approved|needs_edits|rejected|regenerating
    summary: str | None = None


class ScriptEditIn(BaseModel):
    kind: str        # full|section|paragraph|hook|shorten|expand|tone|emotion|repetition|restore
    range: dict | None = None
    prompt: str | None = None
    body: str | None = None
    target_version: int | None = None


class ThumbnailRegenIn(BaseModel):
    prompt_nudge: str | None = None
    keep_current: bool = True


class CommentIn(BaseModel):
    artifact: str
    body: str
    anchor: dict | None = None
    parent_id: int | None = None


# Queue
@router.get("/queue")
async def review_queue(
    state: str = "pending",
    channel_id: str | None = None,
    limit: int = 100,
    _: Principal = Depends(principal_dep),
):
    where = ["rs.state=$1"]
    args = [state]
    if channel_id:
        args.append(channel_id); where.append(f"rs.channel_id=${len(args)}")
    args.append(limit)
    pool = await get_pool()
    # INNER JOIN drops orphaned sessions whose underlying video record was
    # deleted — clicking those would 404 on the detail endpoint.
    rows = await pool.fetch(
        f"""SELECT rs.id, rs.video_id, rs.channel_id, rs.state, rs.opened_at,
                   rs.expires_at, v.title, v.topic, v.content_mode,
                   v.thumbnail_variants_urls, v.authenticity_score
              FROM review_sessions rs
              JOIN videos v ON v.content_id = rs.video_id
             WHERE {' AND '.join(where)}
             ORDER BY rs.opened_at DESC
             LIMIT ${len(args)}""",
        *args,
    )
    return {"data": [dict(r) for r in rows]}


@router.get("/{video_id}")
async def get_review(video_id: str, _: Principal = Depends(principal_dep)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        video = await conn.fetchrow("SELECT * FROM videos WHERE content_id=$1", video_id)
        if not video:
            raise HTTPException(404, "Video not found")
        session = await conn.fetchrow(
            "SELECT * FROM review_sessions WHERE video_id=$1 ORDER BY opened_at DESC LIMIT 1",
            video_id,
        )
        scripts = await conn.fetch(
            "SELECT id, version, source, content, diff_summary, created_by, created_at "
            "FROM script_versions WHERE video_id=$1 ORDER BY version DESC LIMIT 20",
            video_id,
        )
        thumbs = await conn.fetch(
            "SELECT id, version, source, minio_key, prompt, ctr_pred, composition, created_at "
            "FROM thumbnail_versions WHERE video_id=$1 ORDER BY version DESC LIMIT 12",
            video_id,
        )
        comments = []
        if session:
            comments = await conn.fetch(
                "SELECT id, artifact, anchor, author_id, body, parent_id, created_at "
                "FROM review_comments WHERE session_id=$1 ORDER BY created_at",
                session["id"],
            )
    return {
        "data": {
            "video": dict(video),
            "session": dict(session) if session else None,
            "script_versions": [dict(s) for s in scripts],
            "thumbnail_versions": [dict(t) for t in thumbs],
            "comments": [dict(c) for c in comments],
        }
    }


@router.post("/{video_id}/open")
async def open_review(
    video_id: str, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    video = await pool.fetchrow("SELECT channel_id FROM videos WHERE content_id=$1", video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    sid = await pool.fetchval(
        """INSERT INTO review_sessions (video_id, channel_id, state, opened_by)
           VALUES ($1,$2,'pending',$3) RETURNING id""",
        video_id, video["channel_id"], actor.user_id,
    )
    await pool.execute(
        "UPDATE videos SET review_state='pending' WHERE content_id=$1", video_id
    )
    await audit(actor=actor, action="review.open", target_type="video",
                target_id=video_id, request=request)
    return {"status": "ok", "session_id": sid}


@router.post("/{video_id}/decide")
async def decide(
    video_id: str, body: DecisionIn, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    # AE-368: explicit allow-list + clear error message so a UI sending the
    # action verb ('approve'/'reject') instead of the state value gets a
    # 400 that actually tells the engineer what to send.
    _VALID_DECISIONS = ("approved", "needs_edits", "rejected", "regenerating")
    if body.decision not in _VALID_DECISIONS:
        raise HTTPException(
            400,
            f"Invalid decision={body.decision!r}; expected one of {list(_VALID_DECISIONS)}",
        )
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            session = await conn.fetchrow(
                "SELECT id FROM review_sessions WHERE video_id=$1 "
                "ORDER BY opened_at DESC LIMIT 1",
                video_id,
            )
            if not session:
                raise HTTPException(409, "No review session is open")
            await conn.execute(
                """UPDATE review_sessions
                      SET state=$1, decided_by=$2, decided_at=NOW(), summary=$3
                    WHERE id=$4""",
                body.decision, actor.user_id, body.summary, session["id"],
            )
            await conn.execute(
                "UPDATE videos SET review_state=$1, updated_at=NOW() WHERE content_id=$2",
                body.decision, video_id,
            )
    # Notify Temporal workflow if it's waiting (best-effort).
    try:
        from src.services.dashboard.main import _get_temporal_client
        client = await _get_temporal_client()
        rows = await pool.fetch(
            "SELECT workflow_id FROM videos WHERE content_id=$1 AND workflow_id IS NOT NULL",
            video_id,
        )
        for r in rows:
            try:
                handle = client.get_workflow_handle(r["workflow_id"])
                await handle.signal("review_decision", {"decision": body.decision})
            except Exception:
                pass
    except Exception:
        pass

    await audit(actor=actor, action=f"review.{body.decision}", target_type="video",
                target_id=video_id, after={"summary": body.summary}, request=request)
    return {"status": "ok"}


_AI_KINDS = {"hook", "shorten", "expand", "tone", "emotion", "section", "paragraph", "repetition"}


_KIND_PROMPTS = {
    "hook":       "Rewrite ONLY the hook (first 3 seconds, ~25 words) to be more compelling. Keep the topic and angle. Return JSON: {\"body\": \"<full revised script>\"}.",
    "shorten":    "Tighten the script. Cut filler, trim repetition, target ~20 % shorter while keeping the core argument and the tone. Return JSON: {\"body\": \"<full revised script>\"}.",
    "expand":     "Expand the script with concrete examples and one specific case study, target ~25 % longer. Keep tone and structure. Return JSON: {\"body\": \"<full revised script>\"}.",
    "tone":       "Rewrite to match the requested tone shift. Preserve facts and structure. Return JSON: {\"body\": \"<full revised script>\"}.",
    "emotion":    "Rewrite for the requested emotional arc shift. Preserve facts. Return JSON: {\"body\": \"<full revised script>\"}.",
    "section":    "Rewrite ONLY the indicated section, leaving the rest of the script intact. Return JSON: {\"body\": \"<full revised script>\"}.",
    "paragraph":  "Rewrite ONLY the indicated paragraph(s). Keep adjacent context unchanged. Return JSON: {\"body\": \"<full revised script>\"}.",
    "repetition": "Find and remove repetitive phrases or ideas. Keep tone and structure intact. Return JSON: {\"body\": \"<full revised script>\"}.",
}


async def _ai_rewrite_script(*, video_id: str, kind: str, source: str,
                              user_prompt: str | None,
                              span: dict | None) -> str | None:
    """Best-effort LLM rewrite. Returns None if any step fails so the
    caller can fall back to the user's verbatim text."""
    try:
        from src.llm import route
        from src.providers.llm.base import LLMRequest
        from src.db import get_pool as _gp

        # Look up channel_id for budget enforcement.
        channel_id = ""
        try:
            pool = await _gp()
            row = await pool.fetchrow("SELECT channel_id FROM videos WHERE content_id=$1", video_id)
            channel_id = (row and row["channel_id"]) or ""
        except Exception:
            pass

        instr = _KIND_PROMPTS.get(kind, "")
        if not instr:
            return None
        sys = (
            "You are a senior YouTube script editor. Your output MUST be "
            "strict JSON with a single 'body' field containing the full "
            "revised script. Never wrap in markdown."
        )
        user = (
            f"{instr}\n\n"
            + (f"User instruction: {user_prompt}\n\n" if user_prompt else "")
            + (f"Span hint (JSON): {json.dumps(span)}\n\n" if span else "")
            + "ORIGINAL SCRIPT:\n" + source
        )
        result = await route(
            category="llm.script",
            request=LLMRequest(
                messages=[{"role": "system", "content": sys},
                          {"role": "user",   "content": user}],
                temperature=0.55, max_tokens=4000,
                response_format="json",
            ),
            channel_id=channel_id, content_id=video_id,
            record_usage=True,
        )
        text = (result.content or "").strip()
        try:
            parsed = json.loads(text)
            new_body = parsed.get("body")
            if isinstance(new_body, str) and new_body.strip():
                return new_body.strip()
        except Exception:
            # Some providers ignore the JSON instruction — accept their text.
            if text:
                return text
        return None
    except Exception as exc:  # noqa: BLE001
        import structlog
        structlog.get_logger().info("v2.script_edit.ai_failed",
                                    video_id=video_id, kind=kind, error=str(exc))
        return None


@router.post("/{video_id}/script/edit")
async def edit_script(
    video_id: str, body: ScriptEditIn, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    """Append a new script version.

    For ``kind in (rewrite-style)`` we invoke the LLM router to actually
    transform the body. For ``kind == 'full'`` (manual override) and any
    AI rewrite that fails, we persist whatever the human submitted.
    """
    pool = await get_pool()
    final_body = body.body or ""
    ai_used = False

    if body.kind in _AI_KINDS:
        # We need the source text. Either the caller already passed it as
        # body.body (the editor sends the latest version), or we fetch the
        # most recent version from the DB.
        source = body.body or ""
        if not source:
            row = await pool.fetchrow(
                "SELECT content FROM script_versions WHERE video_id=$1 "
                "ORDER BY version DESC LIMIT 1",
                video_id,
            )
            if row and row["content"]:
                try:
                    c = row["content"]
                    if isinstance(c, str):
                        c = json.loads(c)
                    source = (c.get("raw") if isinstance(c, dict) else "") or json.dumps(c)
                except Exception:
                    source = ""
        rewritten = await _ai_rewrite_script(
            video_id=video_id, kind=body.kind, source=source,
            user_prompt=body.prompt, span=body.range,
        )
        if rewritten:
            final_body = rewritten
            ai_used = True

    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await conn.fetchrow(
                "SELECT MAX(version) AS v FROM script_versions WHERE video_id=$1",
                video_id,
            )
            next_v = int(current["v"] or 0) + 1
            content = {"raw": final_body, "kind": body.kind,
                       "prompt": body.prompt, "range": body.range,
                       "ai_used": ai_used}
            vid = await conn.fetchval(
                """INSERT INTO script_versions
                        (video_id, version, source, content, diff_summary, created_by)
                   VALUES ($1,$2,$3,$4::jsonb,$5,$6) RETURNING id""",
                video_id, next_v,
                {
                    "full": "human", "section": "ai_section", "paragraph": "ai_section",
                    "hook": "ai_full", "shorten": "shorten", "expand": "expand",
                    "tone": "tone_change", "emotion": "tone_change",
                    "repetition": "ai_section", "restore": "restore",
                }.get(body.kind, "human"),
                json.dumps(content),
                f"{body.kind} edit by {actor.email or actor.source}"
                + (" (AI-rewritten)" if ai_used else ""),
                actor.user_id,
            )
    await audit(actor=actor, action="review.script.edit", target_type="video",
                target_id=video_id,
                after={"version": next_v, "kind": body.kind, "ai_used": ai_used},
                request=request)
    return {"status": "ok", "version": next_v, "version_id": vid, "ai_used": ai_used}


@router.post("/{video_id}/thumbnail/regenerate")
async def regenerate_thumbnail(
    video_id: str, body: ThumbnailRegenIn, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    """Trigger a fresh thumbnail pipeline run.

    Calls the Thumbnail service's full pipeline (5 concepts → DALL·E →
    Vision QC → best selection) and persists each generated variant as a
    new row in ``thumbnail_versions``. The caller doesn't block on
    completion — we kick off the request and return.
    """
    pool = await get_pool()
    video = await pool.fetchrow(
        "SELECT title, topic, channel_id FROM videos WHERE content_id=$1",
        video_id,
    )
    if not video:
        raise HTTPException(404, "Video not found")
    channel = await pool.fetchrow(
        "SELECT niche, thumbnail_style, primary_color FROM channels WHERE channel_id=$1",
        video["channel_id"],
    )
    style_hints: dict = {}
    if channel:
        if channel["thumbnail_style"]:
            style_hints["thumbnail_style"] = channel["thumbnail_style"]
        if channel["primary_color"]:
            style_hints["primary_color"] = channel["primary_color"]
    if body.prompt_nudge:
        style_hints["prompt_nudge"] = body.prompt_nudge

    triggered = False
    last_error: str | None = None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "http://thumbnail:8005/generate-thumbnail",
                json={
                    "content_id": video_id,
                    "channel_id": video["channel_id"],
                    "title": video["title"] or "",
                    "topic": video["topic"] or "",
                    "niche": (channel and channel["niche"]) or "",
                    "style_hints": style_hints,
                },
            )
            r.raise_for_status()
            triggered = True
            payload = r.json()
            # Persist all generated variants as thumbnail_versions rows.
            try:
                variants = (payload.get("data") or {}).get("variants", [])
                if variants:
                    cur = await pool.fetchrow(
                        "SELECT MAX(version) AS v FROM thumbnail_versions WHERE video_id=$1",
                        video_id,
                    )
                    next_v = int((cur and cur["v"]) or 0)
                    async with pool.acquire() as conn:
                        async with conn.transaction():
                            for var in variants:
                                next_v += 1
                                await conn.execute(
                                    """INSERT INTO thumbnail_versions
                                          (video_id, version, source, image_uri,
                                           prompt, ctr_pred, vision_qc_score)
                                       VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                                    video_id, next_v,
                                    "ai_regen" if not body.keep_current else "ai_regen_keep",
                                    var.get("image_uri") or var.get("url") or "",
                                    (var.get("dall_e_prompt") or "")[:4000],
                                    float(var.get("predicted_ctr") or 0.0),
                                    float(var.get("vision_qc_score") or 0.0),
                                )
            except Exception as exc:  # noqa: BLE001
                import structlog
                structlog.get_logger().warning(
                    "v2.thumb_regen.persist_failed",
                    video_id=video_id, error=str(exc),
                )
    except Exception as exc:  # noqa: BLE001
        last_error = str(exc)
        import structlog
        structlog.get_logger().warning(
            "v2.thumb_regen.dispatch_failed",
            video_id=video_id, error=last_error,
        )

    await audit(actor=actor, action="review.thumbnail.regenerate", target_type="video",
                target_id=video_id,
                after={**body.model_dump(), "triggered": triggered,
                       "error": last_error},
                request=request)
    return {"status": "ok" if triggered else "queued",
            "triggered": triggered, "error": last_error}


@router.post("/{video_id}/comments")
async def add_comment(
    video_id: str, body: CommentIn, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    session = await pool.fetchrow(
        "SELECT id FROM review_sessions WHERE video_id=$1 ORDER BY opened_at DESC LIMIT 1",
        video_id,
    )
    if not session:
        raise HTTPException(409, "No review session is open")
    cid = await pool.fetchval(
        """INSERT INTO review_comments (session_id, artifact, anchor, author_id, body, parent_id)
           VALUES ($1,$2,$3::jsonb,$4,$5,$6) RETURNING id""",
        session["id"], body.artifact,
        json.dumps(body.anchor) if body.anchor else None,
        actor.user_id, body.body, body.parent_id,
    )
    await pool.execute(
        "UPDATE videos SET review_notes_count=review_notes_count+1 WHERE content_id=$1",
        video_id,
    )
    return {"status": "ok", "id": cid}
