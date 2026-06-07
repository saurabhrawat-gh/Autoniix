"""LUT preset registry for the Professional Finishing Pipeline (AE-293 / AE-294).

Single source of truth for the 7 built-in colour-grade presets. Used by both
the worker (``ffmpeg_finisher``) to resolve a ``.cube`` file and the dashboard
API (``finishing.py``) to render the preset picker.

Each preset's ``.cube`` file is seeded into MinIO at ``luts/{key}.cube`` at
bootstrap (see ``scripts/seeds/lut_presets/generate_luts.py``). Preview JPEGs
live at ``luts/previews/{key}.jpg``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.config import settings

LUT_MINIO_PREFIX = "luts/"
LUT_PREVIEW_PREFIX = "luts/previews/"


@dataclass(frozen=True)
class LutPreset:
    key: str
    display_name: str
    description: str
    best_for: list[str] = field(default_factory=list)

    @property
    def cube_key(self) -> str:
        """MinIO object key for this preset's .cube file."""
        return f"{LUT_MINIO_PREFIX}{self.key}.cube"

    @property
    def preview_key(self) -> str:
        """MinIO object key for this preset's preview thumbnail."""
        return f"{LUT_PREVIEW_PREFIX}{self.key}.jpg"

    def thumbnail_url(self) -> str:
        base = (settings.s3_public_base_url or "").rstrip("/")
        if base:
            return f"{base}/{self.preview_key}"
        # Fall back to the canonical assets host referenced in the spec.
        return f"https://assets.autoniix.com/{self.preview_key}"

    def to_api(self) -> dict:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url(),
            "best_for": list(self.best_for),
        }


# Order here is the order shown in the dashboard preset picker.
PRESETS: tuple[LutPreset, ...] = (
    LutPreset(
        key="cinematic",
        display_name="Cinematic",
        description="Teal-orange, lifted blacks, warm shadows — Netflix / high-CPM look",
        best_for=["finance", "tech", "drama"],
    ),
    LutPreset(
        key="clean_bright",
        display_name="Clean & Bright",
        description="Punchy, vibrant, clean whites — educational / explainer look",
        best_for=["educational", "explainer", "tutorials"],
    ),
    LutPreset(
        key="warm_gold",
        display_name="Warm Gold",
        description="Golden warmth with a subtle vignette",
        best_for=["lifestyle", "travel", "wellness"],
    ),
    LutPreset(
        key="cool_blue",
        display_name="Cool Blue",
        description="Desaturated blues, high contrast",
        best_for=["sci-fi", "gaming", "technology"],
    ),
    LutPreset(
        key="vintage",
        display_name="Vintage Film",
        description="Faded, slightly warm, film-grain emulation",
        best_for=["history", "nostalgia", "documentary-style"],
    ),
    LutPreset(
        key="documentary",
        display_name="Documentary",
        description="Natural, desaturated, truthful colour",
        best_for=["news", "commentary", "real-world"],
    ),
    LutPreset(
        key="neon_dark",
        display_name="Neon Dark",
        description="Dark base, neon accent, cinematic low-key",
        best_for=["music", "entertainment", "highlight-reels"],
    ),
)

PRESET_KEYS: tuple[str, ...] = tuple(p.key for p in PRESETS)
_BY_KEY: dict[str, LutPreset] = {p.key: p for p in PRESETS}

DEFAULT_PRESET = "cinematic"


def is_valid_preset(key: str) -> bool:
    return key in _BY_KEY


def get_preset(key: str) -> LutPreset | None:
    return _BY_KEY.get(key)


def cube_key_for(preset_key: str) -> str:
    """MinIO object key for the given preset's .cube file (falls back to default)."""
    preset = _BY_KEY.get(preset_key) or _BY_KEY[DEFAULT_PRESET]
    return preset.cube_key


def all_presets_api() -> list[dict]:
    return [p.to_api() for p in PRESETS]
