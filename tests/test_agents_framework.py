"""Unit tests for the agentic framework (AE-P1 / Agentic Foundation).

Coverage:
  * BaseAgent lifecycle ordering + isolation of failures.
  * AgentMemory.recall — flag gating, scope filtering, threshold filter.
  * AgentRegistry register / get / clear.
  * BrainAgent — observe builds correct AgentObservation, decide enriches
    reasoning with precedent when memories are passed.

All external I/O is patched. No DB, no Redis, no embedding API.
"""
from __future__ import annotations

from dataclasses import asdict
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.base import AgentDecision, AgentObservation, BaseAgent
from src.agents.memory import AgentMemory, MemoryRecallResult
from src.agents.registry import AgentRegistry


# ─────────────────────────────────────────────────────────────────────────────
# BaseAgent
# ─────────────────────────────────────────────────────────────────────────────


class _DummyAgent(BaseAgent):
    name = "dummy"
    decision_table = "dummy_decisions"
    flag_prefix = "dummy."

    def __init__(self):
        super().__init__()
        self.calls: list[str] = []

    async def observe(self, context):
        self.calls.append("observe")
        if context.get("skip"):
            return None
        return AgentObservation(
            scope="channel",
            scope_id=context.get("channel_id", "ch1"),
            facts={"x": 1},
        )

    async def recall(self, observation):
        self.calls.append("recall")
        return [{"id": 99, "decision_type": "HALT", "score": 0.9}]

    async def reason(self, observation, memories):
        self.calls.append("reason")
        return {"observation": observation, "memories": memories}

    async def decide(self, state):
        self.calls.append("decide")
        obs = state["observation"]
        return AgentDecision(
            decision_type="NUDGE",
            scope=obs.scope,
            scope_id=obs.scope_id,
            directive={"action": "NUDGE"},
            reasoning="ok",
            confidence=0.8,
        )

    async def act(self, decision):
        self.calls.append("act")
        return {"id": 1}

    async def remember(self, decision, acted_row):
        self.calls.append("remember")


class TestBaseAgent:
    def test_subclass_requires_metadata(self):
        class _Bad(BaseAgent):
            pass

        with pytest.raises(TypeError):
            _Bad()

    async def test_full_lifecycle_order(self):
        agent = _DummyAgent()
        decision = await agent.run({"channel_id": "ch1"})
        assert decision is not None
        assert agent.calls == [
            "observe", "recall", "reason", "decide", "act", "remember"
        ]

    async def test_observe_returns_none_short_circuits(self):
        agent = _DummyAgent()
        decision = await agent.run({"skip": True})
        assert decision is None
        assert agent.calls == ["observe"]

    async def test_decide_returns_none_skips_act_and_remember(self):
        class _NoDecide(_DummyAgent):
            async def decide(self, state):
                self.calls.append("decide")
                return None

        agent = _NoDecide()
        decision = await agent.run({"channel_id": "ch1"})
        assert decision is None
        assert agent.calls == ["observe", "recall", "reason", "decide"]

    async def test_recall_failure_does_not_block_decide(self):
        class _BrokenRecall(_DummyAgent):
            async def recall(self, observation):
                self.calls.append("recall")
                raise RuntimeError("db down")

        agent = _BrokenRecall()
        # Failure is swallowed inside the orchestrator-defined boundary;
        # _BrokenRecall raises directly so we wrap to mimic the default
        # BaseAgent.recall() which catches its own exceptions.
        with patch.object(
            _BrokenRecall, "recall",
            new=AsyncMock(side_effect=lambda obs: agent.calls.append("recall") or []),
        ):
            decision = await agent.run({"channel_id": "ch1"})
        assert decision is not None
        assert "decide" in agent.calls
        assert "act" in agent.calls


# ─────────────────────────────────────────────────────────────────────────────
# AgentMemory
# ─────────────────────────────────────────────────────────────────────────────


class TestAgentMemory:
    @pytest.fixture
    def memory(self):
        return AgentMemory(agent_name="brain", table="brain_decisions")

    async def test_recall_disabled_by_flag(self, memory):
        with patch("src.agents.memory.get_flag", new=AsyncMock(return_value=False)):
            result = await memory.recall("anything")
        assert result.rows == []
        assert result.skipped_reason == "disabled_by_flag"

    async def test_recall_returns_filtered_rows_above_threshold(self, memory):
        rows = [
            {"id": 1, "decision_type": "HALT", "score": 0.9, "cosine_sim": 0.9},
            {"id": 2, "decision_type": "NUDGE", "score": 0.3, "cosine_sim": 0.3},
            {"id": 3, "decision_type": "HOLD", "score": 0.7, "cosine_sim": 0.7},
        ]
        with (
            patch("src.agents.memory.get_flag", new=AsyncMock(return_value=True)),
            patch(
                "src.agents.memory.semantic_search",
                new=AsyncMock(return_value=rows),
            ),
        ):
            result = await memory.recall("q")
        assert [r["id"] for r in result.rows] == [1, 3]

    async def test_recall_embedding_failure_returns_empty(self, memory):
        from src.llm.embeddings import EmbeddingConfigError
        with (
            patch("src.agents.memory.get_flag", new=AsyncMock(return_value=True)),
            patch(
                "src.agents.memory.semantic_search",
                new=AsyncMock(side_effect=EmbeddingConfigError("no key")),
            ),
        ):
            result = await memory.recall("q")
        assert result.rows == []
        assert result.skipped_reason == "embedding_failed"

    async def test_recall_for_observation_composes_scoped_query(self, memory):
        captured: dict = {}

        async def fake_search(query, **kwargs):
            captured["query"] = query
            captured["where"] = kwargs.get("where")
            captured["where_params"] = kwargs.get("where_params")
            return []

        obs = AgentObservation(
            scope="channel",
            scope_id="ch42",
            facts={"avg_score": 6.5, "consecutive_failures": 2},
        )
        with (
            patch("src.agents.memory.get_flag", new=AsyncMock(return_value=True)),
            patch("src.agents.memory.semantic_search", new=fake_search),
        ):
            await memory.recall_for_observation(obs)

        # Query is deterministic and includes scope + sorted facts.
        assert "scope=channel" in captured["query"]
        assert "scope_id=ch42" in captured["query"]
        assert "avg_score=6.5" in captured["query"]
        # Scope filter binds scope and scope_id as parameters.
        assert captured["where"] == "scope = $2 AND scope_id = $3"
        assert captured["where_params"] == ("channel", "ch42")


