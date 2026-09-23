"""Temporal activity for Phase 1A finishing (AE-294).

Inserted in ``VideoProductionWorkflow`` between ``assembly_activity`` and
``delivery_activity``. Reads the channel's ``channel_finishing_config``, applies
the LUT colour grade + audio mastering chain via ffmpeg, writes the finished MP4
back to MinIO, and (optionally) archives a ProRes master.

Fallback: ffmpeg failures are retried up to ``MAX_FINISH_ATTEMPTS`` times. When
exhausted and ``require_resolve_finish`` is False, the activity returns
``skipped=True`` so the workflow delivers the raw render and flags
``finishing_skipped=true``. When ``require_resolve_finish`` is True it re-raises,
letting Temporal retry per the workflow's retry policy.
"""

from __future__ import annotations

import os
import tempfile

import httpx
import structlog
from temporalio import activity

from core.db import get_pool
from services_api.finishing import lut_registry
from services_api.finishing.ffmpeg_finisher import (
    FinishConfig,
    FinishingError,
    run_finishing,
    run_prores,
)

logger = structlog.get_logger()

MAX_FINISH_ATTEMPTS = 3

_DEFAULT_CONFIG = {
    "require_resolve_finish": False,
    "color_grade_preset": lut_registry.DEFAULT_PRESET,
    "audio_denoise": True,
    "audio_eq": True,
    "audio_compress": True,
    "audio_music_duck": True,
    "audio_loudness_lufs": -14.0,
    "audio_true_peak_dbtps": -1.5,
    "output_prores_archive": False,
}


async def _load_config(channel_id: str) -> dict:
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT require_resolve_finish, color_grade_preset, audio_denoise, "
            "audio_eq, audio_compress, audio_music_duck, audio_loudness_lufs, "
            "audio_true_peak_dbtps, output_prores_archive "
            "FROM channel_finishing_config WHERE channel_id = $1",
            channel_id,
        )
        if row:
            return dict(row)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("finishing.config_load_failed", channel_id=channel_id, error=str(exc))
    return dict(_DEFAULT_CONFIG)


def _storage():
    from providers.registry import ProviderRegistry

    return ProviderRegistry.get("storage")


async def _download_source(video_url: str, dest_path: str) -> None:
    """Fetch the raw render to a local path (http(s) URL or s3:// key)."""
    if video_url.startswith("s3://"):
        key = video_url.split("/", 3)[-1]
        data = await _storage().download(key)
        with open(dest_path, "wb") as fh:
            fh.write(data)
        return
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.get(video_url)
        resp.raise_for_status()
        with open(dest_path, "wb") as fh:
            fh.write(resp.content)


async def _resolve_lut(preset_key: str, dest_path: str) -> str:
    """Download the preset .cube from MinIO; generate locally if unavailable."""
    cube_key = lut_registry.cube_key_for(preset_key)
    try:
        data = await _storage().download(cube_key)
        with open(dest_path, "wb") as fh:
            fh.write(data)
        return dest_path
    except Exception as exc:
        logger.warning("finishing.lut_download_failed_generating", preset=preset_key, key=cube_key, error=str(exc))
        from tools.seeds.lut_presets.generate_luts import write_cube

        write_cube(preset_key, dest_path)
        return dest_path


async def _upload_finished(local_path: str, content_id: str) -> str:
    from providers.storage.base import StorageUpload

    with open(local_path, "rb") as fh:
        data = fh.read()
    key = f"videos/finished/{content_id}.mp4"
    result = await _storage().upload(StorageUpload(key=key, data=data, content_type="video/mp4"))
    return result.url


async def _upload_prores(local_path: str, content_id: str) -> str:
    from providers.storage.base import StorageUpload

    with open(local_path, "rb") as fh:
        data = fh.read()
    key = f"videos/prores/{content_id}/master.mov"
    await _storage().upload(StorageUpload(key=key, data=data, content_type="video/quicktime"))
    return key


async def _mark_db(content_id: str, *, preset: str | None, prores_path: str | None, skipped: bool) -> None:
    try:
        pool = await get_pool()
        await pool.execute(
            "UPDATE videos SET finishing_skipped = $1, finishing_preset_used = $2, "
            "prores_path = $3, updated_at = NOW() WHERE content_id = $4",
            skipped,
            preset,
            prores_path,
            content_id,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("finishing.db_update_failed", content_id=content_id, error=str(exc))


@activity.defn(name="finishing_activity")
async def finishing_activity(params: dict) -> dict:
    """Apply ffmpeg LUT + audio mastering to a rendered video.

    params: content_id, channel_id, video_url, [output_prores_archive override].
    Returns {status, data: {finished_url, prores_path, skipped, preset_used}}.
    """
    content_id = params.get("content_id", "")
    channel_id = params.get("channel_id", "")
    video_url = params.get("video_url", "")

    logger.info("activity.finishing.started", content_id=content_id, channel_id=channel_id)

    if not video_url:
        logger.warning("finishing.no_video_url", content_id=content_id)
        await _mark_db(content_id, preset=None, prores_path=None, skipped=True)
        return {
            "status": "skipped",
            "data": {"finished_url": "", "prores_path": None, "skipped": True, "preset_used": None},
        }

    cfg_row = await _load_config(channel_id)
    cfg = FinishConfig.from_row(cfg_row)
    require_resolve = bool(cfg_row.get("require_resolve_finish", False))
    want_prores = bool(cfg_row.get("output_prores_archive", False))

    tmpdir = tempfile.mkdtemp(prefix=f"finish_{content_id}_")
    raw_path = os.path.join(tmpdir, "raw.mp4")
    finished_path = os.path.join(tmpdir, "finished.mp4")
    lut_path = os.path.join(tmpdir, f"{cfg.color_grade_preset}.cube")
    prores_local = os.path.join(tmpdir, "master.mov")

    try:
        await _download_source(video_url, raw_path)
        await _resolve_lut(cfg.color_grade_preset, lut_path)

        last_err: Exception | None = None
        for attempt in range(1, MAX_FINISH_ATTEMPTS + 1):
            try:
                activity.heartbeat(f"finishing attempt {attempt}")
            except Exception:
                pass
            try:
                await run_finishing(raw_path, finished_path, lut_path, cfg)
                last_err = None
                break
            except FinishingError as exc:
                last_err = exc
                logger.warning("finishing.attempt_failed", content_id=content_id, attempt=attempt, error=str(exc))

        if last_err is not None:
            if require_resolve:
                raise last_err
            logger.warning("finishing.skipped_after_retries", content_id=content_id)
            await _mark_db(content_id, preset=None, prores_path=None, skipped=True)
            return {
                "status": "skipped",
                "data": {"finished_url": "", "prores_path": None, "skipped": True, "preset_used": None},
            }

        finished_url = await _upload_finished(finished_path, content_id)

        prores_path: str | None = None
        if want_prores:
            try:
                await run_prores(raw_path, prores_local, lut_path, cfg)
                prores_path = await _upload_prores(prores_local, content_id)
            except FinishingError as exc:
                logger.warning("finishing.prores_failed", content_id=content_id, error=str(exc))

        await _mark_db(content_id, preset=cfg.color_grade_preset, prores_path=prores_path, skipped=False)

        logger.info(
            "activity.finishing.completed",
            content_id=content_id,
            preset=cfg.color_grade_preset,
            prores=bool(prores_path),
        )
        return {
            "status": "success",
            "data": {
                "finished_url": finished_url,
                "prores_path": prores_path,
                "skipped": False,
                "preset_used": cfg.color_grade_preset,
            },
        }
    finally:
        try:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
