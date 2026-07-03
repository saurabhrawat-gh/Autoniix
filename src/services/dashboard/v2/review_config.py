"""Channel review-gate configuration API (AE-229).

Endpoints (mounted at /api/v2 via channels prefix):
    GET  /channels/{channel_id}/settings/review   read config   (any member)
    PUT  /channels/{channel_id}/settings/review   update config (owner/member)

Stores per-channel review gate config in channels.review_config JSONB.
Part of Epic AE-226 (Pipeline Review & Approval Gates).
"""
from __future__ import annotations

import json
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.db import get_pool

from ._deps import Principal, audit, principal_dep, require_role

logger = structlog.get_logger()

router = APIRouter()

_GATE_KEYS = frozenset({
    "research_data",
    "brand_alignment_report",
    "topic_title",
    "story_script",
    "script_voice_data",
    "script_assets_data",
    "script_direction_data",
    "voice_track",
    "scene_images",
    "remotion_v3_json",
    "metadata",
    "thumbnail",
    "final_video",
})

_PROFILES = frozenset({"hands_off", "quick", "standard", "full_control", "custom"})

_PRESET_GATES: dict[str, set[str]] = {
    "hands_off":    set(),
    "quick":        {"story_script", "final_video"},
    "standard":     {"topic_title", "story_script", "metadata", "thumbnail", "final_video"},
    "full_control": set(_GATE_KEYS),
    "custom":       set(),
}


def _gates_for_profile(profile: str, custom_gates: dict[str, bool] | None) -> dict[str, bool]:
    """Return a full gate dict for the given profile."""
    if profile == "custom" and custom_gates is not None:
        on = {k: bool(v) for k, v in custom_gates.items() if k in _GATE_KEYS}
    else:
        on = {k: True for k in _PRESET_GATES.get(profile, set())}
    return {k: on.get(k, False) for k in sorted(_GATE_KEYS)}


class ReviewConfigUpdate(BaseModel):
    profile: str
    gates: dict[str, bool] | None = None

    model_config = {"extra": "forbid"}

    def validate_profile(self) -> None:
        if self.profile not in _PROFILES:
            raise ValueError(f"profile must be one of {sorted(_PROFILES)}")
        if self.profile == "custom" and not self.gates:
            raise ValueError("gates must be provided when profile is 'custom'")
        if self.gates:
            bad = set(self.gates) - _GATE_KEYS
            if bad:
                raise ValueError(f"Unknown gate keys: {sorted(bad)}")


@router.get("/channels/{channel_id}/settings/review")
async def get_review_config(
    channel_id: str,
    actor: Principal = Depends(principal_dep),
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT review_config FROM channels WHERE channel_id=$1",
            channel_id,
        )
    if not row:
        raise HTTPException(404, "Channel not found")
    cfg = row["review_config"] or {}
    return {
        "channel_id": channel_id,
        "profile": cfg.get("profile", "hands_off"),
        "gates": cfg.get("gates", _gates_for_profile("hands_off", None)),
    }


@router.put("/channels/{channel_id}/settings/review")
async def put_review_config(
    channel_id: str,
    body: ReviewConfigUpdate,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
) -> dict:
    try:
        body.validate_profile()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    gates = _gates_for_profile(body.profile, body.gates)
    new_cfg = {"profile": body.profile, "gates": gates}

    pool = await get_pool()
    async with pool.acquire() as conn:
        updated = await conn.fetchrow(
            """UPDATE channels
                  SET review_config = $1::jsonb, updated_at = NOW()
                WHERE channel_id = $2
            RETURNING channel_id""",
            json.dumps(new_cfg),
            channel_id,
        )
    if not updated:
        raise HTTPException(404, "Channel not found")

    await audit(
        actor=actor,
        action="review_config.updated",
        target_type="channel",
        target_id=channel_id,
        after=new_cfg,
        request=request,
    )
    logger.info("review_config.updated", channel_id=channel_id, profile=body.profile)
    return {"channel_id": channel_id, "profile": body.profile, "gates": gates}
