"""Unit tests for Assembly Service intelligence modules.

Tests: render_predictor (complexity analysis, duration estimation, simplification)
"""

from __future__ import annotations

from services_api.assembly.render_predictor import (
    compute_direction_complexity,
    estimate_render_duration,
    simplify_direction_for_retry,
)


class TestComputeDirectionComplexity:
    def test_empty_direction(self):
        result = compute_direction_complexity({})
        assert result["complexity"] == 0
        assert result["risk"] == "low"

    def test_empty_segments(self):
        result = compute_direction_complexity({"segments": []})
        assert result["complexity"] == 0
        assert result["risk"] == "low"

    def test_simple_direction(self):
        direction = {
            "segments": [
                {
                    "id": "s1",
                    "duration_ms": 5000,
                    "motion_design": {"elements": []},
                    "visual_effects": [],
                    "audio_cues": {"sfx": []},
                },
            ],
        }
        result = compute_direction_complexity(direction)
        assert result["risk"] == "low"
        assert result["complexity"] < 4

    def test_complex_direction(self, sample_direction_v3):
        result = compute_direction_complexity(sample_direction_v3)
        assert result["complexity"] > 0
        assert "risk" in result
        assert isinstance(result.get("risk_factors", []), list)

    def test_high_complexity_with_many_segments(self):
        segments = [
            {
                "id": f"s{i}",
                "duration_ms": 60000,
                "scene_preset": f"preset_{i}",
                "motion_design": {"elements": [{"type": "text"}, {"type": "emoji"}, {"type": "chart"}]},
                "visual_effects": ["blur", "vignette"],
                "audio_cues": {"sfx": ["whoosh", "ding"]},
            }
            for i in range(20)
        ]
        direction = {"segments": segments, "global_overlays": [{"type": "watermark"}, {"type": "logo"}]}
        result = compute_direction_complexity(direction)
        assert result["risk"] == "high"
        assert len(result.get("risk_factors", [])) > 0


class TestEstimateRenderDuration:
    def test_low_complexity(self):
        complexity = {"complexity": 2.0, "risk": "low"}
        duration = estimate_render_duration(complexity)
        assert isinstance(duration, (int, float))
        assert duration > 0

    def test_high_complexity_longer(self):
        low = estimate_render_duration({"complexity": 2.0, "risk": "low"})
        high = estimate_render_duration({"complexity": 10.0, "risk": "high"})
        assert high > low

    def test_zero_complexity(self):
        duration = estimate_render_duration({"complexity": 0, "risk": "low"})
        assert duration > 0


class TestSimplifyDirectionForRetry:
    def test_removes_visual_effects(self, sample_direction_v3):
        simplified = simplify_direction_for_retry(sample_direction_v3)
        for seg in simplified.get("segments", []):
            assert len(seg.get("visual_effects", [])) <= len(
                sample_direction_v3["segments"][0].get("visual_effects", [])
            )

    def test_preserves_segment_count(self, sample_direction_v3):
        simplified = simplify_direction_for_retry(sample_direction_v3)
        assert len(simplified.get("segments", [])) == len(sample_direction_v3.get("segments", []))

    def test_preserves_meta(self, sample_direction_v3):
        simplified = simplify_direction_for_retry(sample_direction_v3)
        assert "meta" in simplified

    def test_empty_direction(self):
        simplified = simplify_direction_for_retry({})
        assert isinstance(simplified, dict)
