"""ffprobe wrapper — measure real audio duration instead of estimating.

The current voice service estimates duration as
``word_count / 150 * 60 / speed``. That's off by 5–15% per sentence,
which accumulates to seconds of timeline drift across a 45-second short.
That drift is why captions and scene cuts land on the wrong frame.

This module wraps ``ffprobe`` (bundled with the same ffmpeg install
Remotion/moviepy already require) to return millisecond-accurate media
info from an in-memory byte buffer (typical: MP3 returned by Inworld TTS)
or a URL.

Usage::

    from media.ffprobe import probe_audio_duration_seconds

    audio_bytes = tts_result.audio_bytes
    duration_s = await probe_audio_duration_seconds(audio_bytes)
    # duration_s is now measured, not estimated.

If ffprobe is not available (containers without ffmpeg) callers get a
``FfprobeUnavailable`` and can fall back to the estimator upstream.
Every fallback is logged and counted so we can spot drift issues later.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger()


class FfprobeUnavailable(RuntimeError):
    """ffprobe binary not found on PATH."""


class FfprobeFailed(RuntimeError):
    """ffprobe ran but returned non-zero or unparseable output."""


@dataclass(frozen=True)
class ProbeResult:
    """Structured ffprobe result. Only common fields — extend as needed."""

    duration_s: float
    bit_rate: int | None
    sample_rate: int | None
    channels: int | None
    codec_name: str | None
    format_name: str | None
    raw: dict[str, Any]


_FFPROBE_BIN: str | None = None


def _resolve_bin() -> str:
    global _FFPROBE_BIN
    if _FFPROBE_BIN is None:
        found = shutil.which("ffprobe")
        if not found:
            raise FfprobeUnavailable("ffprobe binary not found on PATH")
        _FFPROBE_BIN = found
    return _FFPROBE_BIN


async def probe_media(
    data: bytes | str,
    *,
    timeout_s: float = 30.0,
) -> ProbeResult:
    """Run ffprobe against in-memory bytes or a path/URL.

    - If ``data`` is ``bytes``, streams via stdin.
    - If ``data`` is ``str``, treated as a path or URL (ffprobe supports HTTP).

    Raises :class:`FfprobeUnavailable` if the binary isn't installed
    and :class:`FfprobeFailed` on non-zero exit or unparseable JSON.
    """
    bin_path = _resolve_bin()
    args = [
        bin_path,
        "-v",
        "error",
        "-hide_banner",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
    ]
    if isinstance(data, bytes):
        args.append("-")
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(input=data), timeout=timeout_s)
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise FfprobeFailed(f"ffprobe timed out after {timeout_s}s") from exc
    else:
        args.append(data)
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise FfprobeFailed(f"ffprobe timed out after {timeout_s}s") from exc

    if proc.returncode != 0:
        raise FfprobeFailed(f"ffprobe exited {proc.returncode}: {stderr.decode('utf-8', errors='replace')[:500]}")
    try:
        parsed = json.loads(stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise FfprobeFailed(f"ffprobe output was not JSON: {exc}") from exc

    fmt = parsed.get("format") or {}
    streams = parsed.get("streams") or []
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    astream = audio_streams[0] if audio_streams else (streams[0] if streams else {})

    try:
        duration_s = float(fmt.get("duration", 0) or astream.get("duration", 0) or 0)
    except (TypeError, ValueError):
        duration_s = 0.0
    try:
        bit_rate = int(fmt.get("bit_rate")) if fmt.get("bit_rate") else None
    except (TypeError, ValueError):
        bit_rate = None
    try:
        sample_rate = int(astream.get("sample_rate")) if astream.get("sample_rate") else None
    except (TypeError, ValueError):
        sample_rate = None

    return ProbeResult(
        duration_s=duration_s,
        bit_rate=bit_rate,
        sample_rate=sample_rate,
        channels=astream.get("channels"),
        codec_name=astream.get("codec_name"),
        format_name=fmt.get("format_name"),
        raw=parsed,
    )


async def probe_audio_duration_seconds(
    data: bytes | str,
    *,
    fallback_s: float | None = None,
    timeout_s: float = 30.0,
) -> float:
    """Convenience: return only duration in seconds.

    Falls back to ``fallback_s`` (typically the estimate the caller
    already had) on any failure. Logs the fallback so we can catch
    stubborn probe issues later.
    """
    try:
        result = await probe_media(data, timeout_s=timeout_s)
        if result.duration_s > 0:
            return result.duration_s
        if fallback_s is not None:
            logger.warning("ffprobe.zero_duration", fallback_s=fallback_s)
            return fallback_s
        raise FfprobeFailed("duration reported as 0")
    except FfprobeUnavailable:
        if fallback_s is not None:
            logger.warning("ffprobe.unavailable", fallback_s=fallback_s)
            return fallback_s
        raise
    except FfprobeFailed as exc:
        if fallback_s is not None:
            logger.warning("ffprobe.failed", fallback_s=fallback_s, error=str(exc))
            return fallback_s
        raise
