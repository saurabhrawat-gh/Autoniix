"""Brand Kit resolver (AE-357 / Library Sprint).

The Library introduced ``dam_brand_kits`` rows (logo asset IDs, palette
JSONB, font asset IDs, LUT asset ID, intro/outro, motion presets) but
nothing in the production pipeline reads them — Remotion compositions
have been driven by hard-coded registries and the per-channel
``brand_config`` JSONB blob.

This module is the *thin* read-only bridge between the two:

* :func:`resolve_brand_kit_for_channel(channel_id)` — returns a dict
  ready to be injected into a Remotion render request. It does ONE join
  (``channels`` → ``dam_brand_kits``) and ONE pass over ``dam_assets`` to
  expand asset ids into signed URLs. Falls back gracefully when the
  channel has no kit bound (returning ``{}`` so the legacy
  ``brand_config`` path stays in effect).

* Public surface is intentionally small so swapping the resolver later
  for a richer / cached variant is a one-file change.

Schema reference:

* ``channels.brand_kit_id`` — nullable FK added by the 202606131900
  migration. NULL = "use legacy brand_config".
* ``dam_brand_kits`` — logo_asset_ids[], palette JSONB, font_asset_ids[],
  lut_asset_id, intro_asset_id, outro_asset_id, voice_sample_id,
  motion_presets JSONB.
"""
from __future__ import annotations

import json
from typing import Any

import structlog

from src.db import get_pool

logger = structlog.get_logger()


def _parse_jsonb(value: Any) -> Any:
    """Return ``value`` as a Python object whether it was JSONB or text."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


async def _asset_url(pool: Any, asset_id: int | None) -> str | None:
    """Translate a dam_assets.id into a presigned URL, or None if missing."""
    if asset_id is None:
        return None
    row = await pool.fetchrow(
        "SELECT storage_key FROM dam_assets WHERE id = $1 AND deleted_at IS NULL",
        asset_id,
    )
    if row is None or not row["storage_key"]:
        return None
    try:
        from src.providers.registry import ProviderRegistry

        storage = ProviderRegistry.get("storage")
        return await storage.get_signed_url(row["storage_key"])  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("brand_kit.signed_url_failed", asset_id=asset_id, error=str(exc))
        return None


async def _asset_urls(pool: Any, asset_ids: list[int] | None) -> list[str]:
    if not asset_ids:
        return []
    urls: list[str] = []
    for aid in asset_ids:
        u = await _asset_url(pool, aid)
        if u:
            urls.append(u)
    return urls


async def resolve_brand_kit_for_channel(channel_id: str) -> dict:
    """Return the resolved brand kit for a channel, ready for Remotion.

    Output shape (all keys optional):

    .. code-block:: python

        {
          "kit_id": 17,
          "name": "Beast Mode v2",
          "palette": {"primary": "#fff", "secondary": "#000", …},
          "logos": ["https://…/logo_a.png", "https://…/logo_b.svg"],
          "fonts": ["https://…/Inter.woff2", …],
          "lut":   "https://…/cinematic.cube",
          "intro": "https://…/intro.mp4",
          "outro": "https://…/outro.mp4",
          "voice_sample": "https://…/sample.wav",
          "motion_presets": {…},
        }

    When the channel has no kit bound, returns ``{}`` so the caller
    can keep the legacy ``brand_config`` path.

    Never raises. DB / storage failures degrade silently to ``{}``.
    """
    pool = await get_pool()
    try:
        row = await pool.fetchrow(
            """
            SELECT k.id              AS kit_id,
                   k.name,
                   k.palette,
                   k.logo_asset_ids,
                   k.font_asset_ids,
                   k.lut_asset_id,
                   k.intro_asset_id,
                   k.outro_asset_id,
                   k.voice_sample_id,
                   k.motion_presets
              FROM channels c
              JOIN dam_brand_kits k ON k.id = c.brand_kit_id
             WHERE c.channel_id = $1
            """,
            channel_id,
        )
    except Exception as exc:
        logger.warning("brand_kit.lookup_failed", channel_id=channel_id, error=str(exc))
        return {}
    if row is None:
        return {}

    return {
        "kit_id": row["kit_id"],
        "name": row["name"],
        "palette": _parse_jsonb(row["palette"]) or {},
        "logos": await _asset_urls(pool, row["logo_asset_ids"]),
        "fonts": await _asset_urls(pool, row["font_asset_ids"]),
        "lut": await _asset_url(pool, row["lut_asset_id"]),
        "intro": await _asset_url(pool, row["intro_asset_id"]),
        "outro": await _asset_url(pool, row["outro_asset_id"]),
        "voice_sample": await _asset_url(pool, row["voice_sample_id"]),
        "motion_presets": _parse_jsonb(row["motion_presets"]) or {},
    }


async def bind_channel_brand_kit(channel_id: str, kit_id: int | None) -> bool:
    """Set or clear ``channels.brand_kit_id``. Returns True if a row was updated."""
    pool = await get_pool()
    if kit_id is not None:
        exists = await pool.fetchval(
            "SELECT 1 FROM dam_brand_kits WHERE id = $1", kit_id
        )
        if not exists:
            raise ValueError(f"unknown brand kit id={kit_id}")
    result = await pool.execute(
        "UPDATE channels SET brand_kit_id = $2, updated_at = now() WHERE channel_id = $1",
        channel_id,
        kit_id,
    )
    # asyncpg returns 'UPDATE n' — extract the integer.
    try:
        return int(str(result).rsplit(" ", 1)[-1]) > 0
    except Exception:
        return True
