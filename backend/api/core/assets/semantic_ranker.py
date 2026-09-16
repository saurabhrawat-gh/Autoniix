"""Semantic re-ranker for stock-footage candidates.

Computes a 0–1 fitness score per candidate using six weighted signals from
the master plan §3.3:

    score = 0.40 · semantic_similarity (SBERT cosine on query vs tags/title)
          + 0.20 · motion_match        (still ↔ dynamic ↔ frenetic)
          + 0.15 · color_match         (clip palette vs brand palette)
          + 0.10 · license_freedom     (CC0/free > paid > unknown)
          + 0.10 · duration_fit        (clip dur vs requested seg dur)
          + 0.05 · resolution_match    (target 1080p+ for prod, 720p+ test)

Candidates with ``final_score < threshold`` (default 0.55) are rejected so
the chain falls through to the next provider — and, ultimately, to a
kinetic-typography fallback rather than a black frame.

The SBERT model is loaded lazily inside a process-wide cache so service
startup stays fast (~50 ms) even though the model itself is ~80 MB.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Iterable

import structlog

logger = structlog.get_logger()

W_SEMANTIC = 0.40
W_MOTION = 0.20
W_COLOR = 0.15
W_LICENSE = 0.10
W_DURATION = 0.10
W_RESOLUTION = 0.05
SCORE_REJECT_THRESHOLD = 0.55

_MODEL = None
_MODEL_LOCK = threading.Lock()


def _get_model():
    """Lazy-load the SBERT MiniLM model. Returns ``None`` if the optional
    dependency is missing — callers degrade gracefully to keyword scoring.
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            _MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("semantic_ranker.model_loaded", model="MiniLM-L6-v2")
        except Exception as exc:  # pragma: no cover - optional dep
            logger.warning("semantic_ranker.model_unavailable", error=str(exc))
            _MODEL = False
    return _MODEL or None


@dataclass
class ScoredCandidate:
    """Candidate clip annotated with its sub-scores and final score."""

    clip: dict
    semantic: float = 0.0
    motion: float = 0.0
    color: float = 0.0
    license_: float = 0.0
    duration: float = 0.0
    resolution: float = 0.0
    final: float = 0.0
    rejected: bool = False
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "semantic": round(self.semantic, 3),
            "motion": round(self.motion, 3),
            "color": round(self.color, 3),
            "license": round(self.license_, 3),
            "duration": round(self.duration, 3),
            "resolution": round(self.resolution, 3),
            "final": round(self.final, 3),
            "rejected": self.rejected,
        }


def _semantic_sim(query: str, candidate_text: str, model) -> float:
    """Cosine similarity in 0–1. Falls back to keyword overlap if no model."""
    if not query or not candidate_text:
        return 0.0
    q = query.lower().strip()
    c = candidate_text.lower().strip()
    if model is None:
        qs = set(q.split())
        cs = set(c.split())
        if not qs or not cs:
            return 0.0
        inter = len(qs & cs)
        union = len(qs | cs)
        return inter / union if union else 0.0
    try:
        import numpy as np

        vecs = model.encode([q, c], normalize_embeddings=True)
        sim = float(np.dot(vecs[0], vecs[1]))
        return max(0.0, (sim + 1.0) / 2.0)
    except Exception as exc:
        logger.warning("semantic_ranker.sbert_failed", error=str(exc))
        return 0.0


def _motion_score(intent: str, clip: dict) -> float:
    """Map (scene intent, clip duration/resolution heuristics) → 0–1.

    Intent values come from Direction v3: ``still | dynamic | frenetic``.
    We don't have ground-truth motion analysis on stock clips so we use a
    duration-based proxy: short clips (≤ 4s) tend to be dynamic snippets,
    medium (5–10s) are typical b-roll, long (>10s) are slower-paced.
    """
    intent = (intent or "dynamic").lower()
    dur = float(clip.get("duration", 0) or 0)
    if dur <= 0:
        return 0.5
    if intent == "still":
        return 1.0 if dur >= 8 else max(0.3, dur / 8.0)
    if intent == "frenetic":
        return 1.0 if dur <= 4 else max(0.3, 1.0 - (dur - 4) / 16.0)
    if 4 <= dur <= 12:
        return 1.0
    return max(0.4, 1.0 - abs(dur - 8) / 16.0)


def _hex_to_rgb(h: str) -> tuple[int, int, int] | None:
    h = (h or "").lstrip("#").strip()
    if len(h) != 6:
        return None
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None


