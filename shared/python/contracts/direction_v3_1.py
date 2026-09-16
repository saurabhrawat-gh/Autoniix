"""Direction Format v3.1 — Pydantic mirror of ``directionV3_1.ts``.

Mirrors the Zod schema in ``backend/media/remotion/src/schemas/directionV3_1.ts``.
Any change here must be reflected there and vice-versa. See
``/Users/saurabhrawat/.devin/plans/plan-476749920bd78127.md`` for the rationale.

Usage:

    from contracts.direction_v3_1 import DirectionV3_1, validate_timeline_density

    doc = DirectionV3_1.model_validate(payload)
    issues = validate_timeline_density(doc)
    if issues:
        logger.warning("direction.density_gaps", issues=issues)

Design notes:
- All v3.1-added fields are ``Optional`` so a v3.0 payload parses unchanged.
- ``timeline[]`` keyframes are anchor points; between them Remotion
  interpolates using the ``ease`` field. Density floor is ``MAX_KEYFRAME_GAP_MS``.
- ``captions[]`` mirror voice's ``word_alignment`` (from Inworld TTS
  ``get_word_timestamps`` or whisperx fallback).
- ``micro_beats[]`` are ≤100ms hit markers merged from voice ``emphasis_hits``
  + music ``beat_map_ms`` + asset ``cut_suggestions_ms``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

MAX_KEYFRAME_GAP_MS = 500


# ── enums ──────────────────────────────────────────────────────────────────


class EaseCurve(str, Enum):
    LINEAR = "linear"
    STEP = "step"
    CUBIC_IN = "cubic-in"
    CUBIC_OUT = "cubic-out"
    CUBIC_IN_OUT = "cubic-in-out"
    SPRING = "spring"
    ELASTIC_OUT = "elastic-out"
    BACK_OUT = "back-out"
    EXPO_OUT = "expo-out"


class MicroBeatKind(str, Enum):
    HIT = "hit"
    CUT = "cut"
    REVEAL = "reveal"
    ZOOM_PUNCH = "zoom_punch"
    FLASH = "flash"
    SFX = "sfx"


class MicroBeatSource(str, Enum):
    VOICE_EMPHASIS = "voice_emphasis"
    MUSIC_BEAT = "music_beat"
    ASSET_CUT = "asset_cut"
    NARRATIVE = "narrative"
    MANUAL = "manual"


class Aspect(str, Enum):
    WIDE = "16:9"
    VERTICAL = "9:16"
    SQUARE = "1:1"


class LayerFit(str, Enum):
    COVER = "cover"
    CONTAIN = "contain"
    FILL = "fill"


class DirectionVersion(str, Enum):
    V3_0 = "3.0"
    V3_1 = "3.1"


# ── shared primitives (v3.0 kept) ──────────────────────────────────────────


class PresetRef(BaseModel):
    model_config = ConfigDict(extra="allow")
    preset: str = Field(..., min_length=1)
    overrides: Optional[dict[str, Any]] = None


class Animation(BaseModel):
    model_config = ConfigDict(extra="allow")
    preset: str = Field(..., min_length=1)
    target: Optional[str] = None
    overrides: Optional[dict[str, Any]] = None


class SfxCue(BaseModel):
    preset: str
    at_ms: int = Field(..., ge=0)
    volume_db: Optional[float] = None


# ── v3.1 additions ─────────────────────────────────────────────────────────


class CameraState(BaseModel):
    x: float = 0.0
    y: float = 0.0
    scale: float = Field(1.0, gt=0)
    rotation: float = 0.0
    anchor: tuple[float, float] = (0.5, 0.5)


class EffectsIntensity(BaseModel):
    grade_strength: float = Field(1.0, ge=0, le=1)
    vignette: float = Field(0.0, ge=0, le=1)
    blur_px: float = Field(0.0, ge=0)
    chroma: float = Field(0.0, ge=0, le=1)
    grain: float = Field(0.0, ge=0, le=1)
    bloom: float = Field(0.0, ge=0, le=1)


class LightingState(BaseModel):
    exposure: float = 0.0
    contrast: float = Field(1.0, gt=0)
    saturation: float = Field(1.0, ge=0)
    temperature: float = 0.0
    tint: float = 0.0


class TextState(BaseModel):
    visible_word_index: int = Field(0, ge=0)
    emphasis_word_index: Optional[int] = Field(None, ge=0)
    opacity: float = Field(1.0, ge=0, le=1)
    scale: float = Field(1.0, gt=0)


class OverlayOpacity(BaseModel):
    lower_third: float = Field(0.0, ge=0, le=1)
    watermark: float = Field(1.0, ge=0, le=1)
    caption: float = Field(1.0, ge=0, le=1)
    progress_bar: float = Field(0.0, ge=0, le=1)


class TimelineKeyframe(BaseModel):
    """Anchor keyframe. ≤500ms spacing required (see `validate_timeline_density`)."""

    model_config = ConfigDict(extra="allow")
    t_ms: int = Field(..., ge=0)
    ease: EaseCurve = EaseCurve.CUBIC_IN_OUT
    camera: Optional[CameraState] = None
    effects: Optional[EffectsIntensity] = None
    lighting: Optional[LightingState] = None
    text_state: Optional[TextState] = None
    overlay_opacity: Optional[OverlayOpacity] = None
    audio_ducking_db: Optional[float] = None


class CaptionWord(BaseModel):
    """Word-level caption from voice's `word_alignment` (Inworld or whisperx)."""

    word: str
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., gt=0)
    is_emphasis: bool = False
    sentence_id: Optional[str] = None
    style_id: Optional[str] = None


