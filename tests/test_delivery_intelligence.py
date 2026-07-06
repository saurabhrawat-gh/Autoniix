"""Unit tests for Delivery Service intelligence modules.

Tests: seo_optimizer (title scoring, description optimization, tag suggestion)
"""
from __future__ import annotations

import pytest

from services_api.delivery.seo_optimizer import (
    score_title_seo,
    optimize_description,
    suggest_tags,
    POWER_WORDS,
    CATEGORY_MAP,
)



class TestScoreTitleSeo:
    def test_good_title(self):
        result = score_title_seo("5 Secret Tips That Scientists Don't Want You to Know")
        assert result["seo_score"] >= 7.0
        assert result["has_number"] is True
        assert result["power_words_count"] >= 1

    def test_short_title(self):
        result = score_title_seo("Tips")
        assert result["seo_score"] < 6.0
        assert result["char_count"] < 20

    def test_long_title(self):
        long_title = "This Is An Extremely Long Title That Goes On And On And On " * 3
        result = score_title_seo(long_title)
        assert "Title too long" in str(result["factors"])

    def test_question_title(self):
        result = score_title_seo("Why Do 90% of People Fail at This?")
        assert result["has_question"] is True
        assert result["seo_score"] >= 6.5

    def test_power_words_detected(self):
        result = score_title_seo("The Shocking Truth About Secret Proven Methods")
        assert result["power_words_count"] >= 2

    def test_number_bonus(self):
        with_number = score_title_seo("10 Ways to Improve Your Health")
        without = score_title_seo("Ways to Improve Your Health Today")
        assert with_number["seo_score"] >= without["seo_score"]

    def test_brackets_bonus(self):
        result = score_title_seo("How to Start a Business [2024 Guide]")
        assert "Brackets detected" in str(result["factors"])

    def test_caps_penalty(self):
        result = score_title_seo("WHY YOU SHOULD NEVER DO THIS EVER AGAIN")
        assert "spammy" in str(result["factors"]).lower() or result["seo_score"] < 8.0

    def test_score_clamped(self):
        result = score_title_seo("x")
        assert 1.0 <= result["seo_score"] <= 10.0

    def test_empty_title(self):
        result = score_title_seo("")
        assert 1.0 <= result["seo_score"] <= 10.0



class TestOptimizeDescription:
    def test_short_description_warning(self):
        result = optimize_description("Short desc", "Title", [])
        assert any("short" in s.lower() for s in result["suggestions"])

    def test_good_description(self):
        desc = "This is a detailed description about health tips. " * 15
        result = optimize_description(desc, "Health Tips", ["health", "tips"])
        assert result["score"] >= 6.0
        assert result["description_length"] > 500

    def test_missing_keywords(self):
        result = optimize_description(
            "Generic description that doesn't mention the topic at all.",
            "Quantum Physics Explained",
            ["quantum", "physics"])
        assert any("keyword" in s.lower() for s in result["suggestions"])

    def test_keyword_density(self):
        desc = "health health health health " * 10
        result = optimize_description(desc, "Health Tips", ["health"])
        assert result["keyword_density"] > 0

    def test_empty_description(self):
        result = optimize_description("", "Title", [])
        assert result["description_length"] == 0



class TestSuggestTags:
    def test_includes_existing_tags(self):
        tags = suggest_tags("Test Title", "tech", ["existing_tag"])
        assert "existing_tag" in tags

    def test_adds_title_words(self):
        tags = suggest_tags("Quantum Physics Explained Simply", "education", [])
        lowercase_tags = [t.lower() for t in tags]
        assert "quantum" in lowercase_tags
        assert "physics" in lowercase_tags

    def test_adds_niche_tags(self):
        tags = suggest_tags("Test", "tech", [])
        lowercase_tags = [t.lower() for t in tags]
        assert "technology" in lowercase_tags or "tech" in lowercase_tags

    def test_adds_bigram_phrases(self):
        tags = suggest_tags("Machine Learning Tutorial Guide", "tech", [])
        lowercase_tags = [t.lower() for t in tags]
        assert any("machine learning" in t for t in lowercase_tags) or \
               any("learning tutorial" in t for t in lowercase_tags)

    def test_max_tags(self):
        tags = suggest_tags("A B C D E F G H I J K L M N O P Q R S T", "tech", list(range(25)))
        assert len(tags) <= 30

    def test_empty_title(self):
        tags = suggest_tags("", "tech", [])
        assert isinstance(tags, list)



class TestConstants:
    def test_power_words_are_lowercase(self):
        for word in POWER_WORDS:
            assert word == word.lower(), f"Power word '{word}' should be lowercase"

    def test_category_map_has_common_niches(self):
        assert "tech" in CATEGORY_MAP
        assert "health" in CATEGORY_MAP
        assert "education" in CATEGORY_MAP