def _palette_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Normalised Euclidean colour distance in 0–1."""
    d = math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))
    return min(1.0, d / 441.673)


def _color_score(brand_palette: Iterable[str] | None, clip: dict) -> float:
    """Compare clip's dominant colours to the brand palette. Returns 0–1.

    No brand palette → neutral 0.6. No clip colours → neutral 0.5.
    """
    brand = [c for c in (brand_palette or []) if isinstance(c, str)]
    brand_rgb = [rgb for rgb in (_hex_to_rgb(c) for c in brand) if rgb]
    if not brand_rgb:
        return 0.6
    clip_colors = clip.get("dominant_colors") or []
    clip_rgb = [rgb for rgb in (_hex_to_rgb(c) for c in clip_colors) if rgb]
    if not clip_rgb:
        return 0.5
    best_dist = min(_palette_distance(b, c) for b in brand_rgb for c in clip_rgb)
    return max(0.0, 1.0 - best_dist)


def _license_score(clip: dict) -> float:
    lic = (clip.get("license") or "").lower()
    if any(t in lic for t in ("cc0", "public_domain", "free", "pixabay_free", "pexels_free")):
        return 1.0
    if "motionarray" in lic or "library" in lic:
        return 0.9
    if "editorial" in lic:
        return 0.4
    return 0.6


def _duration_score(target_seconds: float, clip: dict) -> float:
    """Triangular kernel around the target duration with ±50% tolerance."""
    if target_seconds <= 0:
        return 0.7
    dur = float(clip.get("duration", 0) or 0)
    if dur <= 0:
        return 0.4
    if dur >= target_seconds:
        return max(0.0, 1.0 - (dur - target_seconds) / target_seconds)
    return max(0.0, 1.0 - (target_seconds - dur) / target_seconds)


def _resolution_score(clip: dict, prefer_1080p: bool = True) -> float:
    h = int(clip.get("height", 0) or 0)
    if h >= 1080:
        return 1.0
    if h >= 720:
        return 0.7 if prefer_1080p else 1.0
    if h >= 480:
        return 0.4
    return 0.2


def _candidate_text(clip: dict) -> str:
    """Build the search-side text used for semantic similarity."""
    parts = [
        clip.get("title", ""),
        clip.get("tags", "") if isinstance(clip.get("tags"), str) else " ".join(clip.get("tags") or []),
        clip.get("description", ""),
    ]
    return " ".join(p for p in parts if p).strip()[:600]


def score_candidates(
    *,
    query: str,
    candidates: list[dict],
    motion_intent: str = "dynamic",
    target_duration_s: float = 0.0,
    brand_palette: Iterable[str] | None = None,
    prefer_1080p: bool = True,
    threshold: float = SCORE_REJECT_THRESHOLD,
) -> list[ScoredCandidate]:
    """Score every candidate, attach sub-scores, sort descending, return all.

    Caller can then filter by ``not rejected`` and pick the top result.
    Rejected candidates are still returned (for debugging / logging) with
    ``rejected=True``.
    """
    model = _get_model()
    out: list[ScoredCandidate] = []
    for clip in candidates:
        text = _candidate_text(clip)
        sem = _semantic_sim(query, text, model) if text else 0.0
        mot = _motion_score(motion_intent, clip)
        col = _color_score(brand_palette, clip)
        lic = _license_score(clip)
        dur = _duration_score(target_duration_s, clip)
        res = _resolution_score(clip, prefer_1080p=prefer_1080p)
        final = (
            W_SEMANTIC * sem + W_MOTION * mot + W_COLOR * col + W_LICENSE * lic + W_DURATION * dur + W_RESOLUTION * res
        )
        sc = ScoredCandidate(
            clip=clip,
            semantic=sem,
            motion=mot,
            color=col,
            license_=lic,
            duration=dur,
            resolution=res,
            final=final,
        )
        if final < threshold:
            sc.rejected = True
            sc.reasons.append(f"score {final:.2f} below threshold {threshold:.2f}")
        out.append(sc)

    out.sort(key=lambda x: x.final, reverse=True)
    return out


def best_candidate(
    scored: list[ScoredCandidate],
) -> ScoredCandidate | None:
    """Return the top non-rejected candidate, or None if all rejected."""
    for sc in scored:
        if not sc.rejected:
            return sc
    return None
