"""Inject Inworld TTS prosody markers into narration text.

Inworld ``inworld-tts-2`` recognises a set of inline instruction/event
markers that shape delivery. The current voice pipeline computes
``prosody_hint``, ``emphasis_words``, ``pause_after_ms`` per sentence but
never surfaces any of it to Inworld — the marker text below is what
takes those hints from "data we have" to "sound the model actually makes".

Supported markers (see Inworld docs):
    [breath]                        — audible inhale before the next word
    [pause 500ms]                   — literal pause of N ms
    [laugh]                         — brief laugh
    [sigh]                          — audible sigh
    [speak with emphasis on X, Y]   — instruction prefix (only at the START of a chunk)
    [speak calmly / dramatically /  — delivery instructions (start of chunk)
     seriously ...]

Two entry points:

* :func:`inject_prosody_markers` — takes a sentence + a ``ProsodyMarker``
  spec and returns the instrumented text.
* :func:`render_emphasis_instruction` — builds the ``[speak with
  emphasis on ...]`` prefix from a list of emphasis words. Idempotent —
  if there are no emphasis words it returns an empty string so callers
  can safely prepend unconditionally.

This module does NOT call Inworld. It's a pure text transformer so we can
unit-test it and swap it in behind the voice service.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class ProsodyMarker:
    """Sentence-level prosody hints resolved from script/voice services."""

    emphasis_words: Sequence[str] = field(default_factory=list)
    pause_before_ms: int = 0
    pause_after_ms: int = 0
    opening_breath: bool = False
    closing_sigh: bool = False
    closing_laugh: bool = False
    delivery_instruction: str | None = None  # e.g. "speak dramatically"


_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
_INWORLD_MAX_PAUSE_MS = 3000  # protect against huge pauses


def render_emphasis_instruction(emphasis_words: Sequence[str]) -> str:
    """Return ``[speak with emphasis on X, Y]`` or empty string.

    Deduplicates and preserves order. Caps at 6 words to keep the
    instruction prefix short (Inworld's model degrades on long
    instructions).
    """
    if not emphasis_words:
        return ""
    seen: set[str] = set()
    ordered: list[str] = []
    for w in emphasis_words:
        w_clean = w.strip().strip(".,!?;:\"'()")
        if not w_clean:
            continue
        key = w_clean.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(w_clean)
        if len(ordered) >= 6:
            break
    if not ordered:
        return ""
    if len(ordered) == 1:
        return f"[speak with emphasis on {ordered[0]}] "
    body = ", ".join(ordered[:-1]) + f" and {ordered[-1]}"
    return f"[speak with emphasis on {body}] "


def _cap_pause(ms: int) -> int:
    return max(0, min(int(ms), _INWORLD_MAX_PAUSE_MS))


def inject_prosody_markers(
    sentence: str,
    marker: ProsodyMarker,
    *,
    include_delivery_prefix: bool = True,
) -> str:
    """Instrument a raw sentence with Inworld prosody markers.

    Returns the sentence unchanged when no prosody hints apply, so this
    is safe to call for every sentence.

    Order of injected pieces (matches Inworld expectations — instruction
    prefixes MUST come first, at the start of the chunk):
      1. delivery instruction prefix (``[speak calmly] ``)
      2. emphasis instruction prefix (``[speak with emphasis on X] ``)
      3. opening breath (``[breath] ``)
      4. pause_before  (``[pause Nms] ``)
      5. the sentence itself
      6. pause_after
      7. closing sigh / laugh

    Emphasis is applied via the instruction prefix — Inworld's ``tts-2``
    does not use inline ``[emphasize]`` on individual words; the model
    reads the prefix and picks up the emphasized words from the body.
    """
    if not sentence.strip():
        return sentence

    parts: list[str] = []

    if include_delivery_prefix and marker.delivery_instruction:
        instr = marker.delivery_instruction.strip()
        if not instr.startswith("["):
            instr = f"[{instr}]"
        parts.append(instr + " ")

    emphasis_prefix = render_emphasis_instruction(marker.emphasis_words)
    if emphasis_prefix:
        parts.append(emphasis_prefix)

    if marker.opening_breath:
        parts.append("[breath] ")

    if marker.pause_before_ms > 0:
        parts.append(f"[pause {_cap_pause(marker.pause_before_ms)}ms] ")

    parts.append(sentence.strip())

    if marker.pause_after_ms > 0:
        parts.append(f" [pause {_cap_pause(marker.pause_after_ms)}ms]")

    if marker.closing_sigh:
        parts.append(" [sigh]")
    if marker.closing_laugh:
        parts.append(" [laugh]")

    result = "".join(parts)
    logger.debug(
        "prosody.injected",
        emphasis_count=len(marker.emphasis_words),
        pauses_ms=(marker.pause_before_ms, marker.pause_after_ms),
        length_delta=len(result) - len(sentence),
    )
    return result


def extract_emphasis_words_from_text(
    sentence: str,
    *,
    caps_ratio_threshold: float = 0.6,
    surrounded_by_stars: bool = True,
) -> list[str]:
    """Heuristic fallback: extract emphasis words directly from the script text.

    Used when the script service didn't pre-compute ``emphasis_words``.
    Detects:
      - Words wrapped in ``*asterisks*``
      - Fully-capitalised words (2+ letters, exceeding ``caps_ratio``)
    Returns unique, order-preserving list.
    """
    found: list[str] = []
    if surrounded_by_stars:
        for match in re.finditer(r"\*([^*]+)\*", sentence):
            for word in match.group(1).split():
                w = word.strip(".,!?;:\"'()")
                if w:
                    found.append(w)

    for match in _WORD_RE.finditer(sentence):
        word = match.group()
        if len(word) < 2:
            continue
        alpha = [c for c in word if c.isalpha()]
        if not alpha:
            continue
        caps = sum(1 for c in alpha if c.isupper())
        if caps / len(alpha) >= caps_ratio_threshold and word.upper() == word:
            found.append(word)

    # dedup preserving order
    seen: set[str] = set()
    out: list[str] = []
    for w in found:
        key = w.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out
