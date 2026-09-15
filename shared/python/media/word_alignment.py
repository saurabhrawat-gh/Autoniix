"""Normalize word-level TTS alignment into a common shape.

Different providers return word-timing data in different envelopes.
This module gives the pipeline a single ``AlignedWord`` schema that
directly feeds the Direction v3.1 ``captions[]`` field.

Sources supported:
    * **Inworld TTS**  — ``get_word_timestamps()`` returns
      ``{"words": [{"word", "startTimeSeconds", "endTimeSeconds", ...}]}``
      OR (newer API) ``{"timestamps": [{"text", "startTime", "endTime"}]}``.
      We accept both shapes.
    * **whisperx**  — forced-alignment fallback. Returns
      ``segments[].words[] = {"word", "start", "end", "score"}``.

Every entry ends up as an :class:`AlignedWord` with:
    - ``word``: str
    - ``start_ms``: int (0-anchored)
    - ``end_ms``: int
    - ``confidence``: float (0..1) — 1.0 for Inworld (they don't return score),
      the whisperx score otherwise
    - ``segment_id`` and ``sentence_id``: optional annotations added later by
      the voice service so downstream can group words by sentence/segment.

Both normalizers gracefully return ``[]`` on unrecognized input so the
voice service can fall back without crashing the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import structlog
from contracts.direction_v3_1 import CaptionWord

logger = structlog.get_logger()


@dataclass(frozen=True)
class AlignedWord:
    word: str
    start_ms: int
    end_ms: int
    confidence: float = 1.0
    segment_id: str | None = None
    sentence_id: str | None = None
    is_emphasis: bool = False


def _to_ms(value: Any) -> int | None:
    """Coerce a ``str | float | int`` timestamp (seconds) to ms int.

    Inworld variants:
      * ``"0.400s"`` — string with 's'
      * ``0.400``    — plain float seconds
      * ``400``      — already-ms int (rare, but defensive)
    """
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if s.endswith("s"):
            s = s[:-1]
        try:
            return int(round(float(s) * 1000))
        except ValueError:
            return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    # If the number looks like milliseconds (large int) keep it; else seconds→ms.
    if v > 1000:  # anything > 1s written as an int is almost certainly already ms
        return int(round(v))
    return int(round(v * 1000))


def normalize_inworld_alignment(
    payload: dict[str, Any] | None,
    *,
    segment_id: str | None = None,
    sentence_id: str | None = None,
    emphasis_words: Iterable[str] = (),
) -> list[AlignedWord]:
    """Convert Inworld ``timestampInfo`` payload → list[AlignedWord].

    Inworld returns one of these envelopes (spec has changed across
    versions; we accept all we've seen):

    Shape A (newer)::
        {"timestamps": [{"text": "Sleep", "startTime": "0.120s",
                          "endTime": "0.480s"}]}

    Shape B (older)::
        {"words": [{"word": "Sleep", "startTimeSeconds": 0.12,
                     "endTimeSeconds": 0.48}]}

    Shape C (defensive)::
        [{"word": "Sleep", "start": 120, "end": 480}]

    Returns ``[]`` on unrecognized input so callers can fall back to
    whisperx without crashing.
    """
    if not payload:
        return []

    entries: list[dict[str, Any]]
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = payload.get("timestamps") or payload.get("words") or payload.get("wordTimestamps") or []
    else:
        logger.warning("word_alignment.inworld.unknown_shape", type=type(payload).__name__)
        return []

    if not entries:
        return []

    emphasis_lower = {w.strip().strip(".,!?;:\"'()").lower() for w in emphasis_words if w}

    out: list[AlignedWord] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        word = e.get("word") or e.get("text") or e.get("token") or ""
        word = str(word).strip()
        if not word:
            continue
        start_ms = _to_ms(
            e.get("startTime") or e.get("startTimeSeconds") or e.get("start") or e.get("startMs") or e.get("start_ms")
        )
        end_ms = _to_ms(
            e.get("endTime") or e.get("endTimeSeconds") or e.get("end") or e.get("endMs") or e.get("end_ms")
        )
        if start_ms is None or end_ms is None:
            continue
        if end_ms <= start_ms:
            end_ms = start_ms + 50  # 50ms floor per word
        clean_key = word.strip(".,!?;:\"'()").lower()
        out.append(
            AlignedWord(
                word=word,
                start_ms=max(0, start_ms),
                end_ms=end_ms,
                confidence=1.0,
                segment_id=segment_id,
                sentence_id=sentence_id,
                is_emphasis=clean_key in emphasis_lower,
            )
        )
    return out


def normalize_whisperx_alignment(
    payload: dict[str, Any] | None,
    *,
    segment_id: str | None = None,
    sentence_id: str | None = None,
    emphasis_words: Iterable[str] = (),
) -> list[AlignedWord]:
    """Convert whisperx output → list[AlignedWord].

    whisperx returns::
        {"segments": [{"start": 0.0, "end": 3.4, "text": "...",
                        "words": [{"word": "Sleep", "start": 0.12,
                                    "end": 0.48, "score": 0.92}, ...]}]}
    """
    if not payload or not isinstance(payload, dict):
        return []

    segments = payload.get("segments") or []
    if not segments:
        # some callers pass the flat words list directly
        words = payload.get("words") or []
        segments = [{"words": words}] if words else []

    emphasis_lower = {w.strip().strip(".,!?;:\"'()").lower() for w in emphasis_words if w}

    out: list[AlignedWord] = []
    for seg in segments:
        for w in seg.get("words", []) or []:
            word = str(w.get("word") or w.get("text") or "").strip()
            if not word:
                continue
            start_ms = _to_ms(w.get("start"))
            end_ms = _to_ms(w.get("end"))
            if start_ms is None or end_ms is None:
                continue
            if end_ms <= start_ms:
                end_ms = start_ms + 50
            try:
                confidence = float(w.get("score", w.get("confidence", 1.0)))
            except (TypeError, ValueError):
                confidence = 1.0
            clean_key = word.strip(".,!?;:\"'()").lower()
            out.append(
                AlignedWord(
                    word=word,
                    start_ms=max(0, start_ms),
                    end_ms=end_ms,
                    confidence=max(0.0, min(1.0, confidence)),
                    segment_id=segment_id,
                    sentence_id=sentence_id,
                    is_emphasis=clean_key in emphasis_lower,
                )
            )
    return out


def to_caption_words(
    aligned: Iterable[AlignedWord],
    *,
    offset_ms: int = 0,
    style_id: str | None = None,
) -> list[CaptionWord]:
    """Convert normalized ``AlignedWord`` list → Direction v3.1 ``CaptionWord[]``.

    ``offset_ms`` shifts every timestamp — used when concatenating
    per-sentence alignments into a whole-segment timeline.

    ``style_id`` sets the caption preset ID (e.g. ``"cap.pop.yellow"``);
    emphasis words can be routed to a different style_id by the caller
    when needed.
    """
    out: list[CaptionWord] = []
    for w in aligned:
        out.append(
            CaptionWord(
                word=w.word,
                start_ms=max(0, w.start_ms + offset_ms),
                end_ms=max(1, w.end_ms + offset_ms),
                is_emphasis=w.is_emphasis,
                sentence_id=w.sentence_id,
                style_id=style_id,
            )
        )
    return out
