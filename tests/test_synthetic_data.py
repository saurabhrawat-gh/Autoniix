"""Unit tests for Synthetic Training Data Generator.

Tests: row generation functions produce valid data within expected ranges.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_training_data import (
    _gen_voice_row,
    _gen_thumbnail_row,
    _gen_delivery_row,
    _gen_feedback_row,
    NICHE_PROFILES,
)


class TestGenVoiceRow:
    def test_generates_valid_features(self):
        profile = NICHE_PROFILES["tech"]
        row = _gen_voice_row(0, "tech", profile, "CH_test")
        f = row["features"]
        assert 0.1 <= f["avg_stability"] <= 0.9
        assert 0.3 <= f["avg_similarity_boost"] <= 1.0
        assert 0.7 <= f["avg_speed"] <= 1.4
        assert f["segment_count"] >= 3
        assert f["total_duration_s"] >= 30

    def test_outcome_in_valid_range(self):
        profile = NICHE_PROFILES["health"]
        row = _gen_voice_row(1, "health", profile, "CH_test")
        o = row["outcome"]
        assert 0.10 <= o["avg_retention_rate"] <= 0.85

    def test_content_id_includes_niche(self):
        profile = NICHE_PROFILES["tech"]
        row = _gen_voice_row(5, "tech", profile, "CH_test")
        assert "tech" in row["content_id"]


class TestGenThumbnailRow:
    def test_generates_valid_features(self):
        profile = NICHE_PROFILES["entertainment"]
        row = _gen_thumbnail_row(0, "entertainment", profile, "CH_test")
        f = row["features"]
        assert isinstance(f["has_face"], bool)
        assert 0 <= f["face_area_ratio"] <= 0.5
        assert 1.0 <= f["local_composition_score"] <= 10.0
        assert f["text_word_count"] >= 1

    def test_ctr_in_range(self):
        profile = NICHE_PROFILES["tech"]
        for i in range(20):
            row = _gen_thumbnail_row(i, "tech", profile, "CH_test")
            assert 0.01 <= row["outcome"]["actual_ctr"] <= 0.20


class TestGenDeliveryRow:
    def test_valid_upload_time(self):
        profile = NICHE_PROFILES["finance"]
        row = _gen_delivery_row(0, "finance", profile, "CH_test")
        f = row["features"]
        assert 0 <= f["upload_hour_utc"] <= 23
        assert 0 <= f["upload_day_of_week"] <= 6
        assert f["tag_count"] >= 5

    def test_views_positive(self):
        profile = NICHE_PROFILES["education"]
        row = _gen_delivery_row(0, "education", profile, "CH_test")
        o = row["outcome"]
        assert o["total_views_7d"] > 0
        assert o["first_hour_views"] >= 0


class TestGenFeedbackRow:
    def test_valid_scores(self):
        profile = NICHE_PROFILES["tech"]
        row = _gen_feedback_row(0, "tech", profile, "CH_test")
        assert 3.0 <= row["idea_score"] <= 10.0
        assert 3.0 <= row["script_score"] <= 10.0
        assert row["yt_views"] > 0
        assert row["performance_tier"] in ("viral", "good", "average", "low")

    def test_engagement_rate(self):
        profile = NICHE_PROFILES["entertainment"]
        row = _gen_feedback_row(0, "entertainment", profile, "CH_test")
        assert row["engagement_rate"] >= 0


class TestNicheProfiles:
    def test_all_profiles_have_required_keys(self):
        required = {"avg_views", "std_views", "avg_ctr", "std_ctr",
                    "avg_retention", "std_retention", "common_emotions",
                    "avg_duration_s", "std_duration_s"}
        for niche, profile in NICHE_PROFILES.items():
            missing = required - set(profile.keys())
            assert not missing, f"{niche} missing keys: {missing}"

    def test_at_least_three_niches(self):
        assert len(NICHE_PROFILES) >= 3
