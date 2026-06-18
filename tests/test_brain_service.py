"""Unit tests for the Brain Service (AE-P1).

Tests are fully in-process — no DB, no Redis, no Temporal.
All external I/O is patched via unittest.mock.

Coverage:
  * analyser.ChannelSignals helpers
  * engine.evaluate thresholds  (HALT / HOLD / NUDGE / no-decision)
  * consumer.handle_pipeline_event dispatch
  * resolver.resolve_stale logic
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.brain.analyser import ChannelSignals


# ─────────────────────────────────────────────────────────────────────────────
# ChannelSignals helpers
# ─────────────────────────────────────────────────────────────────────────────


class TestChannelSignals:
    def _signals(self, **kwargs) -> ChannelSignals:
        defaults = dict(
            channel_id="BS001",
            avg_composite_score=8.0,
            min_composite_score=7.0,
            recent_scores=[8.0, 8.5, 7.5],
            avg_cost_per_video=0.50,
            latest_cost=0.55,
            cost_spike_factor=1.1,
            consecutive_failures=0,
            total_recent_failures=0,
            total_delivered=10,
            total_failed=0,
            daily_budget_limit=10.0,
            daily_spend_today=5.0,
            daily_budget_remaining=5.0,
        )
        defaults.update(kwargs)
        return ChannelSignals(**defaults)

    def test_is_new_channel_no_deliveries(self):
        s = self._signals(total_delivered=0)
        assert s.is_new_channel is True

    def test_is_new_channel_with_deliveries(self):
        s = self._signals(total_delivered=3)
        assert s.is_new_channel is False

    def test_budget_exhausted_true(self):
        s = self._signals(daily_budget_limit=10.0, daily_spend_today=10.0, daily_budget_remaining=0.0)
        assert s.budget_exhausted is True

    def test_budget_exhausted_no_limit(self):
        s = self._signals(daily_budget_limit=0.0, daily_spend_today=999.0, daily_budget_remaining=0.0)
        assert s.budget_exhausted is False

    def test_budget_not_exhausted(self):
        s = self._signals(daily_budget_limit=10.0, daily_spend_today=5.0, daily_budget_remaining=5.0)
        assert s.budget_exhausted is False


# ─────────────────────────────────────────────────────────────────────────────
# Decision engine
# ─────────────────────────────────────────────────────────────────────────────


def _make_signals(**kwargs) -> ChannelSignals:
    defaults = dict(
        channel_id="BS001",
        avg_composite_score=8.5,
        min_composite_score=8.0,
        recent_scores=[8.5, 9.0, 8.0, 8.5, 9.5],
        avg_cost_per_video=0.50,
        latest_cost=0.52,
        cost_spike_factor=1.04,
        consecutive_failures=0,
        total_recent_failures=0,
        total_delivered=20,
        total_failed=1,
        daily_budget_limit=20.0,
        daily_spend_today=5.0,
        daily_budget_remaining=15.0,
    )
    defaults.update(kwargs)
    return ChannelSignals(**defaults)


_FAKE_DECISION = {
    "id": 1,
    "decision_type": "HALT",
    "scope": "channel",
    "scope_id": "BS001",
    "directive": {"action": "HALT"},
    "reasoning": "test",
    "confidence": 0.95,
    "created_at": None,
}


class TestDecisionEngine:
    @pytest.fixture(autouse=True)
    def patch_write(self):
        """Patch _write_decision so tests never touch the DB."""
        with patch(
            "src.services.brain.engine._write_decision",
            new=AsyncMock(return_value=_FAKE_DECISION),
        ) as mock:
            self._write = mock
            yield

    @pytest.fixture(autouse=True)
    def patch_flags(self):
        """Return default threshold values from feature flags."""
        defaults = {
            "brain.threshold.halt.consecutive_failures": 3,
            "brain.threshold.halt.min_quality_score": 5.0,
            "brain.threshold.hold.cost_spike_factor": 3.0,
            "brain.threshold.hold.budget_pct_remaining": 0.05,
            "brain.threshold.nudge.avg_quality_score": 7.0,
        }

        async def _flag(key, default=None):
            return defaults.get(key, default)

        with patch("src.services.brain.engine.get_flag", side_effect=_flag):
            yield

    async def test_no_decision_healthy_channel(self):
        from src.services.brain.engine import _evaluate
        result = await _evaluate(_make_signals(), None)
        assert result is None
        self._write.assert_not_called()

    async def test_skip_new_channel(self):
        from src.services.brain.engine import _evaluate
        result = await _evaluate(_make_signals(total_delivered=0), None)
        assert result is None
        self._write.assert_not_called()

    async def test_halt_consecutive_failures(self):
        from src.services.brain.engine import _evaluate
        result = await _evaluate(_make_signals(consecutive_failures=3), "vid-1")
        assert result == _FAKE_DECISION
        call_kwargs = self._write.call_args.kwargs
        assert call_kwargs["decision_type"] == "HALT"
        assert call_kwargs["directive"]["reason"] == "consecutive_failures"

    async def test_halt_quality_floor(self):
        from src.services.brain.engine import _evaluate
        s = _make_signals(
            avg_composite_score=4.0,
            min_composite_score=3.0,
            recent_scores=[4.0, 4.5, 3.5],
        )
        result = await _evaluate(s, None)
        assert result == _FAKE_DECISION
        call_kwargs = self._write.call_args.kwargs
        assert call_kwargs["decision_type"] == "HALT"
        assert call_kwargs["directive"]["reason"] == "quality_floor_breach"

    async def test_halt_quality_insufficient_data(self):
        """Quality HALT requires >= 3 data points."""
        from src.services.brain.engine import _evaluate
        s = _make_signals(
            avg_composite_score=3.0,
            recent_scores=[3.0, 2.5],  # only 2 — not enough
        )
        result = await _evaluate(s, None)
        assert result is None

    async def test_hold_cost_spike(self):
        from src.services.brain.engine import _evaluate
        s = _make_signals(
            avg_cost_per_video=0.50,
            latest_cost=1.60,
            cost_spike_factor=3.2,
        )
        result = await _evaluate(s, None)
        assert result == _FAKE_DECISION
        call_kwargs = self._write.call_args.kwargs
        assert call_kwargs["decision_type"] == "HOLD"
        assert call_kwargs["directive"]["reason"] == "cost_spike"

    async def test_hold_budget_exhausted(self):
        from src.services.brain.engine import _evaluate
        s = _make_signals(
            daily_budget_limit=10.0,
            daily_spend_today=9.6,
            daily_budget_remaining=0.4,  # 4% left < 5% threshold
        )
        result = await _evaluate(s, None)
        assert result == _FAKE_DECISION
        call_kwargs = self._write.call_args.kwargs
        assert call_kwargs["decision_type"] == "HOLD"
        assert call_kwargs["directive"]["reason"] == "budget_exhausted"

    async def test_nudge_below_quality_target(self):
        from src.services.brain.engine import _evaluate
        s = _make_signals(
            avg_composite_score=6.5,
            recent_scores=[6.5, 6.0, 7.0, 6.5, 6.5],
        )
        result = await _evaluate(s, None)
        assert result == _FAKE_DECISION
        call_kwargs = self._write.call_args.kwargs
        assert call_kwargs["decision_type"] == "NUDGE"

    async def test_nudge_requires_min_5_scores(self):
        """NUDGE is not issued with fewer than 5 data points."""
        from src.services.brain.engine import _evaluate
        s = _make_signals(
            avg_composite_score=6.5,
            recent_scores=[6.5, 6.0, 7.0, 6.5],  # only 4
        )
        result = await _evaluate(s, None)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Consumer
# ─────────────────────────────────────────────────────────────────────────────


class TestConsumer:
    @pytest.fixture(autouse=True)
    def patch_deps(self):
        async def _flag(key, default=None):
            # Force the legacy (non-agent) consumer path for these tests.
            if key == "brain.memory_recall.enabled":
                return False
            # advisory_mode TRUE keeps Temporal signalling disabled.
            return True

        with (
            patch("src.services.brain.consumer.analyse_channel", new=AsyncMock()),
            patch("src.services.brain.consumer.evaluate", new=AsyncMock(return_value=None)),
            patch("src.services.brain.consumer.publish", new=AsyncMock()),
            patch("src.services.brain.consumer.get_flag", side_effect=_flag),
        ):
            yield

    def _envelope(self, topic="pipeline.video.complete", **payload_kwargs):
        return {
            "topic": topic,
            "event_id": "test-event-id",
            "scope": "channel",
            "scope_id": "BS001",
            "payload": {"content_id": "vid-1", "channel_id": "BS001", **payload_kwargs},
            "confidence": None,
            "timestamp": "2026-06-01T00:00:00+00:00",
            "source_service": "test",
        }

    async def test_missing_channel_id_skips(self):
        from src.services.brain.consumer import handle_pipeline_event
        envelope = self._envelope()
        envelope["scope_id"] = ""
        envelope["payload"]["channel_id"] = ""
        await handle_pipeline_event(envelope)
        import src.services.brain.consumer as _c
        _c.analyse_channel.assert_not_called()

    async def test_no_decision_skips_publish(self):
        import src.services.brain.consumer as _c
        _c.evaluate.return_value = None
        from src.services.brain.consumer import handle_pipeline_event
        await handle_pipeline_event(self._envelope())
        _c.publish.assert_not_called()

    async def test_decision_triggers_publish(self):
        import src.services.brain.consumer as _c
        _c.evaluate.return_value = {
            "id": 42,
            "decision_type": "HALT",
            "directive": {"action": "HALT"},
            "reasoning": "test",
            "confidence": 0.95,
        }
        from src.services.brain.consumer import handle_pipeline_event
        await handle_pipeline_event(self._envelope())
        _c.publish.assert_awaited_once()
        call_kwargs = _c.publish.call_args.kwargs
        assert call_kwargs["payload"]["decision_type"] == "HALT"


# ─────────────────────────────────────────────────────────────────────────────
# Resolver
# ─────────────────────────────────────────────────────────────────────────────


class TestResolver:
    @pytest.fixture(autouse=True)
    def patch_deps(self):
        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(return_value={"resolved_count": 2})
        with (
            patch("src.services.brain.resolver.get_pool", new=AsyncMock(return_value=mock_pool)),
            patch("src.services.brain.resolver.get_flag", new=AsyncMock(return_value=7)),
        ):
            self._pool = mock_pool
            yield

    async def test_resolve_stale_returns_count(self):
        from src.services.brain.resolver import resolve_stale
        count = await resolve_stale()
        assert count == 2

    async def test_resolve_stale_db_error_returns_zero(self):
        self._pool.fetchrow.side_effect = RuntimeError("db down")
        from src.services.brain.resolver import resolve_stale
        count = await resolve_stale()
        assert count == 0
