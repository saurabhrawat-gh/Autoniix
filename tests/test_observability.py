"""Unit tests for Intelligence Observability module.

Tests: log_decision, get_cost_savings, get_model_health_summary
"""

from __future__ import annotations

import pytest

from services_api.experiments.observability import (
    get_cost_savings,
    get_model_health_summary,
    log_decision,
    upsert_model_health,
)
from tests.conftest import FakeRecord


class TestLogDecision:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_logs_to_db(self, mock_pool):
        await log_decision(
            service_name="voice",
            decision_point="emotion_mapping",
            path_taken="local_prosody",
            content_id="VID_001",
            channel_id="CH_001",
            local_score=8.5,
            cost_saved_usd=0.003,
            latency_ms=12,
        )
        mock_pool.execute.assert_called_once()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handles_db_error(self, mock_pool):
        mock_pool.execute.side_effect = Exception("DB down")
        await log_decision("voice", "emotion_mapping", "local_prosody")


class TestGetCostSavings:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_savings_summary(self, mock_pool):
        mock_pool.fetchrow.return_value = FakeRecord(
            total_decisions=100,
            total_llm_cost=1.50,
            total_saved=4.50,
            local_decisions=80,
            llm_decisions=20,
        )
        result = await get_cost_savings(days=30)
        assert result["total_decisions"] == 100
        assert result["local_rate_pct"] == 80.0
        assert result["net_savings_usd"] == 3.0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handles_empty(self, mock_pool):
        mock_pool.fetchrow.return_value = FakeRecord(
            total_decisions=0,
            total_llm_cost=None,
            total_saved=None,
            local_decisions=0,
            llm_decisions=0,
        )
        result = await get_cost_savings(days=7)
        assert result["total_decisions"] == 0
        assert result["local_rate_pct"] == 0


class TestUpsertModelHealth:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_upserts(self, mock_pool):
        await upsert_model_health(
            model_name="voice_style_gbm",
            niche="tech",
            training_rows=50,
            accuracy_metric=0.82,
            drift_detected=False,
            status="trained",
        )
        mock_pool.execute.assert_called_once()


class TestGetModelHealthSummary:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_list(self, mock_pool):
        mock_pool.fetch.return_value = [
            FakeRecord(
                model_name="voice_style_gbm",
                niche="tech",
                training_rows=50,
                last_trained_at=None,
                accuracy_metric=0.82,
                drift_detected=False,
                drift_score=0,
                last_checked_at=None,
                status="trained",
            ),
        ]
        result = await get_model_health_summary()
        assert len(result) == 1
        assert result[0]["model_name"] == "voice_style_gbm"
