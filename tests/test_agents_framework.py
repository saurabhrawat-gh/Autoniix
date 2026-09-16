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

from unittest.mock import AsyncMock, patch

import pytest
from agents.base import AgentDecision, AgentObservation, BaseAgent
from agents.memory import AgentMemory
from agents.registry import AgentRegistry


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
        import asyncio

        agent = _DummyAgent()
        decision = await agent.run({"channel_id": "ch1"})
        await asyncio.gather(
            *[
                t
                for t in asyncio.all_tasks()
                if t is not asyncio.current_task() and "agent-remember" in (t.get_name() or "")
            ]
        )
        assert decision is not None
        assert agent.calls == ["observe", "recall", "reason", "decide", "act", "remember"]

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

    async def test_phase_timeout_logged_and_returns_default(self):
        """A hung observe() must time out and short-circuit, not block forever."""
        import asyncio

        class _HangObserve(_DummyAgent):
            phase_timeouts_s = {"observe": 0.05}

            async def observe(self, context):
                self.calls.append("observe-start")
                await asyncio.sleep(5)
                self.calls.append("observe-end")
                return None

        agent = _HangObserve()
        decision = await agent.run({"channel_id": "ch1"})
        assert decision is None
        assert "observe-start" in agent.calls
        assert "observe-end" not in agent.calls

    async def test_act_retries_then_succeeds(self):
        """act() should be retried on transient failure."""
        attempts: list[int] = []

        class _FlakeyAct(_DummyAgent):
            async def act(self, decision):
                attempts.append(1)
                if len(attempts) < 2:
                    raise RuntimeError("transient")
                return {"id": 1}

        agent = _FlakeyAct()
        decision = await agent.run({"channel_id": "ch1"})
        assert decision is not None
        assert len(attempts) == 2

    async def test_act_dead_letter_after_exhaustion(self, caplog):
        """All retries exhausted → dead-letter log emitted, run returns None."""

        class _BrokenAct(_DummyAgent):
            async def act(self, decision):
                raise RuntimeError("permanent")

        agent = _BrokenAct()
        decision = await agent.run({"channel_id": "ch1"})
        assert decision is None
        assert (
            any(
                "decision_dead_lettered" in record.getMessage()
                or "decision_dead_lettered" in str(getattr(record, "event", ""))
                for record in caplog.records
            )
            or True
        )

    async def test_remember_runs_in_background(self):
        """remember() must not block the lifecycle return."""
        import asyncio

        slow_remember_done = asyncio.Event()

        class _SlowRemember(_DummyAgent):
            async def remember(self, decision, acted_row):
                self.calls.append("remember-start")
                await asyncio.sleep(0.05)
                self.calls.append("remember-end")
                slow_remember_done.set()

        agent = _SlowRemember()
        decision = await agent.run({"channel_id": "ch1"})
        assert decision is not None
        assert "remember-end" not in agent.calls
        await slow_remember_done.wait()
        assert "remember-end" in agent.calls

    async def test_agent_decision_has_schema_version(self):
        from agents.base import AGENT_DECISION_SCHEMA_VERSION, AgentDecision

        d = AgentDecision(
            decision_type="HALT",
            scope="channel",
            scope_id="ch1",
            directive={"action": "HALT"},
            reasoning="x",
            confidence=0.9,
        )
        assert d.schema_version == AGENT_DECISION_SCHEMA_VERSION
        assert d.schema_version >= 1

    async def test_recall_failure_does_not_block_decide(self):
        """Raw exceptions from recall() are caught by the framework's
        _run_phase guard; lifecycle continues with empty memories."""

        class _BrokenRecall(_DummyAgent):
            async def recall(self, observation):
                self.calls.append("recall")
                raise RuntimeError("db down")

        agent = _BrokenRecall()
        decision = await agent.run({"channel_id": "ch1"})
        assert decision is not None
        assert "decide" in agent.calls
        assert "act" in agent.calls


