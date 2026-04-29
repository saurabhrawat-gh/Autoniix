"""Unit tests for Direction Service intelligence modules.

Tests: direction_merger
"""
from __future__ import annotations

import pytest

from src.services.direction.direction_merger import (
    merge_script_direction_with_assets,
    score_merged_direction,
    SECTION_PACING,
)


class TestMergeScriptDirection:
    def test_returns_empty_when_no_hint(self, sample_channel):
        result = merge_script_direction_with_assets(
            script_v3_hint={},
            script_segments=[],
            voice_manifest={},
            asset_manifest=[],
            thumbnail_result={},
            music_data={},
            channel=sample_channel,
        )
        assert result == {}

    def test_returns_empty_when_no_segments_in_hint(self, sample_channel):
        result = merge_script_direction_with_assets(
            script_v3_hint={"meta": {}, "segments": []},
            script_segments=[],
            voice_manifest={},
            asset_manifest=[],
            thumbnail_result={},
            music_data={},
            channel=sample_channel,
        )
        assert result == {}

    def test_merges_hint_with_assets(self, sample_segments, sample_channel):
        hint = {
            "meta": {"title": "Test", "aspect_ratio": "9:16"},
            "segments": [
                {"id": "seg_001", "scene_preset": "dramatic_zoom", "camera": {"type": "zoom_in"},
                 "duration_ms": 5000, "motion_design": {"elements": []}},
                {"id": "seg_002", "scene_preset": "clean_info", "camera": {"type": "static"},
                 "duration_ms": 30000, "motion_design": {"elements": []}},
                {"id": "seg_003", "scene_preset": "cta_popup", "camera": {"type": "static"},
                 "duration_ms": 5000, "motion_design": {"elements": []}},
            ],
        }
        asset_manifest = [
            {"segment_id": "seg_001", "url": "http://minio/asset1.mp4", "type": "stock_video"},
            {"segment_id": "seg_002", "url": "http://minio/asset2.mp4", "type": "stock_video"},
        ]
        voice = {"audio_url": "http://minio/full.mp3", "segment_urls": {}}
        music = {"music_url": "http://minio/bg.mp3", "volume": 0.15}

        result = merge_script_direction_with_assets(
            hint, sample_segments, voice, asset_manifest, {}, music, sample_channel)

        assert "segments" in result
        assert len(result["segments"]) == 3
        assert "meta" in result


class TestScoreMergedDirection:
    def test_scores_complete_direction(self, sample_direction_v3):
        result = score_merged_direction(sample_direction_v3)
        assert isinstance(result, dict)
        assert "score" in result
        assert 1.0 <= result["score"] <= 10.0

    def test_scores_empty_direction(self):
        result = score_merged_direction({})
        assert result["score"] <= 3.0
        assert len(result.get("issues", [])) > 0

    def test_more_segments_scores_higher(self):
        minimal = {"segments": [{"id": "s1", "duration_ms": 5000}]}
        richer = {
            "segments": [
                {"id": "s1", "duration_ms": 5000, "camera": {"type": "zoom"},
                 "scene_preset": "a", "text_strategy": {"primary_text": "hi"},
                 "scene_overrides": {"background_url": "http://x/a.mp4"}},
                {"id": "s2", "duration_ms": 10000, "camera": {"type": "pan"},
                 "scene_preset": "b", "text_strategy": {"primary_text": "there"},
                 "scene_overrides": {"background_url": "http://x/b.mp4"}},
            ],
            "meta": {"title": "Test"},
        }
        assert score_merged_direction(richer)["score"] >= score_merged_direction(minimal)["score"]


class TestSectionPacing:
    def test_all_sections_have_required_keys(self):
        for section, pacing in SECTION_PACING.items():
            assert "min_duration_ms" in pacing, f"{section} missing min_duration_ms"
            assert "max_duration_ms" in pacing, f"{section} missing max_duration_ms"
            assert pacing["min_duration_ms"] < pacing["max_duration_ms"]
