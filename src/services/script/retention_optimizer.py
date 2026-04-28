"""Retention Optimizer — Attention economics analysis for scripts.

Scores scripts on YouTube-specific retention mechanics:
- Curiosity loops: opened vs closed, placement quality
- "But/Therefore" technique (South Park method vs "And then")
- Pattern interrupt frequency (target: every 3-8 seconds)
- Open loop tracking and resolution
- Emotional peaks and valleys (should alternate)
- Information density (unique concepts per 100 words)
- Hook strength (first 5-second analysis)
- Pacing rhythm analysis

All computation is local. Zero API cost.
"""
from __future__ import annotations

import re
from typing import Any

import structlog

from src.services.script.script_analyzer import (
    compute_specificity,
    compute_question_density,
    detect_emotions,
    estimate_speaking_duration,
    count_syllables,
    EMOTION_LEXICON,
)

logger = structlog.get_logger()

# ── Curiosity Gap Markers ─────────────────────────────────────
CURIOSITY_OPENERS = [
    r"\bwhy\b", r"\bhow\b", r"\bwhat if\b", r"\bwhat happens\b",
    r"\bever wonder\b", r"\bdid you know\b", r"\bhere'?s (?:the|a) (?:secret|thing|truth)\b",
    r"\bthe (?:real|actual|surprising|shocking) (?:reason|truth|answer)\b",
    r"\bbut (?:here'?s|there'?s) (?:the|a) (?:catch|twist|problem)\b",
    r"\bnobody (?:talks|knows|tells)\b", r"\bno one (?:talks|knows|tells)\b",
    r"\bmost people (?:don'?t|never)\b", r"\bthe mistake\b",
    r"\byet\b", r"\bbut wait\b", r"\bthere'?s more\b",
    r"\bguess what\b", r"\byou won'?t believe\b",
]
_CURIOSITY_COMPILED = [re.compile(p, re.IGNORECASE) for p in CURIOSITY_OPENERS]

CURIOSITY_CLOSERS = [
    r"\bhere'?s (?:why|how|what)\b", r"\bthe answer is\b",
    r"\bthat'?s (?:why|how|because)\b", r"\bthe reason is\b",
    r"\bso here it is\b", r"\bturns out\b", r"\bthe truth is\b",
    r"\bthe solution\b", r"\bin short\b", r"\bsimply put\b",
]
_CLOSER_COMPILED = [re.compile(p, re.IGNORECASE) for p in CURIOSITY_CLOSERS]

# ── Pattern Interrupt Markers ─────────────────────────────────
PATTERN_INTERRUPTS = [
    r"\bbut\b", r"\bhowever\b", r"\bwait\b", r"\bhold on\b",
    r"\bactually\b", r"\bhere'?s (?:the|a) (?:thing|twist|catch)\b",
    r"\bplot twist\b", r"\bnow\b.*\b(?:gets?|is|becomes?)\b.*\b(?:interesting|weird|crazy|wild)\b",
    r"\bexcept\b", r"\bunless\b", r"\bcontrary\b",
    r"\bforget (?:everything|what)\b", r"\bwrong\b",
    r"\bsurprisingly\b", r"\bironically\b",
    r"\blet me (?:tell|show|explain)\b", r"\bstop\b",
    r"\bthink about (?:it|this|that)\b",
]
_INTERRUPT_COMPILED = [re.compile(p, re.IGNORECASE) for p in PATTERN_INTERRUPTS]

# ── But/Therefore vs And-Then ─────────────────────────────────
BUT_THEREFORE_PATTERNS = [
    r"\bbut\b", r"\btherefore\b", r"\bso\b", r"\bhowever\b",
    r"\bconsequently\b", r"\bas a result\b", r"\bbecause of this\b",
    r"\bthat'?s why\b", r"\bwhich means\b", r"\byet\b",
]
AND_THEN_PATTERNS = [
    r"\band then\b", r"\bnext\b", r"\bafter that\b",
    r"\bmoreover\b", r"\bfurthermore\b", r"\badditionally\b",
    r"\balso\b", r"\bin addition\b",
]
_BT_COMPILED = [re.compile(p, re.IGNORECASE) for p in BUT_THEREFORE_PATTERNS]
_AT_COMPILED = [re.compile(p, re.IGNORECASE) for p in AND_THEN_PATTERNS]


