"""ffmpeg finishing pipeline (AE-294, Phase 1A).

Pure command builders (unit-testable without ffmpeg) plus thin async subprocess
runners. The pipeline applies a 3D LUT colour grade to the video track and a full
mastering chain to the audio track:

    denoise (afftdn) → EQ (low-mid cut) → compress (acompressor)
        → loudness normalise (two-pass loudnorm, default -14 LUFS)
        → true-peak limit (alimiter, default -1.5 dBTP)

Loudness uses ffmpeg's two-pass ``loudnorm`` method: pass 1 measures integrated
loudness / true peak / LRA as JSON, pass 2 applies the linear corrective gain.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


class FinishingError(RuntimeError):
    """Raised when an ffmpeg finishing step fails."""


@dataclass
class FinishConfig:
    """Subset of channel_finishing_config that drives the ffmpeg pipeline."""

    color_grade_preset: str = "cinematic"
    audio_denoise: bool = True
    audio_eq: bool = True
    audio_compress: bool = True
    audio_music_duck: bool = True
    audio_loudness_lufs: float = -14.0
    audio_true_peak_dbtps: float = -1.5

    @classmethod
    def from_row(cls, row: dict) -> "FinishConfig":
        return cls(
            color_grade_preset=row.get("color_grade_preset", "cinematic"),
            audio_denoise=bool(row.get("audio_denoise", True)),
            audio_eq=bool(row.get("audio_eq", True)),
            audio_compress=bool(row.get("audio_compress", True)),
            audio_music_duck=bool(row.get("audio_music_duck", True)),
            audio_loudness_lufs=float(row.get("audio_loudness_lufs", -14.0)),
            audio_true_peak_dbtps=float(row.get("audio_true_peak_dbtps", -1.5)),
        )


@dataclass
class LoudnormStats:
    """Measured values from loudnorm pass 1."""

    input_i: str
    input_tp: str
    input_lra: str
    input_thresh: str
    target_offset: str

    @classmethod
    def from_json(cls, data: dict) -> "LoudnormStats":
        return cls(
            input_i=str(data.get("input_i", "-24.0")),
            input_tp=str(data.get("input_tp", "-2.0")),
            input_lra=str(data.get("input_lra", "7.0")),
            input_thresh=str(data.get("input_thresh", "-34.0")),
            target_offset=str(data.get("target_offset", "0.0")),
        )


def _escape_lut_path(path: str) -> str:
    """Escape a filesystem path for use inside an ffmpeg filtergraph."""
    return path.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


def build_video_filter(lut_path: str) -> str:
    """3D LUT colour grade via the ``lut3d`` filter."""
    return f"lut3d=file='{_escape_lut_path(lut_path)}'"


def build_audio_filter(cfg: FinishConfig, measured: LoudnormStats | None = None) -> str:
    """Assemble the mastering audio filter chain.

    When *measured* is provided, ``loudnorm`` runs in linear two-pass mode using
    the measured values; otherwise it runs single-pass (used only as a fallback).
    """
    stages: list[str] = []

    if cfg.audio_denoise:
        stages.append("afftdn=nr=12:nf=-25")
    if cfg.audio_eq:
        stages.append("equalizer=f=200:width_type=o:width=2:g=-3")
    if cfg.audio_compress:
        stages.append("acompressor=threshold=-18dB:ratio=3:attack=5:release=50")

    loudness = f"loudnorm=I={cfg.audio_loudness_lufs}:TP={cfg.audio_true_peak_dbtps}:LRA=11"
    if measured is not None:
        loudness += (
            f":measured_I={measured.input_i}"
            f":measured_TP={measured.input_tp}"
            f":measured_LRA={measured.input_lra}"
            f":measured_thresh={measured.input_thresh}"
            f":offset={measured.target_offset}"
            ":linear=true:print_format=summary"
        )
    stages.append(loudness)

    limit = abs(cfg.audio_true_peak_dbtps)
    stages.append(f"alimiter=level_in=1:level_out=1:limit=-{limit}dB")

    return ",".join(stages)


def build_measure_command(input_path: str, cfg: FinishConfig) -> list[str]:
    """ffmpeg command for loudnorm pass 1 (measure only, JSON to stderr)."""
    measure_filter = f"loudnorm=I={cfg.audio_loudness_lufs}:TP={cfg.audio_true_peak_dbtps}:LRA=11:print_format=json"
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        input_path,
        "-af",
        measure_filter,
        "-f",
        "null",
        "-",
    ]


def build_finish_command(
    input_path: str,
    output_path: str,
    lut_path: str,
    cfg: FinishConfig,
    measured: LoudnormStats | None = None,
) -> list[str]:
    """ffmpeg command for the full finishing pass (LUT + audio master → H.264)."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        input_path,
        "-vf",
        build_video_filter(lut_path),
        "-af",
        build_audio_filter(cfg, measured),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "256k",
        "-movflags",
        "+faststart",
        output_path,
    ]


def build_prores_command(
    input_path: str, output_path: str, lut_path: str, cfg: FinishConfig, measured: LoudnormStats | None = None
) -> list[str]:
    """ffmpeg command for a ProRes 4444 archival master (.mov)."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        input_path,
        "-vf",
        build_video_filter(lut_path),
        "-af",
        build_audio_filter(cfg, measured),
        "-c:v",
        "prores_ks",
        "-profile:v",
        "4",
        "-pix_fmt",
        "yuva444p10le",
        "-c:a",
        "pcm_s24le",
        output_path,
    ]


def parse_loudnorm_json(stderr: str) -> LoudnormStats:
    """Extract the JSON block ffmpeg's loudnorm prints to stderr."""
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise FinishingError("loudnorm: no JSON block found in ffmpeg output")
    try:
        data = json.loads(stderr[start : end + 1])
    except json.JSONDecodeError as exc:
        raise FinishingError(f"loudnorm: invalid JSON ({exc})") from exc
    return LoudnormStats.from_json(data)


async def _run(cmd: list[str]) -> tuple[int, str]:
    """Run a command; return (returncode, stderr_text)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    return proc.returncode or 0, (stderr or b"").decode("utf-8", "replace")


async def measure_loudnorm(input_path: str, cfg: FinishConfig) -> LoudnormStats:
    rc, stderr = await _run(build_measure_command(input_path, cfg))
    if rc != 0:
        raise FinishingError(f"loudnorm measure failed (rc={rc}): {stderr[-500:]}")
    return parse_loudnorm_json(stderr)


async def run_finishing(
    input_path: str,
    output_path: str,
    lut_path: str,
    cfg: FinishConfig,
) -> None:
    """Two-pass finishing: measure loudness, then apply LUT + mastered audio."""
    measured = await measure_loudnorm(input_path, cfg)
    rc, stderr = await _run(build_finish_command(input_path, output_path, lut_path, cfg, measured))
    if rc != 0:
        raise FinishingError(f"finishing encode failed (rc={rc}): {stderr[-500:]}")
    logger.info("finishing.encode_done", output=output_path, preset=cfg.color_grade_preset)


async def run_prores(
    input_path: str,
    output_path: str,
    lut_path: str,
    cfg: FinishConfig,
) -> None:
    measured = await measure_loudnorm(input_path, cfg)
    rc, stderr = await _run(build_prores_command(input_path, output_path, lut_path, cfg, measured))
    if rc != 0:
        raise FinishingError(f"prores encode failed (rc={rc}): {stderr[-500:]}")
    logger.info("finishing.prores_done", output=output_path)
