"""Unit tests for Model Maintenance configuration.

Tests: TRAINABLE_MODELS config, activity function definitions.
"""
from __future__ import annotations

from src.temporal_workflows.model_maintenance import TRAINABLE_MODELS


class TestTrainableModels:
    def test_all_models_have_required_keys(self):
        required = {"model_name", "service", "port", "train_endpoint",
                    "min_new_rows_table", "min_rows_for_train"}
        for m in TRAINABLE_MODELS:
            missing = required - set(m.keys())
            assert not missing, f"{m['model_name']} missing keys: {missing}"

    def test_unique_model_names(self):
        names = [m["model_name"] for m in TRAINABLE_MODELS]
        assert len(names) == len(set(names))

    def test_min_rows_positive(self):
        for m in TRAINABLE_MODELS:
            assert m["min_rows_for_train"] > 0

    def test_ports_valid(self):
        for m in TRAINABLE_MODELS:
            assert 8000 <= m["port"] <= 9000, f"{m['model_name']} port out of range"

    def test_four_trainable_models(self):
        assert len(TRAINABLE_MODELS) == 4