# ═══════════════════════════════════════════════════════════════
# RETENTION ANALYSIS
# ═══════════════════════════════════════════════════════════════

def analyze_curiosity_loops(text: str) -> dict[str, Any]:
    """Count curiosity openers and closers, compute loop balance."""
    openers = sum(len(p.findall(text)) for p in _CURIOSITY_COMPILED)
    closers = sum(len(p.findall(text)) for p in _CLOSER_COMPILED)

    # Ideal: more openers than closers (keeps tension), but closers > 0 (satisfies)
    loop_count = openers
    close_ratio = closers / max(openers, 1)

    # Score: penalize no loops, reward 3-8 loops per 1000 words
    words = max(len(text.split()), 1)
    loops_per_1k = (openers / words) * 1000
    if loops_per_1k >= 6:
        density_score = 1.0
    elif loops_per_1k >= 3:
        density_score = 0.7 + (loops_per_1k - 3) * 0.1
    elif loops_per_1k >= 1:
        density_score = 0.4 + (loops_per_1k - 1) * 0.15
    else:
        density_score = loops_per_1k * 0.4

    # Close ratio: ideal is 0.4-0.7 (some loops stay open for tension)
    if 0.4 <= close_ratio <= 0.7:
        balance_score = 1.0
    elif close_ratio < 0.4:
        balance_score = 0.5 + close_ratio
    else:
        balance_score = max(0.3, 1.0 - (close_ratio - 0.7))

    return {
        "opener_count": openers,
        "closer_count": closers,
        "loop_count": loop_count,
        "close_ratio": round(close_ratio, 3),
        "density_score": round(min(1.0, density_score), 3),
        "balance_score": round(balance_score, 3),
        "composite_score": round((density_score * 0.6 + balance_score * 0.4), 3),
    }


def analyze_pattern_interrupts(text: str, target_interval_words: int = 30) -> dict[str, Any]:
    """Analyze pattern interrupt frequency and placement.

    Target: one interrupt every 20-40 words (~8-15 seconds at 150 WPM).
    """
    words = text.split()
    total_words = len(words)

    interrupt_positions = []
    running_text = ""
    word_idx = 0

    for word in words:
        running_text += word + " "
        word_idx += 1
        for p in _INTERRUPT_COMPILED:
            if p.search(word + " "):
                interrupt_positions.append(word_idx)
                break

    # Remove consecutive duplicates (within 5 words)
    cleaned_positions = []
    for pos in interrupt_positions:
        if not cleaned_positions or pos - cleaned_positions[-1] > 5:
            cleaned_positions.append(pos)

    count = len(cleaned_positions)
    frequency = count / max(total_words / target_interval_words, 1)

    # Analyze spacing (gaps between interrupts)
    gaps = []
    if len(cleaned_positions) >= 2:
        for i in range(1, len(cleaned_positions)):
            gaps.append(cleaned_positions[i] - cleaned_positions[i - 1])

    avg_gap = sum(gaps) / max(len(gaps), 1) if gaps else total_words

    # Score: ideal gap is 20-40 words
    if 20 <= avg_gap <= 40:
        spacing_score = 1.0
    elif 15 <= avg_gap <= 50:
        spacing_score = 0.7
    elif 10 <= avg_gap <= 60:
        spacing_score = 0.5
    else:
        spacing_score = 0.3

    # Frequency score
    freq_per_1k = (count / max(total_words, 1)) * 1000
    if 20 <= freq_per_1k <= 40:
        freq_score = 1.0
    elif 10 <= freq_per_1k <= 50:
        freq_score = 0.7
    else:
        freq_score = max(0.2, min(1.0, freq_per_1k / 30))

    return {
        "interrupt_count": count,
        "positions": cleaned_positions[:20],
        "avg_gap_words": round(avg_gap, 1),
        "gaps": gaps[:20],
        "frequency_per_1k": round(freq_per_1k, 1),
        "spacing_score": round(spacing_score, 3),
        "frequency_score": round(freq_score, 3),
        "composite_score": round((spacing_score * 0.5 + freq_score * 0.5), 3),
    }


