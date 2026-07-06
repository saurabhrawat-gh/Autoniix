"""Unit tests for Thumbnail Service intelligence modules.

Tests: composition_analyzer (pure scoring), ctr_predictor (feature extraction)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from services_api.thumbnail.ctr_predictor import (
    extract_thumbnail_features,
    FEATURE_NAMES,
)



class TestExtractThumbnailFeatures:
    @pytest.mark.asyncio
    async def test_extracts_from_composition(self, mock_pool):
        composition = {
            "composition_score": 8.5,
            "features": {
                "has_face": True,
                "face_area_ratio": 0.15,
                "brightness": 0.65,
                "saturation": 0.55,
                "contrast": 0.45,
                "rule_of_thirds_score": 8.0,
            },
        }
        features = await extract_thumbnail_features(
            "VID_test", "CH_test", composition, variant_id=0, text_overlay="Big Text")
        assert isinstance(features, dict)
        assert features["has_face"] is True
        assert features["brightness_score"] == 0.65
        assert features["text_word_count"] == 2

    @pytest.mark.asyncio
    async def test_handles_missing_fields(self, mock_pool):
        composition = {"composition_score": 5.0}
        features = await extract_thumbnail_features("VID_test", "CH_test", composition)
        assert isinstance(features, dict)
        assert features["has_face"] is False
        assert features["local_composition_score"] == 5.0

    @pytest.mark.asyncio
    async def test_text_area_ratio(self, mock_pool):
        composition = {"composition_score": 7.0}
        features = await extract_thumbnail_features(
            "VID_test", "CH_test", composition, text_overlay="One Two Three Four")
        assert features["text_word_count"] == 4
        assert features["text_area_ratio"] > 0


class TestFeatureNames:
    def test_feature_names_defined(self):
        assert len(FEATURE_NAMES) > 0
        assert all(isinstance(n, str) for n in FEATURE_NAMES)

    def test_expected_features(self):
        assert "has_face" in FEATURE_NAMES
        assert "local_composition_score" in FEATURE_NAMES
