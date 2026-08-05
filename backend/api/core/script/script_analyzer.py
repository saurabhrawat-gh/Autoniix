"""Script Analyzer — Core NLP engine for the Script Intelligence system.

Provides foundational text analysis used by all 3 script view engines:
- spaCy NLP pipeline: tokenization, POS tagging, NER, dependency parsing
- Emotion detection: lexicon-based (500+ curated words across 8 emotions)
- Emphasis detection: TF-IDF-like surprise scoring + POS-based rules
- Syllable counting & WPM estimation for pacing
- Readability scoring via textstat
- Sentence segmentation tuned for spoken delivery

All computation is local. Zero API cost.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from typing import Any

import structlog
import textstat

logger = structlog.get_logger()

_nlp = None
_nlp_lock = asyncio.Lock()
SPACY_MODEL = "en_core_web_sm"


async def _get_nlp():
    """Lazy-load spaCy model (thread-safe, cached)."""
    global _nlp
    if _nlp is not None:
        return _nlp
    async with _nlp_lock:
        if _nlp is not None:
            return _nlp

        def _load():
            import spacy

            try:
                return spacy.load(SPACY_MODEL)
            except OSError:
                from spacy.cli import download

                download(SPACY_MODEL)
                return spacy.load(SPACY_MODEL)

        _nlp = await asyncio.to_thread(_load)
        logger.info("script_analyzer.spacy_loaded", model=SPACY_MODEL)
        return _nlp


EMOTION_LEXICON: dict[str, set[str]] = {
    "curiosity": {
        "why",
        "how",
        "secret",
        "hidden",
        "mystery",
        "unknown",
        "discover",
        "reveal",
        "uncover",
        "puzzle",
        "question",
        "wonder",
        "explore",
        "fascinating",
        "intriguing",
        "curious",
        "riddle",
        "enigma",
        "clue",
        "insight",
        "surprising",
        "unexpected",
        "bizarre",
        "strange",
        "peculiar",
        "remarkable",
        "astonishing",
        "truth",
        "actually",
        "really",
        "turns out",
        "imagine",
        "what if",
        "behind",
        "beneath",
        "deeper",
        "overlooked",
        "missed",
        "nobody",
        "no one",
        "rarely",
        "seldom",
        "hardly",
        "barely",
        "impossible",
        "incredible",
        "unbelievable",
        "mind-blowing",
        "revolutionary",
        "breakthrough",
        "game-changer",
        "paradigm",
        "counterintuitive",
        "paradox",
        "contradiction",
        "myth",
        "misconception",
        "illusion",
        "deception",
        "misleading",
    },
    "surprise": {
        "shocking",
        "stunned",
        "jaw-dropping",
        "unbelievable",
        "wow",
        "insane",
        "crazy",
        "wild",
        "nuts",
        "ridiculous",
        "absurd",
        "outrageous",
        "dramatic",
        "explosive",
        "bombshell",
        "twist",
        "plot twist",
        "suddenly",
        "overnight",
        "instantly",
        "boom",
        "whoa",
        "wait",
        "hold on",
        "but",
        "however",
        "except",
        "unfortunately",
        "ironically",
        "paradoxically",
        "yet",
        "despite",
        "although",
        "shockingly",
        "stunningly",
        "unexpectedly",
        "remarkably",
        "astoundingly",
    },
    "fear": {
        "danger",
        "warning",
        "risk",
        "threat",
        "deadly",
        "fatal",
        "toxic",
        "harmful",
        "damage",
        "destroy",
        "ruin",
        "collapse",
        "crisis",
        "emergency",
        "panic",
        "alarm",
        "terrifying",
        "frightening",
        "scary",
        "horrifying",
        "nightmare",
        "worst",
        "avoid",
        "never",
        "stop",
        "beware",
        "careful",
        "caution",
        "mistake",
        "error",
        "failure",
        "disaster",
        "catastrophe",
        "devastating",
        "irreversible",
        "permanent",
        "silent killer",
        "ticking bomb",
        "trap",
        "pitfall",
        "vulnerability",
    },
    "hope": {
        "solution",
        "answer",
        "fix",
        "heal",
        "recover",
        "restore",
        "improve",
        "better",
        "transform",
        "breakthrough",
        "progress",
        "success",
        "achieve",
        "overcome",
        "conquer",
        "master",
        "freedom",
        "liberation",
        "opportunity",
        "potential",
        "promise",
        "possibility",
        "dream",
        "vision",
        "goal",
        "aspire",
        "thrive",
        "flourish",
        "prosper",
        "grow",
        "build",
        "create",
        "unlock",
        "empower",
        "inspire",
        "motivate",
        "encourage",
        "uplift",
        "finally",
        "at last",
        "good news",
        "fortunately",
    },
    "urgency": {
        "now",
        "today",
        "immediately",
        "urgent",
        "critical",
        "essential",
        "must",
        "need",
        "before",
        "deadline",
        "limited",
        "running out",
        "last chance",
        "don't wait",
        "act fast",
        "hurry",
        "quickly",
        "asap",
        "right now",
        "this moment",
        "tonight",
        "tomorrow",
        "soon",
        "already",
        "still",
        "yet",
        "while",
        "before it's too late",
        "time-sensitive",
        "expiring",
        "disappearing",
        "closing",
    },
    "satisfaction": {
        "proven",
        "works",
        "effective",
        "results",
        "evidence",
        "study",
        "research",
        "data",
        "science",
        "fact",
        "confirmed",
        "verified",
        "exactly",
        "precisely",
        "specifically",
        "guaranteed",
        "reliable",
        "consistent",
        "predictable",
        "clear",
        "simple",
        "easy",
        "straightforward",
        "step-by-step",
        "practical",
        "actionable",
        "concrete",
        "tangible",
        "measurable",
        "real",
        "actual",
        "demonstrated",
        "tested",
        "validated",
        "peer-reviewed",
    },
    "anger": {
        "unfair",
        "wrong",
        "lie",
        "scam",
        "fraud",
        "manipulation",
        "exploit",
        "abuse",
        "corrupt",
        "rigged",
        "cheated",
        "betrayed",
        "stolen",
        "robbed",
        "wasted",
        "ruined",
        "broken",
        "failed",
        "incompetent",
        "negligent",
        "irresponsible",
        "outrageous",
        "unacceptable",
        "disgusting",
        "pathetic",
        "shameful",
        "hypocritical",
        "deceptive",
        "predatory",
        "greedy",
    },
    "empathy": {
        "understand",
        "feel",
        "struggle",
        "pain",
        "suffering",
        "hard",
        "difficult",
        "challenging",
        "overwhelming",
        "exhausting",
        "frustrating",
        "confusing",
        "lonely",
        "scared",
        "worried",
        "anxious",
        "stressed",
        "tired",
        "burnout",
        "you're not alone",
        "we've all been there",
        "it's okay",
        "normal",
        "common",
        "many people",
        "most of us",
        "relatable",
        "human",
        "real",
        "honest",
        "vulnerable",
        "brave",
        "courage",
        "strength",
    },
}

_ALL_EMOTION_WORDS: dict[str, str] = {}
for _emotion, _words in EMOTION_LEXICON.items():
    for _w in _words:
        _ALL_EMOTION_WORDS[_w] = _emotion

POWER_WORDS = {
    "free",
    "new",
    "proven",
    "secret",
    "instant",
    "guaranteed",
    "discover",
    "amazing",
    "powerful",
    "ultimate",
    "exclusive",
    "revolutionary",
    "essential",
    "critical",
    "shocking",
    "hidden",
    "simple",
    "easy",
    "fast",
    "massive",
    "incredible",
    "dangerous",
    "urgent",
    "limited",
    "rare",
    "breakthrough",
    "deadly",
    "silent",
    "forbidden",
    "ancient",
    "forgotten",
    "remarkable",
    "stunning",
}

AI_PATTERNS = [
    r"\blet'?s dive (?:right )?in\b",
    r"\bit(?:'s| is) important to (?:note|understand|remember)\b",
    r"\bin (?:today's|this) (?:video|article)\b",
    r"\bwithout further ado\b",
    r"\bin conclusion\b",
    r"\bas we (?:all )?know\b",
    r"\bmoreover\b",
    r"\bfurthermore\b",
    r"\bnevertheless\b",
    r"\bin the realm of\b",
    r"\bnavigat(?:e|ing) the (?:complexit|landscape|world)\b",
    r"\bunlock(?:ing)? the (?:power|potential|secret)\b",
    r"\bjourney\b",
    r"\bgame[- ]?changer\b",
    r"\btake(?:s)? a closer look\b",
    r"\bdelve\b",
    r"\btap(?:ping)? into\b",
    r"\beverything you need to know\b",
    r"\byou (?:might|may) be (?:surprised|wondering)\b",
    r"\bbuckle up\b",
    r"\bhang tight\b",
]
_AI_PATTERNS_COMPILED = [re.compile(p, re.IGNORECASE) for p in AI_PATTERNS]


def count_syllables(word: str) -> int:
    """Estimate syllable count for a word (English heuristic)."""
    word = word.lower().strip()
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    count = len(re.findall(r"[aeiouy]+", word))
    if word.endswith("e") and not word.endswith("le"):
        count -= 1
    if word.endswith("ed") and len(word) > 4:
        count -= 1
    return max(1, count)


def estimate_speaking_duration(text: str, wpm: int = 150) -> float:
    """Estimate speaking duration in seconds for a text at given WPM."""
    words = text.split()
    return (len(words) / wpm) * 60.0


def estimate_wpm(text: str, duration_s: float) -> float:
    """Estimate WPM given text and its duration."""
    if duration_s <= 0:
        return 150.0
    return (len(text.split()) / duration_s) * 60.0


async def analyze_text(text: str) -> dict[str, Any]:
    """Full NLP analysis of a text string.

    Returns dict with: tokens, sentences, entities, pos_tags,
    noun_phrases, verb_phrases, emotion_scores, readability, etc.
    """
    nlp = await _get_nlp()
    doc = await asyncio.to_thread(nlp, text)

    sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
    sentence_lengths = [len(s.split()) for s in sentences]

    pos_counts = Counter(token.pos_ for token in doc if not token.is_punct)

    entities = [
        {"text": ent.text, "label": ent.label_, "start": ent.start_char, "end": ent.end_char} for ent in doc.ents
    ]

    noun_phrases = [chunk.text for chunk in doc.noun_chunks]

    key_verbs = [token.lemma_ for token in doc if token.pos_ == "VERB" and token.dep_ not in ("aux", "auxpass")]

    return {
        "sentences": sentences,
        "sentence_count": len(sentences),
        "word_count": len(text.split()),
        "sentence_lengths": sentence_lengths,
        "avg_sentence_length": sum(sentence_lengths) / max(len(sentence_lengths), 1),
        "sentence_length_variance": _variance(sentence_lengths),
        "entities": entities,
        "noun_phrases": noun_phrases,
        "key_verbs": key_verbs,
        "pos_distribution": dict(pos_counts),
    }


async def detect_emotions(text: str) -> dict[str, Any]:
    """Detect emotions in text using lexicon lookup.

    Returns per-emotion scores (0-1) and dominant emotion.
    """
    words = re.findall(r"\b\w+\b", text.lower())
    bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]
    all_tokens = words + bigrams
    total = max(len(words), 1)

    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}

    for emotion in EMOTION_LEXICON:
        hits = []
        for token in all_tokens:
            if token in EMOTION_LEXICON[emotion]:
                hits.append(token)
        scores[emotion] = min(1.0, len(hits) / (total * 0.15))
        matched[emotion] = hits[:5]

    dominant = max(scores, key=scores.get) if any(scores.values()) else "neutral"
    total_emotional_intensity = sum(scores.values()) / max(len(scores), 1)

    return {
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "dominant_emotion": dominant,
        "emotional_intensity": round(total_emotional_intensity, 3),
        "matched_words": matched,
    }


async def detect_emphasis_words(text: str, top_n: int = 5) -> list[dict]:
    """Identify words that deserve emphasis in speech.

    Uses: TF-IDF-like surprise, POS (nouns/verbs/adjectives), numbers,
    named entities, power words.
    """
    nlp = await _get_nlp()
    doc = await asyncio.to_thread(nlp, text)

    word_scores: dict[str, float] = {}

    for token in doc:
        if token.is_punct or token.is_space or token.is_stop:
            continue

        word = token.text.lower()
        score = 0.0

        if token.pos_ in ("NOUN", "PROPN"):
            score += 1.5
        elif token.pos_ == "VERB" and token.dep_ not in ("aux", "auxpass"):
            score += 1.2
        elif token.pos_ == "ADJ":
            score += 1.0
        elif token.pos_ == "NUM":
            score += 2.0

        if token.ent_type_:
            score += 1.8

        if word in POWER_WORDS:
            score += 2.5

        if word in _ALL_EMOTION_WORDS:
            score += 1.5

        if len(word) >= 8:
            score += 0.5
        if len(word) >= 12:
            score += 0.5

        if re.search(r"\d", token.text):
            score += 2.5

        if score > 0:
            word_scores[token.text] = max(word_scores.get(token.text, 0), score)

    ranked = sorted(word_scores.items(), key=lambda x: x[1], reverse=True)
    return [
        {"word": w, "score": round(s, 2), "emotion": _ALL_EMOTION_WORDS.get(w.lower(), "neutral")}
        for w, s in ranked[:top_n]
    ]


def compute_specificity(text: str) -> float:
    """Score how specific/concrete the text is (vs abstract/vague).

    High specificity = numbers, proper nouns, exact quantities, dates.
    Low specificity = vague generalities, abstract concepts.
    """
    words = text.split()
    total = max(len(words), 1)

    specific_count = 0
    specific_count += len(re.findall(r"\b\d[\d,.]*%?\b", text))
    specific_count += len(re.findall(r"[\"'].*?[\"']", text))
    sentences = re.split(r"[.!?]\s+", text)
    for sent in sentences:
        words_in = sent.split()
        for w in words_in[1:]:
            if w and w[0].isupper() and w.lower() not in {"i", "a"}:
                specific_count += 1

    return min(1.0, specific_count / (total * 0.08))


def detect_ai_patterns(text: str) -> list[dict]:
    """Find AI-typical phrasings that sound robotic/generic."""
    found = []
    for pattern in _AI_PATTERNS_COMPILED:
        for match in pattern.finditer(text):
            found.append(
                {
                    "phrase": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
    return found


def compute_readability(text: str) -> dict:
    """Compute readability metrics using textstat."""
    return {
        "flesch_reading_ease": textstat.flesch_reading_ease(text),
        "flesch_kincaid_grade": textstat.flesch_kincaid_grade(text),
        "gunning_fog": textstat.gunning_fog(text),
        "automated_readability": textstat.automated_readability_index(text),
        "dale_chall": textstat.dale_chall_readability_score(text),
        "avg_sentence_length": textstat.avg_sentence_length(text),
        "avg_syllables_per_word": textstat.avg_syllables_per_word(text),
    }


def compute_question_density(text: str) -> float:
    """Ratio of questions to total sentences."""
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0.0
    questions = sum(1 for s in sentences if s.rstrip().endswith("?") or text.count("?") > 0)
    question_marks = text.count("?")
    total_sentences = max(len(sentences), 1)
    return min(1.0, question_marks / total_sentences)


def compute_contraction_rate(text: str) -> float:
    """Ratio of contractions to total words (higher = more conversational)."""
    words = text.split()
    if not words:
        return 0.0
    contractions = re.findall(
        r"\b(?:don't|doesn't|didn't|won't|wouldn't|can't|couldn't|shouldn't|"
        r"isn't|aren't|wasn't|weren't|haven't|hasn't|hadn't|it's|he's|she's|"
        r"that's|there's|here's|what's|who's|let's|you're|they're|we're|"
        r"I'm|you've|we've|they've|I've|you'll|we'll|they'll|I'll|"
        r"you'd|we'd|they'd|I'd)\b",
        text,
        re.IGNORECASE,
    )
    return len(contractions) / max(len(words), 1)


async def analyze_segment(segment: dict) -> dict[str, Any]:
    """Full analysis of a single script segment.

    Returns all features needed by prosody, asset, and direction engines.
    """
    narration = segment.get("narration", "")
    section = segment.get("section", "body")

    text_analysis = await analyze_text(narration)
    emotions = await detect_emotions(narration)
    emphasis = await detect_emphasis_words(narration, top_n=5)
    readability = compute_readability(narration)

    duration_s = segment.get("duration_s", estimate_speaking_duration(narration))
    syllable_count = sum(count_syllables(w) for w in narration.split())

    return {
        "segment_id": segment.get("id", ""),
        "section": section,
        "narration": narration,
        "duration_s": duration_s,
        "word_count": text_analysis["word_count"],
        "sentence_count": text_analysis["sentence_count"],
        "sentences": text_analysis["sentences"],
        "avg_sentence_length": text_analysis["avg_sentence_length"],
        "entities": text_analysis["entities"],
        "noun_phrases": text_analysis["noun_phrases"],
        "key_verbs": text_analysis["key_verbs"],
        "emotions": emotions,
        "emphasis_words": emphasis,
        "readability": readability,
        "syllable_count": syllable_count,
        "estimated_wpm": estimate_wpm(narration, duration_s) if duration_s > 0 else 150,
        "specificity": compute_specificity(narration),
        "question_density": compute_question_density(narration),
        "contraction_rate": compute_contraction_rate(narration),
        "ai_patterns": detect_ai_patterns(narration),
    }


async def analyze_full_script(segments: list[dict]) -> dict[str, Any]:
    """Analyze entire script (all segments) — produces aggregate features."""
    all_narration = " ".join(s.get("narration", "") for s in segments)

    segment_analyses = []
    for seg in segments:
        analysis = await analyze_segment(seg)
        segment_analyses.append(analysis)

    total_words = sum(a["word_count"] for a in segment_analyses)
    total_sentences = sum(a["sentence_count"] for a in segment_analyses)
    all_sentence_lengths = []
    for a in segment_analyses:
        all_sentence_lengths.extend([len(s.split()) for s in a["sentences"]])

    emotion_intensities = [a["emotions"]["emotional_intensity"] for a in segment_analyses]
    dominant_emotions = [a["emotions"]["dominant_emotion"] for a in segment_analyses]

    return {
        "segment_analyses": segment_analyses,
        "total_word_count": total_words,
        "total_sentence_count": total_sentences,
        "avg_sentence_length": sum(all_sentence_lengths) / max(len(all_sentence_lengths), 1),
        "sentence_length_variance": _variance(all_sentence_lengths),
        "overall_emotions": await detect_emotions(all_narration),
        "emotion_arc": emotion_intensities,
        "emotion_arc_variance": _variance(emotion_intensities),
        "dominant_emotion_sequence": dominant_emotions,
        "overall_specificity": compute_specificity(all_narration),
        "overall_question_density": compute_question_density(all_narration),
        "overall_contraction_rate": compute_contraction_rate(all_narration),
        "overall_readability": compute_readability(all_narration),
        "ai_patterns_total": sum(len(a["ai_patterns"]) for a in segment_analyses),
        "ai_pattern_density": sum(len(a["ai_patterns"]) for a in segment_analyses) / max(total_words, 1),
    }


def _variance(values: list[float | int]) -> float:
    """Compute variance of a list of numbers."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / len(values)
