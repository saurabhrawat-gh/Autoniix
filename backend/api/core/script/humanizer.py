"""Humanizer — Makes AI-generated scripts sound natural and human.

Applies transformations to remove robotic patterns and add conversational flow:
- Contraction injection ("do not" → "don't")
- AI pattern removal (generic phrases that scream AI)
- Sentence length variation (avoid monotone rhythm)
- Conversational fillers at natural points
- Spoken rhythm enforcement (break at breath points)
- Channel voice adaptation
- Filler word cleanup

All computation is local. Zero API cost.
"""

from __future__ import annotations

import random
import re
from typing import Any

import structlog

from services_api.script.script_analyzer import (
    compute_contraction_rate,
    detect_ai_patterns,
)

logger = structlog.get_logger()

CONTRACTION_MAP = {
    r"\bdo not\b": "don't",
    r"\bdoes not\b": "doesn't",
    r"\bdid not\b": "didn't",
    r"\bwill not\b": "won't",
    r"\bwould not\b": "wouldn't",
    r"\bcould not\b": "couldn't",
    r"\bshould not\b": "shouldn't",
    r"\bcan not\b": "can't",
    r"\bcannot\b": "can't",
    r"\bis not\b": "isn't",
    r"\bare not\b": "aren't",
    r"\bwas not\b": "wasn't",
    r"\bwere not\b": "weren't",
    r"\bhave not\b": "haven't",
    r"\bhas not\b": "hasn't",
    r"\bhad not\b": "hadn't",
    r"\bit is\b": "it's",
    r"\bthat is\b": "that's",
    r"\bthere is\b": "there's",
    r"\bhere is\b": "here's",
    r"\bwhat is\b": "what's",
    r"\bwho is\b": "who's",
    r"\byou are\b": "you're",
    r"\bthey are\b": "they're",
    r"\bwe are\b": "we're",
    r"\bI am\b": "I'm",
    r"\byou have\b": "you've",
    r"\bwe have\b": "we've",
    r"\bthey have\b": "they've",
    r"\bI have\b": "I've",
    r"\byou will\b": "you'll",
    r"\bwe will\b": "we'll",
    r"\bthey will\b": "they'll",
    r"\bI will\b": "I'll",
    r"\byou would\b": "you'd",
    r"\bwe would\b": "we'd",
    r"\bthey would\b": "they'd",
    r"\bI would\b": "I'd",
    r"\blet us\b": "let's",
}
_CONTRACTION_COMPILED = {re.compile(k, re.IGNORECASE): v for k, v in CONTRACTION_MAP.items()}

AI_REPLACEMENTS = [
    (
        r"\blet'?s dive (?:right )?in\b",
        ["Here's what you need to know.", "So here's the deal.", "Let me break this down."],
    ),
    (
        r"\bit(?:'s| is) important to (?:note|understand|remember) that\b",
        ["The key thing here:", "Here's what matters:", "Pay attention to this:"],
    ),
    (r"\bin (?:today's|this) (?:video|article)\b", ["Right now", "In the next few minutes", ""]),
    (r"\bwithout further ado\b", ["So", "Alright", ""]),
    (r"\bin conclusion\b", ["So here's the bottom line", "Here's what it all comes down to", "The real takeaway"]),
    (r"\bas we (?:all )?know\b", ["Look,", "Here's the thing:", ""]),
    (r"\bmoreover\b", ["And", "Plus", "On top of that"]),
    (r"\bfurthermore\b", ["And", "Plus", "Also"]),
    (r"\bnevertheless\b", ["But still", "Even so", "Still"]),
    (r"\bin the realm of\b", ["in", "when it comes to", "with"]),
    (
        r"\bnavigat(?:e|ing) the (?:complexit(?:y|ies)|landscape|world)\b",
        ["figuring out", "dealing with", "understanding"],
    ),
    (r"\bunlock(?:ing)? the (?:power|potential|secret)\b", ["tapping into", "using", "getting the most from"]),
    (r"\bjourney\b", ["process", "path", "experience"]),
    (r"\btake(?:s)? a closer look\b", ["look at this", "check this out", "dig into"]),
    (r"\bdelve\b", ["dig", "get", "look"]),
    (r"\beverything you need to know\b", ["the essentials", "what actually matters", "the real story"]),
    (r"\bbuckle up\b", ["", "Get ready", ""]),
]
_AI_REPLACE_COMPILED = [(re.compile(p, re.IGNORECASE), alts) for p, alts in AI_REPLACEMENTS]

BRIDGES = {
    "transition": [
        "Now,",
        "So,",
        "Here's the thing.",
        "And this is where it gets interesting.",
        "But wait.",
        "Think about it.",
        "Here's why that matters.",
    ],
    "emphasis": [
        "Seriously.",
        "And I mean that.",
        "This is huge.",
        "Read that again.",
        "Let that sink in.",
        "That's not a typo.",
    ],
    "engagement": [
        "Sound familiar?",
        "Ever noticed that?",
        "Makes sense, right?",
        "Crazy, right?",
        "Wild, isn't it?",
        "You see what happened there?",
    ],
}


def inject_contractions(text: str) -> str:
    """Convert formal phrases to contractions for natural speech."""
    for pattern, replacement in _CONTRACTION_COMPILED.items():

        def _replace(match, repl=replacement):
            original = match.group()
            if original[0].isupper():
                return repl[0].upper() + repl[1:]
            return repl

        text = pattern.sub(_replace, text)
    return text


