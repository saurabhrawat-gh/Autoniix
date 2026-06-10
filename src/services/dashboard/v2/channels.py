"""Channel wizard + settings — Phase 1 (S1).

Endpoints:
  POST   /channels                       Create channel from full payload
  GET    /channels                       List with profile join
  GET    /channels/{id}                  Full bundle (channel + profile + pillars + ...)
  PUT    /channels/{id}                  Patch core columns
  PUT    /channels/{id}/profile          Upsert extended profile
  POST   /channels/{id}/pillars          Add pillar
  PUT    /channels/{id}/pillars/{pid}    Update pillar
  DELETE /channels/{id}/pillars/{pid}
  POST   /channels/{id}/topic-rules      Add topic rule (avoid/safe/core/...)
  DELETE /channels/{id}/topic-rules/{rid}
  POST   /channels/{id}/references       Register a reference (URL or pre-uploaded MinIO key)
  DELETE /channels/{id}/references/{rid}
  POST   /channels/{id}/memory           Append memory entry
  GET    /channels/presets               List presets
  POST   /channels/drafts                Create draft
  PUT    /channels/drafts/{id}           Autosave
  GET    /channels/drafts/{id}
  POST   /channels/ai/field-suggest      AI suggestion for a field
"""
from __future__ import annotations

import json
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from src.db import get_pool
from ._deps import Principal, audit, principal_dep, require_role

router = APIRouter()


# Schemas
class ChannelCreate(BaseModel):
    channel_id: str | None = None
    channel_name: str
    niche: str
    sub_niche: str | None = None
    platform: str = "youtube"
    handle: str | None = None
    description: str | None = None
    content_mode: str = "short"
    primary_language: str = "en"
    target_audience: str | None = None
    geography: str | None = None
    target_age_group: str | None = None
    tone: str | None = None
    brand_personality: str | None = None
    mission: str | None = None
    vision: str | None = None
    humor_style: str | None = None
    narration_style: str | None = None
    music_style: str | None = None
    lut_preference: str | None = None
    transition_preference: str | None = None
    typography_preference: str | None = None
    meme_intensity: int | None = None
    emotion_intensity: int | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    thumbnail_style: str | None = None
    pacing_style: str | None = None
    auto_upload: bool = False
    human_review_required: str = "first_10"
    human_review_ratio: float = 0.0
    review_timeout_hours: int = 24
    max_daily_api_spend: float = 5.00
    videos_per_week_short: int = 7
    videos_per_week_long: int = 1
    short_form_duration: int = 60
    long_form_duration: int = 600
    elevenlabs_voice_id: str | None = None
    voice_stability: float | None = None
    voice_similarity: float | None = None
    voice_style: float | None = None
    pillars: list[dict] = Field(default_factory=list)
    topic_rules: list[dict] = Field(default_factory=list)
    references: list[dict] = Field(default_factory=list)
    preset: str | None = None
    extra: dict = Field(default_factory=dict)

    @field_validator("platform")
    @classmethod
    def platform_must_be_youtube(cls, v: str) -> str:
        if v != "youtube":
            raise ValueError("Only 'youtube' platform is supported in v1")
        return v


class ChannelPatch(BaseModel):
    channel_name: str | None = None
    niche: str | None = None
    sub_niche: str | None = None
    status: str | None = None
    auto_upload: bool | None = None
    human_review_required: str | None = None
    human_review_ratio: float | None = None
    review_timeout_hours: int | None = None
    max_daily_api_spend: float | None = None
    handle: str | None = None
    description: str | None = None
    primary_language: str | None = None
    geography: str | None = None
    target_age_group: str | None = None
    target_audience: str | None = None
    tone: str | None = None
    brand_personality: str | None = None
    humor_style: str | None = None
    narration_style: str | None = None
    music_style: str | None = None
    lut_preference: str | None = None
    transition_preference: str | None = None
    typography_preference: str | None = None
    meme_intensity: int | None = None
    emotion_intensity: int | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    thumbnail_style: str | None = None
    pacing_style: str | None = None
    elevenlabs_voice_id: str | None = None
    voice_stability: float | None = None
    voice_similarity: float | None = None
    voice_style: float | None = None


class PillarIn(BaseModel):
    name: str
    description: str | None = None
    weight: float = 1.0
    examples: list[str] = Field(default_factory=list)
    position: int = 0


class TopicRuleIn(BaseModel):
    kind: str  # avoid|safe|core|inspiration_competitor|primary_competitor
    value: str
    metadata: dict = Field(default_factory=dict)


class ReferenceIn(BaseModel):
    kind: str
    label: str | None = None
    uri: str | None = None
    minio_key: str | None = None
    parsed_metadata: dict = Field(default_factory=dict)


class ChannelDeleteIn(BaseModel):
    confirmation: str
    password: str

    @field_validator("confirmation")
    @classmethod
    def confirmation_must_match(cls, v: str) -> str:
        # Case-sensitive — owner must literally type "delete"
        if v != "delete":
            raise ValueError("confirmation must be the literal string 'delete'")
        return v


