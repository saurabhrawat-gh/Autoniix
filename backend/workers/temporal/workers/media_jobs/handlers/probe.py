"""``probe`` handler — extract basic metadata from an asset.

Currently supports images via Pillow (width / height / mode / format).
Audio / video probing requires ``ffprobe`` and is intentionally deferred
until ffmpeg is added to the worker image; in the meantime the worker
marks those as ``skipped`` via the fallback handler so the queue stays
clean.

Writes the discovered metadata back into ``dam_assets.metadata``.
"""

from __future__ import annotations

import io
from typing import Any

import structlog

from temporal_workers.media_jobs.storage import download_bytes

logger = structlog.get_logger()

KIND = "probe"


async def run(pool: Any, asset: dict, job: dict) -> dict:
    asset_kind = asset.get("kind")
    storage_key = asset.get("storage_key")
    if not storage_key:
        return {"status": "skipped", "reason": "asset has no storage_key"}

    if asset_kind == "image":
        return await _probe_image(pool, asset, storage_key)
    if asset_kind == "font":
        return {"status": "done", "result": {"probed": True, "kind": "font"}}
    if asset_kind in {"video", "audio"}:
        return {
            "status": "skipped",
            "reason": "ffprobe not installed in the worker image yet",
        }
    return {
        "status": "skipped",
        "reason": f"probe not implemented for kind={asset_kind!r}",
    }


async def _probe_image(pool: Any, asset: dict, storage_key: str) -> dict:
    data = await download_bytes(storage_key)
    if data is None:
        return {"status": "failed", "reason": "could not fetch object"}

    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover — Pillow is in requirements
        return {"status": "failed", "reason": f"Pillow unavailable: {exc!s}"}

    try:
        with Image.open(io.BytesIO(data)) as img:
            metadata = {
                "width": img.width,
                "height": img.height,
                "mode": img.mode,
                "format": (img.format or "").lower() or None,
            }
    except Exception as exc:
        return {"status": "failed", "reason": f"image probe failed: {exc!s}"}

    await pool.execute(
        """
        UPDATE dam_assets
           SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb,
               updated_at = now()
         WHERE id = $1
        """,
        asset["id"],
        _metadata_to_jsonb(metadata),
    )
    return {"status": "done", "result": metadata}


def _metadata_to_jsonb(d: dict) -> str:
    """asyncpg accepts a JSON string for a JSONB parameter cast."""
    import json

    return json.dumps(d)