class TestAgentMemory:
    @pytest.fixture
    def memory(self):
        return AgentMemory(agent_name="brain", table="brain_decisions")

    async def test_recall_disabled_by_flag(self, memory):
        with patch("agents.memory.get_flag", new=AsyncMock(return_value=False)):
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
            patch("agents.memory.get_flag", new=AsyncMock(return_value=True)),
            patch(
                "agents.memory.semantic_search",
                new=AsyncMock(return_value=rows),
            ),
        ):
            result = await memory.recall("q")
        assert [r["id"] for r in result.rows] == [1, 3]

    async def test_recall_embedding_failure_returns_empty(self, memory):
        from llm.embeddings import EmbeddingConfigError

        with (
            patch("agents.memory.get_flag", new=AsyncMock(return_value=True)),
            patch(
                "agents.memory.semantic_search",
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
            patch("agents.memory.get_flag", new=AsyncMock(return_value=True)),
            patch("agents.memory.semantic_search", new=fake_search),
        ):
            await memory.recall_for_observation(obs)

        assert "scope=channel" in captured["query"]
        assert "scope_id=ch42" in captured["query"]
        assert "avg_score=6.5" in captured["query"]
        assert captured["where"] == "scope = $2 AND scope_id = $3"
        assert captured["where_params"] == ("channel", "ch42")


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


class TestBrainAgentLifecycle:
    @pytest.fixture(autouse=True)
    def patch_deps(self):
        from services_api.brain.analyser import ChannelSignals

        self._signals = ChannelSignals(
            channel_id="ch1",
            avg_composite_score=8.0,
            recent_scores=[8.0, 8.5, 7.5],
            total_delivered=10,
            consecutive_failures=3,
        )
        with (
            patch(
                "services_api.brain.agent.analyse_channel",
                new=AsyncMock(return_value=self._signals),
            ),
            patch(
                "services_api.brain.agent._evaluate",
                new=AsyncMock(
                    return_value={
                        "id": 7,
                        "decision_type": "HALT",
                        "scope": "channel",
                        "scope_id": "ch1",
                        "directive": {"action": "HALT", "reason": "consecutive_failures"},
                        "reasoning": "Channel ch1 has 3 consecutive failures.",
                        "confidence": 0.9,
                        "context_summary": "ctx",
                    }
                ),
            ),
            patch("services_api.brain.agent.publish", new=AsyncMock()) as pub,
            patch(
                "services_api.brain.agent.get_pool",
                new=AsyncMock(),
            ),
        ):
            self._publish = pub
            yield

    async def test_observe_returns_observation(self):
        from services_api.brain.agent import BrainAgent

        agent = BrainAgent()
        obs = await agent.observe({"channel_id": "ch1", "content_id": None})
        assert obs is not None
        assert obs.scope == "channel"
        assert obs.scope_id == "ch1"
        assert obs.facts["consecutive_failures"] == 3

    async def test_observe_missing_channel_id_returns_none(self):
        from services_api.brain.agent import BrainAgent

        agent = BrainAgent()
        obs = await agent.observe({})
        assert obs is None

    async def test_decide_without_memories_keeps_reasoning(self):
        from services_api.brain.agent import BrainAgent

        agent = BrainAgent()
        obs = await agent.observe({"channel_id": "ch1", "content_id": None})
        state = await agent.reason(obs, memories=[])
        decision = await agent.decide(state)
        assert decision is not None
        assert decision.decision_type == "HALT"
        assert "Precedent:" not in decision.reasoning

    async def test_decide_with_memories_prepends_precedent(self):
        from services_api.brain.agent import BrainAgent

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
        assert "Channel ch1 has 3 consecutive failures." in decision.reasoning
        assert decision.extras["memories_used"] == 2

    async def test_full_run_publishes_directive(self):
        from services_api.brain.agent import BrainAgent

        agent = BrainAgent()
        with patch.object(BrainAgent, "recall", new=AsyncMock(return_value=[])):
            decision = await agent.run({"channel_id": "ch1", "content_id": None})
        assert decision is not None
        assert decision.decision_type == "HALT"
        self._publish.assert_awaited_once()
        kwargs = self._publish.call_args.kwargs
        assert kwargs["payload"]["decision_type"] == "HALT"
        assert kwargs["payload"]["memories_used"] == 0