class MicroBeat(BaseModel):
    """Sub-100ms hit marker. Merged from voice / music / asset sources."""

    at_ms: int = Field(..., ge=0)
    kind: MicroBeatKind
    source: MicroBeatSource
    intensity: float = Field(0.5, ge=0, le=1)
    payload: Optional[dict[str, Any]] = None


class DuckingEnvelopePoint(BaseModel):
    t_ms: int = Field(..., ge=0)
    gain_db: float


class AudioTrack(BaseModel):
    voiceover_url: Optional[HttpUrl] = None
    voiceover_start_ms: int = Field(0, ge=0)
    voiceover_gain_db: float = 0.0
    music_bed_url: Optional[HttpUrl] = None
    music_gain_db: float = -8.0
    ducking_envelope: Optional[list[DuckingEnvelopePoint]] = None
    loudness_target_lufs: float = -14.0


class LayerOpacityKeyframe(BaseModel):
    t_ms: int = Field(..., ge=0)
    opacity: float = Field(..., ge=0, le=1)


class Layer(BaseModel):
    z: int = 0
    asset_url: HttpUrl
    fit: LayerFit = LayerFit.COVER
    transform_keyframes: Optional[list[TimelineKeyframe]] = None
    opacity_keyframes: Optional[list[LayerOpacityKeyframe]] = None


# ── segment (v3.0 fields kept + v3.1 additions) ───────────────────────────


class Segment(BaseModel):
    model_config = ConfigDict(extra="allow")

    # v3.0 (unchanged)
    id: str
    start_ms: int = Field(..., ge=0)
    duration_ms: int = Field(..., gt=0)
    scene_preset: str = Field(..., min_length=1)
    scene_overrides: Optional[dict[str, Any]] = None
    animations_in: Optional[list[Animation]] = None
    animations_out: Optional[list[Animation]] = None
    effects: Optional[list[str]] = None
    overlays: Optional[list[PresetRef]] = None
    sfx: Optional[list[SfxCue]] = None
    transition_out: Optional[PresetRef] = None

    # v3.1 additions
    timeline: Optional[list[TimelineKeyframe]] = None
    captions: Optional[list[CaptionWord]] = None
    micro_beats: Optional[list[MicroBeat]] = None
    audio_track: Optional[AudioTrack] = None
    layers: Optional[list[Layer]] = None
    is_hero_moment: Optional[bool] = None