class MemoryIn(BaseModel):
    memory_type: str
    content: dict
    confidence: float | None = None


class DraftIn(BaseModel):
    current_step: int = 1
    payload: dict = Field(default_factory=dict)


class FieldSuggestIn(BaseModel):
    field: str
    context: dict = Field(default_factory=dict)


# Helpers
def _new_channel_id(name: str) -> str:
    """Lowercase slug + 4-char suffix (matches existing 20-char limit)."""
    base = "".join(c for c in (name or "ch").lower() if c.isalnum())[:14] or "ch"
    return f"{base}_{secrets.token_hex(2)}"


def _completeness(profile: dict) -> int:
    """Heuristic 0-100 score of how well a profile has been filled."""
    fields = [
        "mission", "vision", "brand_personality", "tone", "narration_style",
        "music_style", "humor_style", "lut_preference",
    ]
    filled = sum(1 for f in fields if profile.get(f))
    return int(round((filled / len(fields)) * 100))


# Channel CRUD
@router.post("")
async def create_channel(
    body: ChannelCreate,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    channel_id = body.channel_id or _new_channel_id(body.channel_name)

    # Apply preset if specified
    preset_payload: dict[str, Any] = {}
    if body.preset:
        row = await pool.fetchrow(
            "SELECT payload FROM channel_presets WHERE name=$1", body.preset
        )
        if row:
            raw = row["payload"] or {}
            preset_payload = json.loads(raw) if isinstance(raw, str) else raw

    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT 1 FROM channels WHERE channel_id=$1", channel_id
            )
            if existing:
                raise HTTPException(409, f"channel_id {channel_id!r} exists")

            # Insert minimal core row; new columns nullable.
            await conn.execute(
                """
                INSERT INTO channels (
                    channel_id, channel_name, niche, sub_niche, content_mode,
                    target_audience, primary_language, geography, target_age_group,
                    platform, handle, description, mission, vision, brand_personality,
                    humor_style, narration_style, music_style, lut_preference,
                    transition_preference, typography_preference, meme_intensity,
                    emotion_intensity, primary_color, secondary_color, thumbnail_style,
                    pacing_style, auto_upload, human_review_required, human_review_ratio,
                    review_timeout_hours, max_daily_api_spend,
                    videos_per_week_short, videos_per_week_long,
                    short_form_duration, long_form_duration,
                    elevenlabs_voice_id, voice_stability, voice_similarity, voice_style,
                    source, status, environment, workspace_id
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,
                    $16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,
                    $31,$32,$33,$34,$35,$36,$37,$38,$39,$40,$41,$42,$43,$44
                )
                """,
                channel_id, body.channel_name, body.niche, body.sub_niche,
                body.content_mode, body.target_audience, body.primary_language,
                body.geography, body.target_age_group, body.platform, body.handle,
                body.description, body.mission, body.vision, body.brand_personality,
                body.humor_style or preset_payload.get("narration_style"),
                body.narration_style or preset_payload.get("narration_style"),
                body.music_style or preset_payload.get("music_style"),
                body.lut_preference, body.transition_preference,
                body.typography_preference, body.meme_intensity, body.emotion_intensity,
                body.primary_color, body.secondary_color, body.thumbnail_style,
                body.pacing_style or preset_payload.get("pacing_style"),
                body.auto_upload, body.human_review_required,
                body.human_review_ratio, body.review_timeout_hours,
                body.max_daily_api_spend, body.videos_per_week_short,
                body.videos_per_week_long, body.short_form_duration,
                body.long_form_duration, body.elevenlabs_voice_id,
                body.voice_stability, body.voice_similarity, body.voice_style,
                "wizard", "active", "production", actor.workspace_id,
            )

            # Profile (extended payload)
            extended = body.extra or {}
            extended.update({k: getattr(body, k) for k in (
                "mission", "vision", "brand_personality", "tone",
                "humor_style", "narration_style", "music_style",
                "lut_preference", "transition_preference", "typography_preference",
                "meme_intensity", "emotion_intensity", "primary_language",
                "geography", "target_age_group",
            ) if getattr(body, k, None) is not None})

            await conn.execute(
                """
                INSERT INTO channel_profiles
                    (channel_id, payload, mission, vision, brand_personality,
                     tone, completeness_score)
                VALUES ($1, $2::jsonb, $3, $4, $5, $6, $7)
                """,
                channel_id, json.dumps(extended), body.mission, body.vision,
                body.brand_personality, body.tone, _completeness(extended),
            )

            # Pillars
            for i, p in enumerate(body.pillars):
                await conn.execute(
                    """INSERT INTO channel_pillars (channel_id, name, description, weight, examples, position)
                       VALUES ($1,$2,$3,$4,$5::jsonb,$6)""",
                    channel_id, p.get("name", f"Pillar {i+1}"), p.get("description"),
                    float(p.get("weight", 1.0)), json.dumps(p.get("examples", [])),
                    int(p.get("position", i)),
                )

            # Topic rules
            for r in body.topic_rules:
                if r.get("kind") and r.get("value"):
                    await conn.execute(
                        """INSERT INTO channel_topic_rules (channel_id, kind, value, metadata)
                           VALUES ($1,$2,$3,$4::jsonb)""",
                        channel_id, r["kind"], r["value"],
                        json.dumps(r.get("metadata", {})),
                    )

            # References
            for r in body.references:
                if r.get("kind"):
                    await conn.execute(
                        """INSERT INTO channel_references
                            (channel_id, kind, label, uri, minio_key, parsed_metadata, uploaded_by)
                           VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7)""",
                        channel_id, r["kind"], r.get("label"), r.get("uri"),
                        r.get("minio_key"), json.dumps(r.get("parsed_metadata", {})),
                        actor.user_id,
                    )

    await audit(actor=actor, action="channel.create", target_type="channel",
                target_id=channel_id, after=body.model_dump(), request=request)
    return {"status": "ok", "channel_id": channel_id}


