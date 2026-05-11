"""Unit tests for Analytics Service intelligence modules.

Tests: pattern_miner (DB-dependent tests with mock pool)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from tests.conftest import FakeRecord

# Pattern miner functions are all async and DB-dependent.
# We test the logic by mocking the DB pool responses.

from src.services.analytics.pattern_miner import mine_performance_patterns


class TestMinePerformancePatterns:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_insufficient_data(self, mock_pool):
        mock_pool.fetch.return_value = [
            FakeRecord(video_id="v1", title="Test", idea_score=8.0, script_score=8.0,
                       thumbnail_score=8.0, hook_retention_score=8.0, final_score=8.0,
                       yt_views=1000, yt_likes=50, yt_comments=10,
                       engagement_rate=0.05, performance_tier="good",
                       content_mode="short", created_at="2024-01-01")
        ]
        result = await mine_performance_patterns("CH_test")
        assert result["status"] == "insufficient_data"
        assert result["videos_analyzed"] < 5

    @pytest.mark.asyncio
    async def test_returns_patterns_with_enough_data(self, mock_pool):
        rows = [
            FakeRecord(
                video_id=f"v{i}", title=f"Test {i}",
                idea_score=7.0 + i * 0.1, script_score=7.5 + i * 0.1,
                thumbnail_score=8.0, hook_retention_score=7.0 + i * 0.2,
                final_score=7.5 + i * 0.1,
                yt_views=1000 * (i + 1), yt_likes=50 * (i + 1), yt_comments=10 * (i + 1),
                engagement_rate=0.05 + i * 0.001,
                performance_tier="good" if i > 2 else "average",
                content_mode="short", created_at="2024-01-01")
            for i in range(10)
        ]
        mock_pool.fetch.return_value = rows
        result = await mine_performance_patterns("CH_test")
        assert result.get("status") != "insufficient_data"