def analyze_but_therefore(text: str) -> dict[str, Any]:
    """Analyze But/Therefore vs And-Then ratio (South Park technique).

    Great scripts use causal connectors (but, therefore, so, however)
    rather than sequential connectors (and then, next, also).
    """
    bt_count = sum(len(p.findall(text)) for p in _BT_COMPILED)
    at_count = sum(len(p.findall(text)) for p in _AT_COMPILED)
    total = bt_count + at_count

    if total == 0:
        ratio = 0.5
    else:
        ratio = bt_count / total

    # Score: ideal is 0.65-0.85 BT ratio
    if 0.65 <= ratio <= 0.85:
        score = 1.0
    elif 0.50 <= ratio <= 0.90:
        score = 0.7
    elif 0.35 <= ratio <= 0.95:
        score = 0.5
    else:
        score = 0.3

    return {
        "but_therefore_count": bt_count,
        "and_then_count": at_count,
        "ratio": round(ratio, 3),
        "score": round(score, 3),
    }


async def analyze_emotional_arc(segments: list[dict]) -> dict[str, Any]:
    """Analyze emotional peaks and valleys across segments.

    Good scripts alternate tension/release, not flat or monotone.
    """
    intensities = []
    emotions_sequence = []

    for seg in segments:
        narration = seg.get("narration", "")
        emotions = await detect_emotions(narration)
        intensities.append(emotions["emotional_intensity"])
        emotions_sequence.append(emotions["dominant_emotion"])

    if len(intensities) < 2:
        return {
            "intensities": intensities,
            "emotions_sequence": emotions_sequence,
            "variance": 0.0,
            "has_climax": False,
            "arc_score": 0.3,
        }

    # Check for peaks (high points should be near start and 70-85% through)
    max_idx = intensities.index(max(intensities))
    relative_peak = max_idx / max(len(intensities) - 1, 1)

    # Variance: higher is better (means dynamic arc)
    mean_i = sum(intensities) / len(intensities)
    variance = sum((x - mean_i) ** 2 for x in intensities) / len(intensities)

    # Direction changes (peaks and valleys)
    direction_changes = 0
    for i in range(2, len(intensities)):
        prev_dir = intensities[i-1] - intensities[i-2]
        curr_dir = intensities[i] - intensities[i-1]
        if (prev_dir > 0 and curr_dir < 0) or (prev_dir < 0 and curr_dir > 0):
            direction_changes += 1

    # Has climax: should peak at 60-85% through
    has_climax = 0.5 <= relative_peak <= 0.9

    # Score components
    variance_score = min(1.0, variance * 10)  # Reward variance
    change_score = min(1.0, direction_changes / max(len(intensities) // 3, 1))
    climax_score = 1.0 if has_climax else 0.4

    arc_score = (variance_score * 0.3 + change_score * 0.4 + climax_score * 0.3)

    return {
        "intensities": [round(i, 3) for i in intensities],
        "emotions_sequence": emotions_sequence,
        "variance": round(variance, 4),
        "direction_changes": direction_changes,
        "peak_position": round(relative_peak, 2),
        "has_climax": has_climax,
        "arc_score": round(arc_score, 3),
    }


async def analyze_hook_strength(first_segment: dict, hook_duration_s: float = 5.0) -> dict[str, Any]:
    """Deep analysis of the hook (first 5 seconds).

    Checks: curiosity trigger, specificity, emotion trigger,
    open loop creation, pattern interrupt, power words.
    """
    narration = first_segment.get("narration", "")
    section = first_segment.get("section", "")

    # Estimate which words fall in first 5 seconds
    words = narration.split()
    wpm = 150
    words_in_hook = min(len(words), int((hook_duration_s / 60) * wpm))
    hook_text = " ".join(words[:words_in_hook]) if words_in_hook > 0 else narration

    scores = {}

    # Curiosity trigger
    curiosity_hits = sum(1 for p in _CURIOSITY_COMPILED if p.search(hook_text))
    scores["curiosity_trigger"] = min(1.0, curiosity_hits * 0.5)

    # Specificity (numbers, names, concrete details)
    scores["specificity"] = compute_specificity(hook_text)

    # Emotion trigger
    emotions = await detect_emotions(hook_text)
    scores["emotion_trigger"] = emotions["emotional_intensity"]

    # Question (creates open loop)
    scores["has_question"] = 1.0 if "?" in hook_text else 0.0

    # Pattern interrupt (subverts expectations)
    interrupt_hits = sum(1 for p in _INTERRUPT_COMPILED if p.search(hook_text))
    scores["pattern_interrupt"] = min(1.0, interrupt_hits * 0.5)

    # Power words
    hook_words_lower = set(hook_text.lower().split())
    from src.services.script.script_analyzer import POWER_WORDS
    power_hits = len(hook_words_lower & POWER_WORDS)
    scores["power_words"] = min(1.0, power_hits * 0.3)

    # Word economy (fewer words = more impact in hook)
    if words_in_hook <= 15:
        scores["word_economy"] = 1.0
    elif words_in_hook <= 25:
        scores["word_economy"] = 0.7
    else:
        scores["word_economy"] = 0.4

    # Composite
    weights = {
        "curiosity_trigger": 0.25, "specificity": 0.15, "emotion_trigger": 0.15,
        "has_question": 0.10, "pattern_interrupt": 0.10, "power_words": 0.10,
        "word_economy": 0.15,
    }
    composite = sum(scores[k] * weights[k] for k in weights)

    return {
        "hook_text": hook_text,
        "words_analyzed": words_in_hook,
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "composite_score": round(composite, 3),
        "dominant_emotion": emotions["dominant_emotion"],
    }


def analyze_information_density(text: str) -> dict[str, Any]:
    """Score information density — unique concepts per 100 words.

    High density = rich content. Too high = overwhelming. Too low = filler.
    """
    words = text.lower().split()
    total = max(len(words), 1)

    # Unique meaningful words (exclude stop words)
    STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "can", "could", "must", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into", "through",
        "during", "before", "after", "above", "below", "between", "and",
        "but", "or", "not", "no", "so", "if", "then", "than", "that",
        "this", "these", "those", "it", "its", "you", "your", "we", "our",
        "they", "their", "he", "she", "his", "her", "i", "my", "me",
    }
    meaningful = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    unique_meaningful = set(meaningful)

    # Concepts per 100 words
    density = (len(unique_meaningful) / total) * 100

    # Score: ideal 25-45 unique concepts per 100 words
    if 25 <= density <= 45:
        score = 1.0
    elif 20 <= density <= 50:
        score = 0.7
    elif 15 <= density <= 55:
        score = 0.5
    else:
        score = 0.3

    return {
        "unique_concepts": len(unique_meaningful),
        "total_words": total,
        "density_per_100": round(density, 1),
        "score": round(score, 3),
    }


# ═══════════════════════════════════════════════════════════════
# COMPOSITE RETENTION SCORE
# ═══════════════════════════════════════════════════════════════

async def compute_retention_score(segments: list[dict]) -> dict[str, Any]:
    """Compute comprehensive retention score for a full script.

    Returns composite score (0-1) with per-dimension breakdown.
    """
    if not segments:
        return {"composite_score": 0.0, "dimensions": {}, "recommendations": []}

    all_narration = " ".join(s.get("narration", "") for s in segments)

    # Run all analyses
    curiosity = analyze_curiosity_loops(all_narration)
    interrupts = analyze_pattern_interrupts(all_narration)
    bt = analyze_but_therefore(all_narration)
    emotional_arc = await analyze_emotional_arc(segments)
    hook = await analyze_hook_strength(segments[0]) if segments else {}
    info_density = analyze_information_density(all_narration)
    specificity = compute_specificity(all_narration)
    q_density = compute_question_density(all_narration)

    dimensions = {
        "curiosity_loops": curiosity["composite_score"],
        "pattern_interrupts": interrupts["composite_score"],
        "but_therefore_ratio": bt["score"],
        "emotional_arc": emotional_arc.get("arc_score", 0.3),
        "hook_strength": hook.get("composite_score", 0.3),
        "information_density": info_density["score"],
        "specificity": specificity,
        "question_engagement": min(1.0, q_density * 3),
    }

    weights = {
        "curiosity_loops": 0.18,
        "pattern_interrupts": 0.12,
        "but_therefore_ratio": 0.10,
        "emotional_arc": 0.15,
        "hook_strength": 0.20,
        "information_density": 0.08,
        "specificity": 0.10,
        "question_engagement": 0.07,
    }

    composite = sum(dimensions[k] * weights[k] for k in weights)

    # Generate recommendations for weak dimensions
    recommendations = []
    for dim, score in dimensions.items():
        if score < 0.5:
            rec = _get_recommendation(dim, score)
            if rec:
                recommendations.append(rec)

    return {
        "composite_score": round(composite, 3),
        "dimensions": {k: round(v, 3) for k, v in dimensions.items()},
        "weights": weights,
        "details": {
            "curiosity": curiosity,
            "pattern_interrupts": interrupts,
            "but_therefore": bt,
            "emotional_arc": emotional_arc,
            "hook": hook,
            "information_density": info_density,
        },
        "recommendations": recommendations,
    }


def _get_recommendation(dimension: str, score: float) -> dict | None:
    """Generate actionable recommendation for a weak dimension."""
    recs = {
        "curiosity_loops": {
            "issue": "Too few curiosity loops — viewers have no reason to keep watching",
            "fix": "Add 'But here's where it gets interesting...' or 'What nobody tells you is...' between sections",
        },
        "pattern_interrupts": {
            "issue": "Script feels monotone — no pattern breaks",
            "fix": "Insert a contrarian statement, rhetorical question, or tonal shift every 20-30 words",
        },
        "but_therefore_ratio": {
            "issue": "Script uses too many 'and then' sequential connectors",
            "fix": "Replace 'and then' with 'but' (conflict) or 'therefore/so' (causation)",
        },
        "emotional_arc": {
            "issue": "Flat emotional arc — no peaks and valleys",
            "fix": "Alternate between tension (fear, urgency) and release (hope, satisfaction) across segments",
        },
        "hook_strength": {
            "issue": "Hook is weak — won't stop scrolling",
            "fix": "Start with a shocking stat, open loop question, or contrarian statement in first 5 seconds",
        },
        "information_density": {
            "issue": "Either too sparse (filler) or too dense (overwhelming)",
            "fix": "Aim for 25-45 unique concepts per 100 words. Cut filler or spread dense sections",
        },
        "specificity": {
            "issue": "Too vague — lacks concrete numbers, names, or examples",
            "fix": "Replace 'a lot of money' with '₹1,37,420'. Replace 'many people' with '73% of adults'",
        },
        "question_engagement": {
            "issue": "No rhetorical questions — missing audience engagement triggers",
            "fix": "Add questions like 'But why does this happen?' or 'Sound familiar?' every 2-3 segments",
        },
    }
    rec = recs.get(dimension)
    if rec:
        return {"dimension": dimension, "score": round(score, 3), **rec}
    return None