@router.get("")
async def list_channels(
    include_archived: bool = False,
    enrich: bool = True,
    actor: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    args: list[Any] = [actor.workspace_id]
    conditions = ["c.workspace_id = $1"]
    if not include_archived:
        conditions.append("c.status != 'archived'")
    where = "WHERE " + " AND ".join(conditions)
    rows = await pool.fetch(
        f"""
        SELECT c.channel_id, c.channel_name, c.niche, c.sub_niche, c.content_mode,
               c.platform, c.handle, c.status, c.auto_upload,
               c.human_review_required, c.human_review_ratio,
               c.created_at,
               c.primary_language       AS language,
               c.publish_cadence,
               c.videos_per_week_short,
               c.videos_per_week_long,
               c.environment,
               cp.completeness_score, cp.tone, cp.brand_personality,
               (SELECT COUNT(*) FROM channel_pillars p WHERE p.channel_id = c.channel_id) AS pillar_count,
               (SELECT COUNT(*) FROM channel_references r WHERE r.channel_id = c.channel_id) AS reference_count
          FROM channels c
          LEFT JOIN channel_profiles cp ON cp.channel_id = c.channel_id
          {where}
          ORDER BY c.created_at DESC, c.channel_id
        """,
        *args,
    )
    data = [dict(r) for r in rows]
    if enrich and data:
        data = await _enrich_channel_list(pool, data)
    return {"data": data}


@router.get("/presets")
async def list_presets(_: Principal = Depends(principal_dep)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, name, description, payload, is_system FROM channel_presets ORDER BY is_system DESC, name"
    )
    return {"data": [dict(r) for r in rows]}


@router.get("/stats")
async def dashboard_stats_early(_: Principal = Depends(principal_dep)):
    """Forwarded to the real implementation registered after enrichment helper."""
    return await _dashboard_stats_impl(_)


@router.get("/{channel_id}")
async def get_channel(channel_id: str, actor: Principal = Depends(principal_dep)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        ch = await conn.fetchrow(
            "SELECT * FROM channels WHERE channel_id=$1 AND workspace_id=$2",
            channel_id, actor.workspace_id,
        )
        if not ch:
            raise HTTPException(404, "Channel not found")
        profile = await conn.fetchrow(
            "SELECT * FROM channel_profiles WHERE channel_id=$1", channel_id
        )
        pillars = await conn.fetch(
            "SELECT * FROM channel_pillars WHERE channel_id=$1 ORDER BY position", channel_id
        )
        rules = await conn.fetch(
            "SELECT * FROM channel_topic_rules WHERE channel_id=$1 ORDER BY kind, id", channel_id
        )
        refs = await conn.fetch(
            "SELECT id, kind, label, uri, minio_key, parsed_metadata, uploaded_at "
            "FROM channel_references WHERE channel_id=$1 ORDER BY uploaded_at DESC",
            channel_id,
        )
        memory = await conn.fetch(
            "SELECT id, memory_type, content, confidence, created_at "
            "FROM channel_memory WHERE channel_id=$1 ORDER BY created_at DESC LIMIT 50",
            channel_id,
        )
    return {
        "data": {
            "channel": dict(ch),
            "profile": dict(profile) if profile else None,
            "pillars": [dict(p) for p in pillars],
            "topic_rules": [dict(r) for r in rules],
            "references": [dict(r) for r in refs],
            "memory": [dict(m) for m in memory],
        }
    }


@router.put("/{channel_id}")
async def patch_channel(
    channel_id: str,
    body: ChannelPatch,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return {"status": "noop"}
    pool = await get_pool()
    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates.keys()))
    values = list(updates.values())
    before = await pool.fetchrow(
        f"SELECT {', '.join(updates.keys())} FROM channels WHERE channel_id=$1", channel_id
    )
    if not before:
        raise HTTPException(404, "Channel not found")
    await pool.execute(
        f"UPDATE channels SET {sets}, updated_at=NOW() WHERE channel_id=$1",
        channel_id, *values,
    )
    await audit(actor=actor, action="channel.update", target_type="channel",
                target_id=channel_id, before=dict(before), after=updates, request=request)
    return {"status": "ok"}


@router.put("/{channel_id}/profile")
async def upsert_profile(
    channel_id: str,
    body: dict,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    payload = body.get("payload") or {}
    score = _completeness(payload)
    await pool.execute(
        """
        INSERT INTO channel_profiles (channel_id, payload, mission, vision,
            brand_personality, tone, completeness_score, updated_at)
        VALUES ($1, $2::jsonb, $3, $4, $5, $6, $7, NOW())
        ON CONFLICT (channel_id) DO UPDATE SET
            payload = EXCLUDED.payload,
            mission = EXCLUDED.mission,
            vision = EXCLUDED.vision,
            brand_personality = EXCLUDED.brand_personality,
            tone = EXCLUDED.tone,
            completeness_score = EXCLUDED.completeness_score,
            updated_at = NOW()
        """,
        channel_id, json.dumps(payload), payload.get("mission"), payload.get("vision"),
        payload.get("brand_personality"), payload.get("tone"), score,
    )
    await audit(actor=actor, action="channel.profile.upsert", target_type="channel_profile",
                target_id=channel_id, after={"completeness": score}, request=request)
    return {"status": "ok", "completeness_score": score}


# Pillars
@router.post("/{channel_id}/pillars")
async def add_pillar(
    channel_id: str, body: PillarIn, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    pid = await pool.fetchval(
        """INSERT INTO channel_pillars (channel_id, name, description, weight, examples, position)
           VALUES ($1,$2,$3,$4,$5::jsonb,$6) RETURNING id""",
        channel_id, body.name, body.description, body.weight,
        json.dumps(body.examples), body.position,
    )
    await audit(actor=actor, action="channel.pillar.create", target_type="channel_pillar",
                target_id=str(pid), after=body.model_dump(), request=request)
    return {"status": "ok", "id": pid}


@router.put("/{channel_id}/pillars/{pillar_id}")
async def update_pillar(
    channel_id: str, pillar_id: int, body: PillarIn, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    res = await pool.execute(
        """UPDATE channel_pillars
              SET name=$1, description=$2, weight=$3, examples=$4::jsonb, position=$5
            WHERE id=$6 AND channel_id=$7""",
        body.name, body.description, body.weight, json.dumps(body.examples),
        body.position, pillar_id, channel_id,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Pillar not found")
    await audit(actor=actor, action="channel.pillar.update", target_type="channel_pillar",
                target_id=str(pillar_id), after=body.model_dump(), request=request)
    return {"status": "ok"}


@router.delete("/{channel_id}/pillars/{pillar_id}")
async def delete_pillar(
    channel_id: str, pillar_id: int, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    res = await pool.execute(
        "DELETE FROM channel_pillars WHERE id=$1 AND channel_id=$2",
        pillar_id, channel_id,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Pillar not found")
    await audit(actor=actor, action="channel.pillar.delete", target_type="channel_pillar",
                target_id=str(pillar_id), request=request)
    return {"status": "ok"}


# Topic rules
@router.post("/{channel_id}/topic-rules")
async def add_topic_rule(
    channel_id: str, body: TopicRuleIn, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    rid = await pool.fetchval(
        """INSERT INTO channel_topic_rules (channel_id, kind, value, metadata)
           VALUES ($1,$2,$3,$4::jsonb) RETURNING id""",
        channel_id, body.kind, body.value, json.dumps(body.metadata),
    )
    await audit(actor=actor, action="channel.topic_rule.create", target_type="channel_topic_rule",
                target_id=str(rid), after=body.model_dump(), request=request)
    return {"status": "ok", "id": rid}


@router.delete("/{channel_id}/topic-rules/{rule_id}")
async def delete_topic_rule(
    channel_id: str, rule_id: int, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    res = await pool.execute(
        "DELETE FROM channel_topic_rules WHERE id=$1 AND channel_id=$2",
        rule_id, channel_id,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Rule not found")
    await audit(actor=actor, action="channel.topic_rule.delete", target_type="channel_topic_rule",
                target_id=str(rule_id), request=request)
    return {"status": "ok"}


# References
@router.post("/{channel_id}/references")
async def add_reference(
    channel_id: str, body: ReferenceIn, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    rid = await pool.fetchval(
        """INSERT INTO channel_references (channel_id, kind, label, uri, minio_key, parsed_metadata, uploaded_by)
           VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7) RETURNING id""",
        channel_id, body.kind, body.label, body.uri, body.minio_key,
        json.dumps(body.parsed_metadata), actor.user_id,
    )
    await audit(actor=actor, action="channel.reference.create", target_type="channel_reference",
                target_id=str(rid), after=body.model_dump(), request=request)
    return {"status": "ok", "id": rid}


@router.delete("/{channel_id}/references/{ref_id}")
async def delete_reference(
    channel_id: str, ref_id: int, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    res = await pool.execute(
        "DELETE FROM channel_references WHERE id=$1 AND channel_id=$2", ref_id, channel_id
    )
    if res.endswith("0"):
        raise HTTPException(404, "Reference not found")
    await audit(actor=actor, action="channel.reference.delete", target_type="channel_reference",
                target_id=str(ref_id), request=request)
    return {"status": "ok"}


# Memory
@router.post("/{channel_id}/memory")
async def add_memory(
    channel_id: str, body: MemoryIn, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    mid = await pool.fetchval(
        """INSERT INTO channel_memory (channel_id, memory_type, content, confidence)
           VALUES ($1,$2,$3::jsonb,$4) RETURNING id""",
        channel_id, body.memory_type, json.dumps(body.content), body.confidence,
    )
    await audit(actor=actor, action="channel.memory.add", target_type="channel_memory",
                target_id=str(mid), after=body.model_dump(), request=request)
    return {"status": "ok", "id": mid}


# Drafts
@router.post("/drafts")
async def create_draft(
    body: DraftIn,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    did = await pool.fetchval(
        """INSERT INTO channel_drafts (user_id, current_step, payload)
           VALUES ($1,$2,$3::jsonb) RETURNING id""",
        actor.user_id, body.current_step, json.dumps(body.payload),
    )
    return {"status": "ok", "id": did}


@router.put("/drafts/{draft_id}")
async def save_draft(
    draft_id: int, body: DraftIn,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    res = await pool.execute(
        """UPDATE channel_drafts
              SET current_step=$1, payload=$2::jsonb, updated_at=NOW()
            WHERE id=$3 AND (user_id=$4 OR user_id IS NULL)""",
        body.current_step, json.dumps(body.payload), draft_id, actor.user_id,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Draft not found")
    return {"status": "ok"}


@router.get("/drafts/{draft_id}")
async def get_draft(
    draft_id: int,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, current_step, payload, updated_at FROM channel_drafts WHERE id=$1",
        draft_id,
    )
    if not row:
        raise HTTPException(404, "Draft not found")
    return {"data": dict(row)}


# AI field-suggest
@router.post("/ai/field-suggest")
async def field_suggest(
    body: FieldSuggestIn,
    _: Principal = Depends(principal_dep),
):
    """Heuristic + LLM-backed suggestion for wizard fields.

    Falls back to a rule-based suggestion if the LLM is unavailable, so the
    wizard always returns something usable in dev/test.
    """
    field = body.field
    ctx = body.context or {}
    fallback = _heuristic_suggest(field, ctx)

    # Try the LLM router (fully respects the per-channel budget cap +
    # provider ladder). Fall back to a deterministic heuristic so the
    # wizard always gives the user something usable in dev/test.
    try:
        from src.llm import route
        from src.providers.llm.base import LLMRequest

        prompt = (
            f"You help a creator fill in the '{field}' field of a content "
            f"channel configuration. Given the context, write a single "
            f"concise, practical value (under 240 characters), and a one-"
            f"sentence rationale. Always return strict JSON with keys "
            f"'suggestion' and 'rationale'.\n\n"
            f"Context (JSON): {json.dumps(ctx, ensure_ascii=False)}"
        )
        result = await route(
            category="llm.ideation",
            request=LLMRequest(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6, max_tokens=400,
                response_format="json",
            ),
            channel_id=str(ctx.get("channel_id") or ""),
            content_id="",
            record_usage=True,
        )
        text = (result.content or "").strip()
        try:
            parsed = json.loads(text)
            sug = str(parsed.get("suggestion") or "").strip()[:240]
            rat = str(parsed.get("rationale") or "").strip()[:240]
            if sug:
                return {"data": {"suggestion": sug, "rationale": rat or "llm",
                                 "provider": result.provider, "model": result.model}}
        except Exception:
            # Provider returned plain text — still usable.
            if text:
                return {"data": {"suggestion": text[:240], "rationale": "llm",
                                 "provider": result.provider, "model": result.model}}
    except Exception as exc:  # noqa: BLE001
        # Budget exceeded, ladder exhausted, or provider-side error — log
        # and fall through to the heuristic so the UI still works.
        import structlog
        structlog.get_logger().info("v2.field_suggest.fallback", error=str(exc))
    return {"data": {"suggestion": fallback, "rationale": "heuristic"}}


# Wave 5: enrichment helper + action endpoints

async def _enrich_channel_list(pool: Any, channels: list[dict]) -> list[dict]:
    """Batch-attach stats, weekly_usage, and active_jobs to each channel dict."""
    ids = [c["channel_id"] for c in channels]

    # Lifetime per-channel stats
    stat_rows = await pool.fetch(
        """SELECT channel_id,
                  COUNT(*) FILTER (WHERE status IN ('delivered','test_delivered')) AS delivered,
                  COUNT(*) FILTER (WHERE status NOT IN
                      ('delivered','test_delivered','failed','stopped','superseded','rejected')) AS in_progress,
                  COUNT(*) AS total
             FROM videos WHERE channel_id = ANY($1::text[])
             GROUP BY channel_id""",
        ids,
    )
    stats_map = {r["channel_id"]: r for r in stat_rows}

    # Weekly usage (current ISO week)
    weekly_rows = await pool.fetch(
        """SELECT channel_id,
                  COUNT(*) FILTER (WHERE content_mode = 'short'
                      AND status NOT IN ('failed','stopped','superseded','rejected')) AS short_used,
                  COUNT(*) FILTER (WHERE content_mode = 'long_form'
                      AND status NOT IN ('failed','stopped','superseded','rejected')) AS long_used
             FROM videos
            WHERE channel_id = ANY($1::text[])
              AND created_at >= date_trunc('week', NOW())
            GROUP BY channel_id""",
        ids,
    )
    weekly_map = {r["channel_id"]: r for r in weekly_rows}

    # Active (non-terminal) jobs — latest per channel+mode
    job_rows = await pool.fetch(
        """SELECT DISTINCT ON (channel_id, content_mode)
                  channel_id, content_id, status, content_mode
             FROM videos
            WHERE channel_id = ANY($1::text[])
              AND status NOT IN ('delivered','test_delivered','failed','stopped',
                                 'superseded','rejected','retrying')
            ORDER BY channel_id, content_mode, created_at DESC""",
        ids,
    )
    job_map: dict[str, list] = {}
    for r in job_rows:
        job_map.setdefault(r["channel_id"], []).append({
            "content_id": r["content_id"],
            "status": r["status"],
            "content_mode": r["content_mode"],
            "is_paused": False,
        })

    for ch in channels:
        cid = ch["channel_id"]
        s = stats_map.get(cid)
        w = weekly_map.get(cid)
        ch["stats"] = {
            "delivered":   int(s["delivered"])   if s else 0,
            "in_progress": int(s["in_progress"]) if s else 0,
            "total":       int(s["total"])       if s else 0,
        }
        ch["weekly_usage"] = {
            "short":    {"used": int(w["short_used"])  if w else 0,
                         "limit": ch.get("videos_per_week_short") or 7},
            "long_form": {"used": int(w["long_used"]) if w else 0,
                          "limit": ch.get("videos_per_week_long") or 1},
        }
        ch["active_jobs"] = job_map.get(cid, [])
    return channels


async def _dashboard_stats_impl(_: Principal):
    """Shared implementation for GET /stats (registered early to beat /{channel_id})."""  # noqa
    pool = await get_pool()
    ch = await pool.fetchrow(
        """SELECT COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE status = 'active')   AS active,
                  COUNT(*) FILTER (WHERE status = 'disabled') AS disabled,
                  COUNT(*) FILTER (WHERE status = 'archived') AS archived
             FROM channels"""
    )
    vid = await pool.fetchrow(
        """SELECT COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE status IN ('delivered','test_delivered')) AS delivered,
                  COUNT(*) FILTER (WHERE status = 'failed')   AS failed,
                  COUNT(*) FILTER (WHERE status NOT IN
                      ('delivered','test_delivered','failed','stopped','superseded','rejected')) AS in_progress,
                  COALESCE(SUM(total_cost), 0) AS total_cost
             FROM videos WHERE created_at::date = CURRENT_DATE"""
    )
    budget_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'daily_budget_limit'"
    )
    stop_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'emergency_stop'"
    )
    return {
        "data": {
            "channels": dict(ch),
            "today": {
                "videos_total": int(vid["total"]),
                "delivered":    int(vid["delivered"]),
                "failed":       int(vid["failed"]),
                "in_progress":  int(vid["in_progress"]),
                "cost":         float(vid["total_cost"]),
            },
            "budget": {
                "daily_limit": float(budget_row["config_value"]) if budget_row else 0.0,
                "today_cost":  float(vid["total_cost"]),
            },
            "emergency_stop": (stop_row["config_value"] or "").lower() in ("true", "1") if stop_row else False,
        }
    }


# Channel status actions

@router.put("/{channel_id}/enable")
async def enable_channel(
    channel_id: str, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    res = await pool.execute(
        "UPDATE channels SET status='active', updated_at=NOW() WHERE channel_id=$1", channel_id
    )
    if res.endswith("0"):
        raise HTTPException(404, "Channel not found")
    await audit(actor=actor, action="channel.enable", target_type="channel",
                target_id=channel_id, request=request)
    return {"status": "ok"}


@router.put("/{channel_id}/disable")
async def disable_channel(
    channel_id: str, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    res = await pool.execute(
        "UPDATE channels SET status='disabled', updated_at=NOW() WHERE channel_id=$1", channel_id
    )
    if res.endswith("0"):
        raise HTTPException(404, "Channel not found")
    await audit(actor=actor, action="channel.disable", target_type="channel",
                target_id=channel_id, request=request)
    return {"status": "ok"}


@router.put("/{channel_id}/archive")
async def archive_channel(
    channel_id: str, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    res = await pool.execute(
        "UPDATE channels SET status='archived', updated_at=NOW() WHERE channel_id=$1", channel_id
    )
    if res.endswith("0"):
        raise HTTPException(404, "Channel not found")
    await audit(actor=actor, action="channel.archive", target_type="channel",
                target_id=channel_id, request=request)
    return {"status": "ok"}


@router.put("/{channel_id}/restore")
async def restore_channel(
    channel_id: str, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    res = await pool.execute(
        "UPDATE channels SET status='disabled', updated_at=NOW() WHERE channel_id=$1 AND status='archived'",
        channel_id,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Channel not found or not archived")
    await audit(actor=actor, action="channel.restore", target_type="channel",
                target_id=channel_id, request=request)
    return {"status": "ok"}


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    body: ChannelDeleteIn,
    request: Request,
    actor: Principal = Depends(require_role("owner")),
):
    """Hard-delete a channel.

    Gated by:
      * workspace ``owner`` role (enforced at the dependency level)
      * literal ``confirmation == "delete"`` (validated at schema level)
      * server-side re-verification of the actor's account password
      * channel must belong to the actor's workspace
      * blocked when any ``videos`` row references the channel (FK is NO ACTION)

    On success, FK cascades remove ``channel_*``, ``projects``, ``series``;
    ``provider_credentials.channel_id`` is set to ``NULL``.  Pre-delete state
    is captured into the audit log for forensics.
    """
    if not actor.user_id:
        raise HTTPException(403, "No user context")

    pool = await get_pool()

    # Re-verify password against the live user row
    user = await pool.fetchrow(
        "SELECT password_hash FROM users WHERE id=$1", actor.user_id
    )
    if not user:
        raise HTTPException(404, detail={"code": "user_not_found"})
    from .auth import _verify_pw  # local import to avoid circular deps
    if not _verify_pw(body.password, user["password_hash"] or ""):
        raise HTTPException(403, detail={"code": "wrong_password"})

    # Channel must exist AND belong to actor's workspace
    channel = await pool.fetchrow(
        """SELECT channel_id, channel_name, niche, platform, status,
                  workspace_id, created_at
             FROM channels WHERE channel_id=$1""",
        channel_id,
    )
    if not channel or channel["workspace_id"] != actor.workspace_id:
        # Don't leak existence of channels in other workspaces
        raise HTTPException(404, detail={"code": "channel_not_found"})

    # Refuse if any videos exist — protects historical content
    video_count = await pool.fetchval(
        "SELECT COUNT(*) FROM videos WHERE channel_id=$1", channel_id
    )
    if video_count and video_count > 0:
        raise HTTPException(
            409,
            detail={
                "code": "has_videos",
                "message": (
                    f"Cannot delete channel with {video_count} published "
                    "videos. Archive instead."
                ),
                "video_count": video_count,
            },
        )

    # Detect existing YouTube linkage so we can emit a separate audit event
    yt_linked = await pool.fetchval(
        """SELECT 1 FROM provider_credentials
            WHERE channel_id=$1 AND category='youtube' LIMIT 1""",
        channel_id,
    )

    # Capture forensic snapshot
    snapshot = {
        "channel_id": channel["channel_id"],
        "channel_name": channel["channel_name"],
        "niche": channel["niche"],
        "platform": channel["platform"],
        "status": channel["status"],
        "workspace_id": channel["workspace_id"],
        "created_at": channel["created_at"].isoformat()
            if channel["created_at"] else None,
    }

    # Delete — DB cascades + SET NULL handle the rest
    await pool.execute("DELETE FROM channels WHERE channel_id=$1", channel_id)

    await audit(
        actor=actor,
        action="channel.delete",
        target_type="channel",
        target_id=channel_id,
        before=snapshot,
        request=request,
    )

    if yt_linked:
        await audit(
            actor=actor,
            action="provider.youtube.unlink",
            target_type="provider_credentials",
            target_id=channel_id,
            before={"channel_id": channel_id, "reason": "channel_hard_delete"},
            request=request,
        )

    return {"status": "ok", "data": {"deleted": True, "channel_id": channel_id}}


@router.post("/{channel_id}/clone")
async def clone_channel(
    channel_id: str, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    """Proxy to legacy clone endpoint (Temporal-aware)."""
    import httpx
    token = request.headers.get("Authorization", "")
    bff_base = "http://localhost:8020"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{bff_base}/api/channels/{channel_id}/clone",
                headers={"Authorization": token},
            )
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.json().get("detail", "Clone failed"))
        result = resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(502, f"Legacy BFF unreachable: {exc}") from exc
    await audit(actor=actor, action="channel.clone", target_type="channel",
                target_id=channel_id, request=request)
    return result


@router.get("/{channel_id}/export")
async def export_channel(
    channel_id: str,
    _: Principal = Depends(principal_dep),
):
    """Return full channel config as a JSON download."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        ch = await conn.fetchrow("SELECT * FROM channels WHERE channel_id=$1", channel_id)
        if not ch:
            raise HTTPException(404, "Channel not found")
        profile = await conn.fetchrow("SELECT * FROM channel_profiles WHERE channel_id=$1", channel_id)
        pillars = await conn.fetch("SELECT * FROM channel_pillars WHERE channel_id=$1 ORDER BY position", channel_id)
        rules = await conn.fetch("SELECT * FROM channel_topic_rules WHERE channel_id=$1", channel_id)
    return {
        "data": {
            "channel":     dict(ch),
            "profile":     dict(profile) if profile else None,
            "pillars":     [dict(p) for p in pillars],
            "topic_rules": [dict(r) for r in rules],
        }
    }


class TriggerIn(BaseModel):
    content_mode: str | None = None
    topic_hint: str | None = None
    topic_candidates: list[str] = Field(default_factory=list)
    max_cost_usd: float | None = None


@router.post("/{channel_id}/trigger")
async def trigger_channel(
    channel_id: str,
    body: TriggerIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    """Proxy trigger to the legacy BFF which handles Temporal start + budget checks."""
    import httpx
    token = request.headers.get("Authorization", "")
    bff_base = "http://localhost:8020"
    payload: dict = {}
    if body.content_mode:
        payload["content_mode"] = body.content_mode
    if body.topic_hint:
        payload["topic_candidates"] = [body.topic_hint]
    if body.topic_candidates:
        payload["topic_candidates"] = body.topic_candidates
    if body.max_cost_usd is not None:
        payload["max_cost_usd"] = body.max_cost_usd
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{bff_base}/api/channels/{channel_id}/trigger",
                headers={"Authorization": token},
                json=payload,
            )
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.json().get("detail", "Trigger failed"))
        result = resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(502, f"Legacy BFF unreachable: {exc}") from exc
    await audit(actor=actor, action="channel.trigger", target_type="channel",
                target_id=channel_id, after=payload, request=request)
    return result


# Job control (pause / resume / stop)

@router.post("/{channel_id}/jobs/{content_id}/pause")
async def pause_job(
    channel_id: str, content_id: str, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    import httpx
    token = request.headers.get("Authorization", "")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"http://localhost:8020/api/channels/{channel_id}/jobs/{content_id}/pause",
            headers={"Authorization": token},
        )
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.json().get("detail", "Pause failed"))
    await audit(actor=actor, action="job.pause", target_type="video",
                target_id=content_id, request=request)
    return resp.json()


@router.post("/{channel_id}/jobs/{content_id}/resume")
async def resume_job(
    channel_id: str, content_id: str, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    import httpx
    token = request.headers.get("Authorization", "")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"http://localhost:8020/api/channels/{channel_id}/jobs/{content_id}/resume",
            headers={"Authorization": token},
        )
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.json().get("detail", "Resume failed"))
    await audit(actor=actor, action="job.resume", target_type="video",
                target_id=content_id, request=request)
    return resp.json()


@router.post("/{channel_id}/jobs/{content_id}/stop")
async def stop_job(
    channel_id: str, content_id: str, request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    import httpx
    token = request.headers.get("Authorization", "")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"http://localhost:8020/api/channels/{channel_id}/jobs/{content_id}/stop",
            headers={"Authorization": token},
        )
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.json().get("detail", "Stop failed"))
    await audit(actor=actor, action="job.stop", target_type="video",
                target_id=content_id, request=request)
    return resp.json()


def _is_async(fn):
    import asyncio as _a
    return _a.iscoroutinefunction(fn)


def _heuristic_suggest(field: str, ctx: dict) -> str:
    niche = ctx.get("niche", "")
    name = ctx.get("channel_name", "")
    table = {
        "mission":           f"Make {niche} feel obvious to anyone who watches one of our videos.",
        "vision":            f"Be the most-bingeable {niche} channel for curious beginners.",
        "brand_personality": "Warm, sharply curious, occasionally playful.",
        "tone":              "Direct, friendly, confident without being preachy.",
        "narration_style":   "Conversational, fast-cut, micro-pauses for emphasis.",
        "music_style":       "Cinematic minimal pads with subtle percussion.",
        "humor_style":       "Dry observational, never cynical.",
        "thumbnail_style":   "Bold subject, single contrast color, 3-word headline.",
        "pacing_style":      "Fast (1.6 cuts/sec), slow on key facts.",
        "lut_preference":    "Cinematic teal-orange, mild contrast.",
        "transition_preference": "Whip-pan + match-cut; avoid stock fades.",
        "typography_preference": "Inter / Geist; bold weights on emphasis words.",
    }
    return table.get(field, f"Suggested value for {field} on {name or niche}")
