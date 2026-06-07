"""Channel finishing settings API (AE-296).

Endpoints (mounted at /api/v2):
    GET  /channels/{channel_id}/settings/finishing   read config   (any member)
    PUT  /channels/{channel_id}/settings/finishing   update config (owner/member)
    GET  /finishing/presets                          list LUT presets (no auth)

Data foundation for Epic AE-293 (Professional Finishing Pipeline). Both Phase 1A
(ffmpeg) and Phase 1B (DaVinci Resolve) read ``channel_finishing_config``.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from src.db import get_pool
from src.services.finishing.lut_registry import (
    PRESET_KEYS,
    all_presets_api,
    is_valid_preset,
)

from ._deps import Principal, audit, principal_dep, require_role

logger = structlog.get_logger()

router = APIRouter()

# Columns returned by GET / accepted (subset) by PUT.
_CONFIG_COLUMNS = (
    "channel_id",
    "require_resolve_finish",
    "color_grade_preset",
    "audio_denoise",
    "audio_eq",
    "audio_compress",
    "audio_music_duck",
    "audio_loudness_lufs",
    "audio_true_peak_dbtps",
    "output_prores_archive",
    "updated_at",
)

# Editable fields (everything except the PK + updated_at).
_EDITABLE = (
    "require_resolve_finish",
    "color_grade_preset",
    "audio_denoise",
    "audio_eq",
    "audio_compress",
    "audio_music_duck",
    "audio_loudness_lufs",
    "audio_true_peak_dbtps",
    "output_prores_archive",
)

LOUDNESS_MIN, LOUDNESS_MAX = -24.0, -9.0
TRUE_PEAK_MIN, TRUE_PEAK_MAX = -6.0, -0.1


class FinishingConfigUpdate(BaseModel):
    """All fields optional — PUT applies partial (PATCH-style) updates."""

    require_resolve_finish: bool | None = None
    color_grade_preset: str | None = None
    audio_denoise: bool | None = None
    audio_eq: bool | None = None
    audio_compress: bool | None = None
    audio_music_duck: bool | None = None
    audio_loudness_lufs: float | None = None
    audio_true_peak_dbtps: float | None = None
    output_prores_archive: bool | None = None

    @field_validator("color_grade_preset")
    @classmethod
    def _valid_preset(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not is_valid_preset(v):
            raise ValueError(
                f"unrecognised preset: {v}, valid values: {list(PRESET_KEYS)}"
            )
        return v

    @field_validator("audio_loudness_lufs")
    @classmethod
    def _valid_loudness(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not (LOUDNESS_MIN <= v <= LOUDNESS_MAX):
            raise ValueError(
                f"audio_loudness_lufs must be between {LOUDNESS_MIN} and {LOUDNESS_MAX} LUFS"
            )
        return v

    @field_validator("audio_true_peak_dbtps")
    @classmethod
    def _valid_true_peak(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not (TRUE_PEAK_MIN <= v <= TRUE_PEAK_MAX):
            raise ValueError(
                f"audio_true_peak_dbtps must be between {TRUE_PEAK_MIN} and {TRUE_PEAK_MAX} dBTP"
            )
        return v


def _serialise(row) -> dict:
    out = dict(row)
    # Decimals → float for JSON; timestamps → ISO.
    for k in ("audio_loudness_lufs", "audio_true_peak_dbtps"):
        if out.get(k) is not None:
            out[k] = float(out[k])
    if out.get("updated_at") is not None:
        out["updated_at"] = out["updated_at"].isoformat()
    return out


async def _channel_exists(pool, channel_id: str) -> bool:
    val = await pool.fetchval(
        "SELECT 1 FROM channels WHERE channel_id = $1", channel_id
    )
    return bool(val)


async def _get_or_create_config(pool, channel_id: str):
    row = await pool.fetchrow(
        f"SELECT {', '.join(_CONFIG_COLUMNS)} FROM channel_finishing_config "
        "WHERE channel_id = $1",
        channel_id,
    )
    if row is not None:
        return row
    # No row yet (channel created after the seed migration) — create the default.
    await pool.execute(
        "INSERT INTO channel_finishing_config (channel_id) VALUES ($1) "
        "ON CONFLICT (channel_id) DO NOTHING",
        channel_id,
    )
    return await pool.fetchrow(
        f"SELECT {', '.join(_CONFIG_COLUMNS)} FROM channel_finishing_config "
        "WHERE channel_id = $1",
        channel_id,
    )


@router.get("/channels/{channel_id}/settings/finishing")
async def get_finishing_config(
    channel_id: str,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    if not await _channel_exists(pool, channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")
    row = await _get_or_create_config(pool, channel_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Finishing config not found")
    return _serialise(row)


@router.put("/channels/{channel_id}/settings/finishing")
async def update_finishing_config(
    channel_id: str,
    body: FinishingConfigUpdate,
    request: Request,
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    if not await _channel_exists(pool, channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")

    updates = {
        k: v
        for k, v in body.model_dump(exclude_unset=True).items()
        if k in _EDITABLE and v is not None
    }

    before = _serialise(await _get_or_create_config(pool, channel_id))

    if updates:
        set_parts = [f"{col} = ${i + 2}" for i, col in enumerate(updates)]
        set_parts.append("updated_at = NOW()")
        await pool.execute(
            f"UPDATE channel_finishing_config SET {', '.join(set_parts)} "
            "WHERE channel_id = $1",
            channel_id,
            *updates.values(),
        )

    after_row = await _get_or_create_config(pool, channel_id)
    after = _serialise(after_row)

    await audit(
        actor=actor,
        action="channel.finishing.update",
        target_type="channel",
        target_id=channel_id,
        before=before,
        after=after,
        request=request,
    )
    logger.info("finishing.config_updated", channel_id=channel_id,
                fields=list(updates.keys()))
    return after


@router.get("/finishing/presets")
async def list_finishing_presets():
    """Public — used by the dashboard preset picker. No auth required."""
    return {"presets": all_presets_api()}
