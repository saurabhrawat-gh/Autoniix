"""Unit tests for A/B Testing Framework.

Tests: deterministic assignment, experiment CRUD, analysis.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.services.experiments.ab_framework import (
    _deterministic_variant,
    create_experiment,
    assign_variant,
    analyze_experiment,
)


class TestDeterministicVariant:
    def test_consistent_assignment(self):
        v1 = _deterministic_variant("exp1", "content_001", ["control", "treatment"])
        v2 = _deterministic_variant("exp1", "content_001", ["control", "treatment"])
        assert v1 == v2

    def test_different_content_may_differ(self):
        results = set()
        for i in range(100):
            v = _deterministic_variant("exp1", f"content_{i:04d}", ["control", "treatment"])
            results.add(v)
        assert len(results) == 2

    def test_respects_weights(self):
        counts = {"a": 0, "b": 0}
        for i in range(1000):
            v = _deterministic_variant("exp_w", f"c_{i}", ["a", "b"], [0.9, 0.1])
            counts[v] += 1
        assert counts["a"] > counts["b"] * 3

    def test_single_variant(self):
        v = _deterministic_variant("exp", "content", ["only_one"])
        assert v == "only_one"

    def test_three_variants(self):
        results = set()
        for i in range(200):
            v = _deterministic_variant("exp3", f"c_{i}", ["a", "b", "c"])
            results.add(v)
        assert len(results) == 3


class TestCreateExperiment:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_creates_experiment(self, mock_pool):
        result = await create_experiment(
            "test_exp", "Testing", [{"name": "control"}, {"name": "treatment"}])
        assert result["name"] == "test_exp"
        assert result["status"] == "draft"
        mock_pool.execute.assert_called_once()


class TestAssignVariant:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_inactive_experiment(self, mock_pool, fake_record):
        mock_pool.fetchrow.return_value = fake_record(
            experiment_name="exp", variants='[{"name":"control"},{"name":"treat"}]',
            traffic_pct=100.0, status="draft")
        result = await assign_variant("exp", "content_001")
        assert result["in_experiment"] is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_active_experiment(self, mock_pool, fake_record):
        mock_pool.fetchrow.return_value = fake_record(
            experiment_name="exp",
            variants='[{"name":"control","weight":0.5,"config":{}},{"name":"treatment","weight":0.5,"config":{"use_local":true}}]',
            traffic_pct=100.0, status="active")
        result = await assign_variant("exp", "content_001", "CH_test")
        assert result["in_experiment"] is True
        assert result["variant"] in ("control", "treatment")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_no_experiment(self, mock_pool):
        mock_pool.fetchrow.return_value = None
        result = await assign_variant("nonexistent", "content_001")
        assert result["in_experiment"] is False