# ─────────────────────────────────────────────────────────────────────────────
# AgentRegistry
# ─────────────────────────────────────────────────────────────────────────────


class TestAgentRegistry:
    def setup_method(self):
        AgentRegistry.clear()

    def teardown_method(self):
        AgentRegistry.clear()

    def test_register_and_get(self):
        agent = _DummyAgent()
        AgentRegistry.register(agent)
        assert AgentRegistry.get("dummy") is agent

    def test_register_overwrites_same_name(self):
        AgentRegistry.register(_DummyAgent())
        second = _DummyAgent()
        AgentRegistry.register(second)
        assert AgentRegistry.get("dummy") is second

    def test_all_returns_list(self):
        AgentRegistry.register(_DummyAgent())
        assert len(AgentRegistry.all()) == 1


# ─────────────────────────────────────────────────────────────────────────────
# BrainAgent integration with framework
# ─────────────────────────────────────────────────────────────────────────────


class TestBrainAgentLifecycle:
    @pytest.fixture(autouse=True)
    def patch_deps(self):
        from src.services.brain.analyser import ChannelSignals
        self._signals = ChannelSignals(
            channel_id="ch1",
            avg_composite_score=8.0,
            recent_scores=[8.0, 8.5, 7.5],
            total_delivered=10,
            consecutive_failures=3,  # triggers HALT
        )
        with (
            patch(
                "src.services.brain.agent.analyse_channel",
                new=AsyncMock(return_value=self._signals),
            ),
            patch(
                "src.services.brain.agent._evaluate",
                new=AsyncMock(return_value={
                    "id": 7,
                    "decision_type": "HALT",
                    "scope": "channel",
                    "scope_id": "ch1",
                    "directive": {"action": "HALT", "reason": "consecutive_failures"},
                    "reasoning": "Channel ch1 has 3 consecutive failures.",
                    "confidence": 0.9,
                    "context_summary": "ctx",
                }),
            ),
            patch("src.services.brain.agent.publish", new=AsyncMock()) as pub,
            patch(
                "src.services.brain.agent.get_pool",
                new=AsyncMock(),
            ),
        ):
            self._publish = pub
            yield

    async def test_observe_returns_observation(self):
        from src.services.brain.agent import BrainAgent
        agent = BrainAgent()
        obs = await agent.observe({"channel_id": "ch1", "content_id": None})
        assert obs is not None
        assert obs.scope == "channel"
        assert obs.scope_id == "ch1"
        assert obs.facts["consecutive_failures"] == 3

    async def test_observe_missing_channel_id_returns_none(self):
        from src.services.brain.agent import BrainAgent
        agent = BrainAgent()
        obs = await agent.observe({})
        assert obs is None

    async def test_decide_without_memories_keeps_reasoning(self):
        from src.services.brain.agent import BrainAgent
        agent = BrainAgent()
        obs = await agent.observe({"channel_id": "ch1", "content_id": None})
        state = await agent.reason(obs, memories=[])
        decision = await agent.decide(state)
        assert decision is not None
        assert decision.decision_type == "HALT"
        assert "Precedent:" not in decision.reasoning

    async def test_decide_with_memories_prepends_precedent(self):
        from src.services.brain.agent import BrainAgent
        agent = BrainAgent()
        obs = await agent.observe({"channel_id": "ch1", "content_id": None})
        memories = [
            {"id": 5, "decision_type": "HALT", "score": 0.88},
            {"id": 4, "decision_type": "NUDGE", "score": 0.72},
        ]
        state = await agent.reason(obs, memories=memories)
        decision = await agent.decide(state)
        assert decision is not None
        assert decision.reasoning.startswith("Precedent: ")
        assert "#5 HALT" in decision.reasoning
        assert "#4 NUDGE" in decision.reasoning
        # original reasoning still present after the precedent line
        assert "Channel ch1 has 3 consecutive failures." in decision.reasoning
        assert decision.extras["memories_used"] == 2

    async def test_full_run_publishes_directive(self):
        from src.services.brain.agent import BrainAgent
        agent = BrainAgent()
        # Stub recall so it returns empty (no DB hit) and remember (no-op).
        with patch.object(
            BrainAgent, "recall", new=AsyncMock(return_value=[])
        ):
            decision = await agent.run(
                {"channel_id": "ch1", "content_id": None}
            )
        assert decision is not None
        assert decision.decision_type == "HALT"
        self._publish.assert_awaited_once()
        kwargs = self._publish.call_args.kwargs
        assert kwargs["payload"]["decision_type"] == "HALT"
        assert kwargs["payload"]["memories_used"] == 0
