"""Unit tests for PreventorAgent (AE-P1 / Agentic Foundation, P2).

All external I/O patched. No DB, Redis, or LLM calls.

Coverage:
  * observe(): master flag gating, missing channel_id, analyser failure,
    unresolved-HALT signal hooked into facts.
  * decide(): full rule matrix —
      - VETO when channel has unresolved HALT (and the override flag is on)
      - VETO when consecutive_failures >= threshold
      - HOLD when budget remaining below percentage threshold
      - WARN when avg quality below threshold with enough samples
      - ALLOW default
      - WARN suppressed when sample size too low
      - HOLD suppressed when budget threshold is 0 (disabled)
      - VETO-on-halt suppressed when override flag is FALSE
  * act(): writes preventor_decisions, publishes BRAIN_PREVENTOR_RISK,
    publish failure does not block persistence, decision_id propagated.
  * _has_unresolved_halt: TRUE on hit, FALSE on miss, FALSE on DB error
    (fail-open so DB blips don't auto-VETO every request).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base import AgentObservation
from src.agents.preventor import PreventorAgent, _has_unresolved_halt
from src.services.brain.analyser import ChannelSignals


def _flag_map(flags):
    async def _get_flag(key, default=None):
        return flags.get(key, default)
    return _get_flag


def _signals(**kw) -> ChannelSignals:
    defaults = dict(
        channel_id="ch1",
        avg_composite_score=8.0,
        min_composite_score=7.0,
        recent_scores=[8.0, 8.0, 8.0],
        consecutive_failures=0,
        total_recent_failures=0,
        total_delivered=10,
        total_failed=0,
        daily_budget_limit=100.0,
        daily_spend_today=10.0,
        daily_budget_remaining=90.0,
    )
    defaults.update(kw)
    return ChannelSignals(**defaults)


def _facts_from_signals(
    signals: ChannelSignals,
    *,
    content_id: str | None = "v1",
    planned_action: str = "produce_video",
    unresolved_halt: bool = False,
) -> dict:
    from dataclasses import asdict
    facts = asdict(signals)
    facts.update({
        "content_id": content_id,
        "planned_action": planned_action,
        "channel_has_unresolved_halt": unresolved_halt,
    })
    return facts


def _observation(
    signals: ChannelSignals,
    *,
    unresolved_halt: bool = False,
    content_id: str | None = "v1",
    planned_action: str = "produce_video",
) -> AgentObservation:
    facts = _facts_from_signals(
        signals,
        content_id=content_id,
        planned_action=planned_action,
        unresolved_halt=unresolved_halt,
    )
    return AgentObservation(
        scope="video" if content_id else "channel",
        scope_id=content_id or signals.channel_id,
        facts=facts,
    )


# ─────────────────────────────────────────────────────────────────────────────
# observe()
# ─────────────────────────────────────────────────────────────────────────────


class TestObserve:
    async def test_disabled_returns_none(self):
        agent = PreventorAgent()
        with patch(
            "src.agents.preventor.get_flag",
            new=AsyncMock(return_value=False),
        ):
            obs = await agent.observe({"channel_id": "ch1"})
        assert obs is None

    async def test_flag_read_failure_returns_none(self):
        agent = PreventorAgent()
        with patch(
            "src.agents.preventor.get_flag",
            new=AsyncMock(side_effect=RuntimeError("flags down")),
        ):
            obs = await agent.observe({"channel_id": "ch1"})
        assert obs is None

    async def test_missing_channel_id_returns_none(self):
        agent = PreventorAgent()
        with patch(
            "src.agents.preventor.get_flag",
            new=AsyncMock(return_value=True),
        ):
            obs = await agent.observe({"content_id": "v1"})
        assert obs is None

    async def test_analyser_failure_returns_none(self):
        agent = PreventorAgent()
        with (
            patch(
                "src.agents.preventor.get_flag",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "src.agents.preventor.analyse_channel",
                new=AsyncMock(side_effect=RuntimeError("db down")),
            ),
        ):
            obs = await agent.observe({"channel_id": "ch1"})
        assert obs is None

    async def test_attaches_unresolved_halt_signal(self):
        agent = PreventorAgent()
        with (
            patch(
                "src.agents.preventor.get_flag",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "src.agents.preventor.analyse_channel",
                new=AsyncMock(return_value=_signals()),
            ),
            patch(
                "src.agents.preventor._has_unresolved_halt",
                new=AsyncMock(return_value=True),
            ),
        ):
            obs = await agent.observe(
                {"channel_id": "ch1", "content_id": "v1"}
            )
        assert obs is not None
        assert obs.scope == "video"
        assert obs.scope_id == "v1"
        assert obs.facts["channel_has_unresolved_halt"] is True
        assert obs.facts["planned_action"] == "produce_video"

    async def test_default_planned_action(self):
        agent = PreventorAgent()
        with (
            patch(
                "src.agents.preventor.get_flag",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "src.agents.preventor.analyse_channel",
                new=AsyncMock(return_value=_signals()),
            ),
            patch(
                "src.agents.preventor._has_unresolved_halt",
                new=AsyncMock(return_value=False),
            ),
        ):
            obs = await agent.observe({"channel_id": "ch1"})
        assert obs is not None
        assert obs.facts["planned_action"] == "produce_video"
        assert obs.scope == "channel"


# ─────────────────────────────────────────────────────────────────────────────
# decide() — rule matrix
# ─────────────────────────────────────────────────────────────────────────────


_BASE_FLAGS = {
    "preventor.veto_when_channel_halted": True,
    "preventor.threshold.veto.consecutive_failures": 5,
    "preventor.threshold.hold.budget_pct_remaining": 0.05,
    "preventor.threshold.warn.min_quality_score": 6.5,
}


class TestDecide:
    async def test_veto_when_channel_halted(self):
        agent = PreventorAgent()
        obs = _observation(_signals(), unresolved_halt=True)
        with patch(
            "src.agents.preventor.get_flag",
            side_effect=_flag_map(_BASE_FLAGS),
        ):
            decision = await agent.decide(
                {"observation": obs, "memories": []}
            )
        assert decision is not None
        assert decision.decision_type == "VETO"
        assert "unresolved HALT" in decision.reasoning
        assert decision.confidence == 0.95

    async def test_halt_veto_suppressed_when_override_off(self):
        agent = PreventorAgent()
        obs = _observation(_signals(), unresolved_halt=True)
        flags = {**_BASE_FLAGS, "preventor.veto_when_channel_halted": False}
        with patch(
            "src.agents.preventor.get_flag",
            side_effect=_flag_map(flags),
        ):
            decision = await agent.decide(
                {"observation": obs, "memories": []}
            )
        assert decision is not None
        assert decision.decision_type == "ALLOW"

    async def test_veto_when_consecutive_failures_exceed_threshold(self):
        agent = PreventorAgent()
        obs = _observation(_signals(consecutive_failures=5))
        with patch(
            "src.agents.preventor.get_flag",
            side_effect=_flag_map(_BASE_FLAGS),
        ):
            decision = await agent.decide(
                {"observation": obs, "memories": []}
            )
        assert decision is not None
        assert decision.decision_type == "VETO"
        assert "consecutive_failures" in decision.reasoning

    async def test_hold_when_budget_remaining_below_threshold(self):
        agent = PreventorAgent()
        # 4% remaining < 5% threshold
        obs = _observation(
            _signals(daily_budget_limit=100.0, daily_budget_remaining=4.0),
        )
        with patch(
            "src.agents.preventor.get_flag",
            side_effect=_flag_map(_BASE_FLAGS),
        ):
            decision = await agent.decide(
                {"observation": obs, "memories": []}
            )
        assert decision is not None
        assert decision.decision_type == "HOLD"
        assert "budget" in decision.reasoning.lower()

    async def test_hold_disabled_when_budget_threshold_zero(self):
        agent = PreventorAgent()
        obs = _observation(
            _signals(daily_budget_limit=100.0, daily_budget_remaining=0.0),
        )
        flags = {
            **_BASE_FLAGS,
            "preventor.threshold.hold.budget_pct_remaining": 0,
        }
        with patch(
            "src.agents.preventor.get_flag",
            side_effect=_flag_map(flags),
        ):
            decision = await agent.decide(
                {"observation": obs, "memories": []}
            )
        # Budget gate disabled — falls through to ALLOW (no other trigger).
        assert decision is not None
        assert decision.decision_type == "ALLOW"

    async def test_warn_when_quality_below_threshold(self):
        agent = PreventorAgent()
        obs = _observation(
            _signals(
                avg_composite_score=5.0,
                recent_scores=[5.0, 5.0, 5.0],
            ),
        )
        with patch(
            "src.agents.preventor.get_flag",
            side_effect=_flag_map(_BASE_FLAGS),
        ):
            decision = await agent.decide(
                {"observation": obs, "memories": []}
            )
        assert decision is not None
        assert decision.decision_type == "WARN"
        assert "quality" in decision.reasoning.lower() or \
               "score" in decision.reasoning.lower()

    async def test_warn_suppressed_when_sample_too_small(self):
        agent = PreventorAgent()
        # Quality is bad but only 2 recent scores < 3-sample minimum.
        obs = _observation(
            _signals(
                avg_composite_score=4.0,
                recent_scores=[4.0, 4.0],
            ),
        )
        with patch(
            "src.agents.preventor.get_flag",
            side_effect=_flag_map(_BASE_FLAGS),
        ):
            decision = await agent.decide(
                {"observation": obs, "memories": []}
            )
        assert decision is not None
        assert decision.decision_type == "ALLOW"

    async def test_default_allow(self):
        agent = PreventorAgent()
        obs = _observation(_signals())
        with patch(
            "src.agents.preventor.get_flag",
            side_effect=_flag_map(_BASE_FLAGS),
        ):
            decision = await agent.decide(
                {"observation": obs, "memories": []}
            )
        assert decision is not None
        assert decision.decision_type == "ALLOW"
        # Risk signals must be carried in extras for act() to persist.
        assert "risk_signals" in decision.extras
        assert decision.extras["planned_action"] == "produce_video"


# ─────────────────────────────────────────────────────────────────────────────
# act()
# ─────────────────────────────────────────────────────────────────────────────


class TestAct:
    async def test_persists_and_publishes(self):
        agent = PreventorAgent()
        obs = _observation(_signals())
        with patch(
            "src.agents.preventor.get_flag",
            side_effect=_flag_map(_BASE_FLAGS),
        ):
            decision = await agent.decide(
                {"observation": obs, "memories": []}
            )
        assert decision is not None

        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={"id": 99})
        with (
            patch(
                "src.agents.preventor.get_pool",
                new=AsyncMock(return_value=pool),
            ),
            patch(
                "src.agents.preventor.publish",
                new=AsyncMock(return_value="event-id"),
            ) as pub,
        ):
            ack = await agent.act(decision)

        assert ack == {"id": 99}
        assert decision.extras["decision_id"] == 99
        pool.fetchrow.assert_awaited_once()
        pub.assert_awaited_once()
        # Topic and source_service correctly wired.
        kwargs = pub.await_args.kwargs
        assert kwargs["source_service"] == "preventor-agent"
        assert kwargs["payload"]["decision_id"] == 99
        assert kwargs["payload"]["decision_type"] == "ALLOW"

    async def test_publish_failure_does_not_block_persistence(self):
        agent = PreventorAgent()
        obs = _observation(_signals(consecutive_failures=5))
        with patch(
            "src.agents.preventor.get_flag",
            side_effect=_flag_map(_BASE_FLAGS),
        ):
            decision = await agent.decide(
                {"observation": obs, "memories": []}
            )
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={"id": 7})
        with (
            patch(
                "src.agents.preventor.get_pool",
                new=AsyncMock(return_value=pool),
            ),
            patch(
                "src.agents.preventor.publish",
                new=AsyncMock(side_effect=RuntimeError("redis down")),
            ),
        ):
            ack = await agent.act(decision)
        assert ack == {"id": 7}
        pool.fetchrow.assert_awaited_once()


# ─────────────────────────────────────────────────────────────────────────────
# _has_unresolved_halt
# ─────────────────────────────────────────────────────────────────────────────


class TestUnresolvedHalt:
    async def test_returns_true_on_hit(self):
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={"?column?": 1})
        with patch(
            "src.agents.preventor.get_pool",
            new=AsyncMock(return_value=pool),
        ):
            assert await _has_unresolved_halt("ch1") is True

    async def test_returns_false_on_miss(self):
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value=None)
        with patch(
            "src.agents.preventor.get_pool",
            new=AsyncMock(return_value=pool),
        ):
            assert await _has_unresolved_halt("ch1") is False

    async def test_returns_false_on_db_error(self):
        # Conservative on DB failure — fail-open rather than auto-VETO
        # the entire system on a transient blip.
        pool = MagicMock()
        pool.fetchrow = AsyncMock(side_effect=RuntimeError("db down"))
        with patch(
            "src.agents.preventor.get_pool",
            new=AsyncMock(return_value=pool),
        ):
            assert await _has_unresolved_halt("ch1") is False