# ── top-level (v3.0 fields kept) ──────────────────────────────────────────


class Theme(BaseModel):
    primary_color: str
    accent_color: str
    background_color: str
    text_color: str
    fonts: dict[str, str]


class DuckingConfig(BaseModel):
    enabled: bool
    threshold_db: float
    attack_ms: float
    release_ms: float


class Audio(BaseModel):
    voiceover_url: Optional[HttpUrl] = None
    voiceover_srt_url: Optional[HttpUrl] = None
    music_url: Optional[HttpUrl] = None
    music_volume_db: Optional[float] = None
    ducking: Optional[DuckingConfig] = None
    loudness_target_lufs: Optional[float] = None


class Branding(BaseModel):
    intro_preset: Optional[str] = None
    outro_preset: Optional[str] = None
    watermark: Optional[PresetRef] = None


class Resolution(BaseModel):
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)


class Meta(BaseModel):
    video_id: str
    channel_id: str
    title: str
    duration_target_seconds: float = Field(..., gt=0)
    aspect: Aspect
    fps: int = Field(..., gt=0)
    resolution: Resolution


class ThumbnailTitle(BaseModel):
    text: str
    font: str
    weight: int
    size: int
    color: str
    stroke: Optional[dict[str, Any]] = None


class Thumbnail(BaseModel):
    composition: str  # "ThumbnailComp"
    layout_preset: str
    background_url: HttpUrl
    title: ThumbnailTitle
    format: str  # "png" | "jpg"
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)


class DirectionV3_1(BaseModel):
    """Root Direction v3.1 payload. Also accepts v3.0 (all v3.1 fields optional)."""

    model_config = ConfigDict(extra="allow")

    version: DirectionVersion
    meta: Meta
    template: str
    theme: Theme
    grade_preset: str
    global_effects: Optional[list[str]] = None
    global_overlays: Optional[list[PresetRef]] = None
    audio: Optional[Audio] = None
    branding: Optional[Branding] = None
    segments: list[Segment] = Field(..., min_length=1)
    thumbnail: Optional[Thumbnail] = None


# ── density validator ─────────────────────────────────────────────────────


def validate_timeline_density(direction: DirectionV3_1) -> list[str]:
    """Check every segment's timeline has ≤500 ms gaps.

    Only enforced when a segment actually declares a ``timeline`` — v3.0
    payloads (no timeline) pass unchecked. Assembly service upgrades
    v3.0 → v3.1 via the densifier before this check.

    Returns a list of human-readable issues. Empty list = passes.
    """
    issues: list[str] = []
    for seg in direction.segments:
        if not seg.timeline:
            continue
        kfs = sorted(seg.timeline, key=lambda k: k.t_ms)
        if kfs[0].t_ms > 0:
            issues.append(f"segment {seg.id}: first keyframe at {kfs[0].t_ms}ms, expected 0")
        last = kfs[-1]
        tail_gap = seg.duration_ms - last.t_ms
        if tail_gap > MAX_KEYFRAME_GAP_MS:
            issues.append(
                f"segment {seg.id}: last keyframe at {last.t_ms}ms leaves "
                f"{tail_gap}ms tail (> {MAX_KEYFRAME_GAP_MS}ms floor) before segment end"
            )
        for i in range(1, len(kfs)):
            gap = kfs[i].t_ms - kfs[i - 1].t_ms
            if gap > MAX_KEYFRAME_GAP_MS:
                issues.append(
                    f"segment {seg.id}: keyframe gap {gap}ms between "
                    f"t={kfs[i - 1].t_ms} and t={kfs[i].t_ms} exceeds {MAX_KEYFRAME_GAP_MS}ms floor"
                )
    return issues
