"""Asset Engine — Script v2 (Asset Generation) generator.

Transforms the base script into optimized stock footage search queries:
- NER extraction (people, places, things, concepts)
- Action verb extraction from dependency parse
- Environment/setting detection
- Mood/atmosphere keywords from emotion analysis
- Multi-query generation with synonym expansion (WordNet via NLTK)
- Negative keywords (avoid cliché/overused stock footage)
- Shot type inference from context
- Style tags from Channel DNA
- Animation mode support (stock_footage, kinetic_text, 2D, 3D recipes)
- Query relevance scoring

All computation is local. Zero API cost.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import structlog

from services_api.script.script_analyzer import (
    analyze_segment,
)

logger = structlog.get_logger()

_wordnet_ready = False
_wn_lock = asyncio.Lock()


async def _ensure_wordnet():
    """Download WordNet data if not available (one-time)."""
    global _wordnet_ready
    if _wordnet_ready:
        return
    async with _wn_lock:
        if _wordnet_ready:
            return

        def _download():
            import nltk

            try:
                from nltk.corpus import wordnet

                wordnet.synsets("test")
            except LookupError:
                nltk.download("wordnet", quiet=True)
                nltk.download("omw-1.4", quiet=True)

        await asyncio.to_thread(_download)
        _wordnet_ready = True
        logger.info("asset_engine.wordnet_ready")


def _get_synonyms(word: str, max_syns: int = 3) -> list[str]:
    """Get synonyms from WordNet (synchronous — call in thread)."""
    try:
        from nltk.corpus import wordnet

        syns = set()
        for synset in wordnet.synsets(word):
            for lemma in synset.lemmas():
                name = lemma.name().replace("_", " ")
                if name.lower() != word.lower():
                    syns.add(name)
                if len(syns) >= max_syns:
                    return list(syns)
        return list(syns)
    except Exception:
        return []


NEGATIVE_KEYWORDS = {
    "handshake",
    "business meeting",
    "happy family",
    "light bulb",
    "puzzle pieces",
    "road fork",
    "thumbs up",
    "high five",
    "group cheering",
    "fireworks celebration",
    "graduation cap",
    "target bullseye",
    "chess pieces",
    "hourglass",
    "compass",
    "flag waving",
    "globe spinning",
    "stock market graph",
    "woman typing laptop",
    "man thinking",
    "sunrise motivation",
}

SHOT_TYPE_MAP = {
    "hook": "close_up",
    "intro": "medium_shot",
    "body": "medium_shot",
    "climax": "close_up",
    "outro": "wide_shot",
}

EMOTION_MOOD_MAP = {
    "curiosity": {"mood": "mysterious", "lighting": "dim warm", "color_tone": "amber"},
    "surprise": {"mood": "dramatic", "lighting": "high contrast", "color_tone": "vivid"},
    "fear": {"mood": "dark", "lighting": "low key", "color_tone": "cold blue"},
    "hope": {"mood": "uplifting", "lighting": "golden hour", "color_tone": "warm gold"},
    "urgency": {"mood": "intense", "lighting": "harsh", "color_tone": "red orange"},
    "satisfaction": {"mood": "clean", "lighting": "bright even", "color_tone": "neutral"},
    "anger": {"mood": "aggressive", "lighting": "dramatic shadows", "color_tone": "deep red"},
    "empathy": {"mood": "soft", "lighting": "diffused", "color_tone": "pastel"},
    "neutral": {"mood": "neutral", "lighting": "natural", "color_tone": "balanced"},
}

STYLE_RECIPES = {
    "stock_footage": {
        "primary_source": "stock_video",
        "fallback_source": "stock_image",
        "overlay": "kinetic_text",
        "min_queries": 3,
    },
    "kinetic_text": {
        "primary_source": "text_animation",
        "fallback_source": "gradient_background",
        "overlay": None,
        "min_queries": 1,
    },
    "2d_animation": {
        "primary_source": "2d_scene",
        "fallback_source": "stock_image",
        "overlay": "subtitle",
        "min_queries": 2,
    },
    "3d_animation": {
        "primary_source": "3d_render",
        "fallback_source": "stock_video",
        "overlay": "subtitle",
        "min_queries": 2,
    },
}


async def extract_asset_queries(
    segment: dict,
    channel: dict | None = None,
    video_style: str = "stock_footage",
) -> dict[str, Any]:
    """Extract optimized search queries for a single segment.

    Returns primary query, alternate queries, negative keywords,
    shot type, mood data, and animation recipe if applicable.
    """
    analysis = await analyze_segment(segment)
    narration = segment.get("narration", "")
    section = segment.get("section", "body")
    scene_direction = segment.get("scene_direction", "")
    text_overlay = segment.get("text_overlay", "")

    entities = analysis["entities"]
    noun_phrases = analysis["noun_phrases"]
    key_verbs = analysis["key_verbs"]
    emotions = analysis["emotions"]
    dominant_emotion = emotions["dominant_emotion"]

    primary_parts = []
    relevant_ents = [
        e["text"] for e in entities if e["label"] in ("PERSON", "ORG", "GPE", "EVENT", "PRODUCT", "WORK_OF_ART")
    ]
    if relevant_ents:
        primary_parts.extend(relevant_ents[:2])
    elif noun_phrases:
        sorted_nps = sorted(noun_phrases, key=len, reverse=True)
        primary_parts.append(sorted_nps[0])

    if key_verbs:
        primary_parts.append(key_verbs[0])

    if scene_direction:
        scene_nouns = re.findall(
            r"\b(?:room|office|lab|street|city|forest|ocean|space|desk|"
            r"screen|phone|brain|body|heart|blood|cell|dna|book|"
            r"hospital|kitchen|gym|mountain|beach|sky)\b",
            scene_direction.lower(),
        )
        primary_parts.extend(scene_nouns[:2])

    primary_query = " ".join(primary_parts[:4]) if primary_parts else narration[:50]

    await _ensure_wordnet()
    alternate_queries = []

    for np in noun_phrases[:3]:
        core_word = np.split()[-1] if np.split() else np
        syns = await asyncio.to_thread(_get_synonyms, core_word, 2)
        for syn in syns:
            alt = np.replace(core_word, syn) if core_word in np else f"{syn} {np}"
            alternate_queries.append(alt.strip())

    mood = EMOTION_MOOD_MAP.get(dominant_emotion, EMOTION_MOOD_MAP["neutral"])
    mood_query = f"{mood['mood']} {mood['lighting']} {primary_parts[0] if primary_parts else 'abstract'}"
    alternate_queries.append(mood_query)

    b_roll = segment.get("b_roll_keywords", [])
    if b_roll:
        alternate_queries.extend(b_roll[:3])

    seen = {primary_query.lower()}
    unique_alts = []
    for q in alternate_queries:
        q_clean = q.strip()
        if q_clean.lower() not in seen and q_clean:
            seen.add(q_clean.lower())
            unique_alts.append(q_clean)
    alternate_queries = unique_alts[:5]

    shot_type = SHOT_TYPE_MAP.get(section, "medium_shot")
    if any(e["label"] in ("PERSON",) for e in entities):
        shot_type = "close_up"
    elif any(e["label"] in ("GPE", "LOC") for e in entities):
        shot_type = "wide_shot"

    neg_keywords = list(NEGATIVE_KEYWORDS & set(w.lower() for w in narration.split()))
    neg_keywords.extend(["generic", "clip art", "cartoon"])

    recipe = STYLE_RECIPES.get(video_style, STYLE_RECIPES["stock_footage"])
    animation_recipe = None

    if video_style == "kinetic_text":
        animation_recipe = {
            "type": "kinetic_typography",
            "primary_text": text_overlay or (narration[:30] + "..."),
            "animation_style": "bold_reveal" if section in ("hook", "climax") else "smooth_type",
            "background": f"gradient_{mood['color_tone']}",
        }
    elif video_style == "2d_animation":
        animation_recipe = {
            "type": "2d_scene",
            "scene_description": scene_direction or f"{mood['mood']} scene with {primary_query}",
            "character_style": "minimal_flat",
            "animation_type": "motion_graphics",
        }
    elif video_style == "3d_animation":
        animation_recipe = {
            "type": "3d_render",
            "scene_description": scene_direction or f"{mood['mood']} 3D environment",
            "lighting": mood["lighting"],
            "camera_angle": shot_type,
            "material_style": "realistic",
        }

    query_score = _score_query(primary_query, entities, noun_phrases, key_verbs)

    return {
        "segment_id": segment.get("id", ""),
        "section": section,
        "primary_query": primary_query,
        "alternate_queries": alternate_queries,
        "negative_keywords": neg_keywords[:5],
        "shot_type": shot_type,
        "mood": mood,
        "dominant_emotion": dominant_emotion,
        "entities_used": [e["text"] for e in entities[:5]],
        "noun_phrases_used": noun_phrases[:5],
        "key_verbs_used": key_verbs[:3],
        "video_style": video_style,
        "source_priority": recipe["primary_source"],
        "fallback_source": recipe["fallback_source"],
        "animation_recipe": animation_recipe,
        "query_score": query_score,
    }


def _score_query(query: str, entities: list, noun_phrases: list, verbs: list) -> float:
    """Score query quality (0-1). Higher = more likely to find relevant assets."""
    score = 0.0
    words = query.split()

    if 2 <= len(words) <= 5:
        score += 0.3
    elif 1 <= len(words) <= 7:
        score += 0.15

    if any(e["text"].lower() in query.lower() for e in entities):
        score += 0.25

    if any(np.lower() in query.lower() for np in noun_phrases):
        score += 0.2

    if any(v.lower() in query.lower() for v in verbs):
        score += 0.15

    generic_terms = {"thing", "stuff", "people", "way", "something", "everything"}
    if not any(g in query.lower().split() for g in generic_terms):
        score += 0.1

    return round(min(1.0, score), 3)


async def generate_script_assets(
    segments: list[dict],
    channel: dict | None = None,
    video_style: str = "stock_footage",
) -> dict[str, Any]:
    """Generate complete Script v2 (Asset Generation version).

    Produces per-segment search queries, shot types, mood data,
    animation recipes, and quality metrics.
    """
    asset_segments = []

    for seg in segments:
        asset_data = await extract_asset_queries(seg, channel, video_style)
        asset_segments.append(asset_data)

    total_segs = len(asset_segments)
    viable_segs = sum(1 for a in asset_segments if a["query_score"] >= 0.3)
    coverage = viable_segs / max(total_segs, 1)

    all_queries = [a["primary_query"] for a in asset_segments]
    unique_queries = len(set(q.lower() for q in all_queries))
    query_diversity = unique_queries / max(total_segs, 1)

    avg_query_score = sum(a["query_score"] for a in asset_segments) / max(total_segs, 1)

    return {
        "version": "v2_assets",
        "video_style": video_style,
        "segments": asset_segments,
        "qc": {
            "asset_coverage": round(coverage, 3),
            "coverage_ok": coverage >= 0.85,
            "query_diversity": round(query_diversity, 3),
            "avg_query_score": round(avg_query_score, 3),
            "total_queries": sum(1 + len(a["alternate_queries"]) for a in asset_segments),
            "segments_with_animation": sum(1 for a in asset_segments if a["animation_recipe"]),
        },
    }