def remove_ai_patterns(text: str) -> tuple[str, list[str]]:
    """Remove AI-typical phrasings and replace with natural alternatives."""
    removed = []
    for pattern, alternatives in _AI_REPLACE_COMPILED:

        def _replace(match, alts=alternatives):
            original = match.group()
            removed.append(original)
            replacement = random.choice(alts)
            if replacement and original[0].isupper():
                return replacement[0].upper() + replacement[1:]
            return replacement

        text = pattern.sub(_replace, text, count=1)

    text = re.sub(r"  +", " ", text).strip()
    return text, removed


def enforce_sentence_variation(text: str) -> str:
    """Ensure sentence lengths vary (no monotone rhythm).

    Breaks long sentences, occasionally merges very short ones.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) < 2:
        return text

    result = []
    for sent in sentences:
        words = sent.split()
        word_count = len(words)

        if word_count > 30:
            parts = re.split(r"(,\s*(?:and|but|or|so|because|which|that|where|when)\s)", sent, maxsplit=1)
            if len(parts) >= 3:
                first_part = parts[0] + "."
                second_part = parts[1].strip(", ").capitalize() + parts[2] if len(parts) > 2 else ""
                result.append(first_part)
                if second_part:
                    result.append(second_part)
                continue

        result.append(sent)

    return " ".join(result)


def enforce_spoken_rhythm(text: str) -> str:
    """Break sentences at natural breath points for spoken delivery.

    Adds em-dashes and ellipses where speakers naturally pause.
    """
    text = re.sub(r",?\s*\b(but|however|yet)\b", r" — \1", text)

    text = re.sub(r"\bbecause\b\s+", "because... ", text, count=2)

    return text


def adapt_to_channel_voice(text: str, pacing_style: str = "dynamic", brand_voice: str = "") -> str:
    """Adapt text to match channel's voice style."""
    if pacing_style == "slow_philosophical":
        text = re.sub(r"\.\s+", ". \n", text, count=3)
    elif pacing_style in ("fast_energetic", "fast_provocative"):
        text = re.sub(r",\s*and\s+", ". ", text)
    elif pacing_style == "gentle_progressive":
        text = text.replace(" — but", ", but")
        text = text.replace(" — however", ", however")

    return text


def humanize_segment(
    narration: str, pacing_style: str = "dynamic", brand_voice: str = "", seed: int | None = None
) -> dict[str, Any]:
    """Apply all humanization transforms to a segment's narration.

    Returns the humanized text plus metrics.
    """
    if seed is not None:
        random.seed(seed)

    original = narration
    text = narration

    text = inject_contractions(text)

    text, removed_patterns = remove_ai_patterns(text)

    text = enforce_sentence_variation(text)

    text = enforce_spoken_rhythm(text)

    text = adapt_to_channel_voice(text, pacing_style, brand_voice)

    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\.\s*\.", ".", text)
    text = re.sub(r"—\s*—", "—", text)

    original_contraction_rate = compute_contraction_rate(original)
    new_contraction_rate = compute_contraction_rate(text)
    remaining_ai = detect_ai_patterns(text)

    return {
        "original": original,
        "humanized": text,
        "ai_patterns_removed": removed_patterns,
        "ai_patterns_remaining": len(remaining_ai),
        "contraction_rate_before": round(original_contraction_rate, 3),
        "contraction_rate_after": round(new_contraction_rate, 3),
        "word_count_change": len(text.split()) - len(original.split()),
    }


def humanize_full_script(segments: list[dict], pacing_style: str = "dynamic", brand_voice: str = "") -> dict[str, Any]:
    """Humanize all segments in a script.

    Returns updated segments and aggregate metrics.
    """
    humanized_segments = []
    total_ai_removed = 0
    total_ai_remaining = 0

    for i, seg in enumerate(segments):
        narration = seg.get("narration", "")
        result = humanize_segment(narration, pacing_style, brand_voice, seed=None)

        updated = {**seg, "narration": result["humanized"]}
        humanized_segments.append(updated)

        total_ai_removed += len(result["ai_patterns_removed"])
        total_ai_remaining += result["ai_patterns_remaining"]

    total_words = sum(len(s.get("narration", "").split()) for s in humanized_segments)
    avg_contraction = compute_contraction_rate(" ".join(s.get("narration", "") for s in humanized_segments))

    contraction_score = 1.0 if 0.02 <= avg_contraction <= 0.06 else (0.7 if 0.01 <= avg_contraction <= 0.08 else 0.4)

    ai_density = total_ai_remaining / max(total_words, 1)
    ai_score = 1.0 if ai_density == 0 else max(0.2, 1.0 - ai_density * 50)

    all_sentences = []
    for s in humanized_segments:
        sents = re.split(r"[.!?]+", s.get("narration", ""))
        all_sentences.extend([len(sent.split()) for sent in sents if sent.strip()])

    if len(all_sentences) >= 3:
        mean_len = sum(all_sentences) / len(all_sentences)
        variance = sum((x - mean_len) ** 2 for x in all_sentences) / len(all_sentences)
        variation_score = min(1.0, variance / 25)
    else:
        variation_score = 0.5

    composite = contraction_score * 0.3 + ai_score * 0.4 + variation_score * 0.3

    return {
        "segments": humanized_segments,
        "metrics": {
            "ai_patterns_removed": total_ai_removed,
            "ai_patterns_remaining": total_ai_remaining,
            "contraction_rate": round(avg_contraction, 3),
            "contraction_score": round(contraction_score, 3),
            "ai_pattern_score": round(ai_score, 3),
            "variation_score": round(variation_score, 3),
            "composite_score": round(composite, 3),
        },
    }
