"""Unit tests for src/agents/llm_reasoner.py and the LLM decide path in
BrainAgent. All LLM calls are mocked — no network, no DB."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.llm_reasoner import (
    BRAIN_SYSTEM_PROMPT,
    DECISION_JSON_SCHEMA,
    LLMReasoner,
)
from providers.llm.base import LLMResult




def _llm_result(content: str) -> LLMResult:
    return LLMResult(
        content=content,
        model="mock-model",
        tokens_in=10,
        tokens_out=20,
        cost_usd=0.0001,
        latency_ms=42,
        provider="mock",
    )


@pytest.fixture
def reasoner():
    return LLMReasoner(system_prompt="test-prompt", temperature=0.0)


class TestLLMReasonerReason:
    async def test_happy_path_returns_validated_dict(self, reasoner):
        payload = {
            "decision_type": "HALT",
            "directive": {"action": "HALT", "reason": "test"},
            "reasoning": "channel failed three times in a row",
            "confidence": 0.85,
        }
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(return_value=_llm_result(json.dumps(payload))),
        ):
            out = await reasoner.reason(user_prompt="p", channel_id="ch1")
        assert out["decision_type"] == "HALT"
        assert out["confidence"] == 0.85

    async def test_parses_json_inside_codefence(self, reasoner):
        payload = {
            "decision_type": "ADVISE",
            "directive": {"action": "ADVISE"},
            "reasoning": "ok",
            "confidence": 0.6,
        }
        wrapped = f"Here is your decision:\n```json\n{json.dumps(payload)}\n```\nDone."
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(return_value=_llm_result(wrapped)),
        ):
            out = await reasoner.reason(user_prompt="p")
        assert out is not None
        assert out["decision_type"] == "ADVISE"

    async def test_returns_none_on_parse_failure(self, reasoner):
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(return_value=_llm_result("not even close to json")),
        ):
            out = await reasoner.reason(user_prompt="p")
        assert out is None

    async def test_returns_none_on_missing_required_field(self, reasoner):
        bad = {
            "decision_type": "HALT",
            "reasoning": "x",
            "confidence": 0.5,
        }
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(return_value=_llm_result(json.dumps(bad))),
        ):
            out = await reasoner.reason(user_prompt="p")
        assert out is None

    async def test_returns_none_on_confidence_out_of_range(self, reasoner):
        bad = {
            "decision_type": "HALT",
            "directive": {},
            "reasoning": "x",
            "confidence": 1.5,
        }
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(return_value=_llm_result(json.dumps(bad))),
        ):
            out = await reasoner.reason(user_prompt="p")
        assert out is None

    async def test_returns_none_on_disallowed_decision_type(self, reasoner):
        rogue = {
            "decision_type": "BLOW_UP_THE_WORLD",
            "directive": {"action": "x"},
            "reasoning": "rogue",
            "confidence": 0.99,
        }
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(return_value=_llm_result(json.dumps(rogue))),
        ):
            out = await reasoner.reason(
                user_prompt="p",
                allowed_decision_types={"HALT", "HOLD", "NUDGE"},
            )
        assert out is None

    async def test_budget_exceeded_returns_none(self, reasoner):
        from llm.router import BudgetExceeded
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(side_effect=BudgetExceeded("ch1", 5.0, 1.0)),
        ):
            out = await reasoner.reason(user_prompt="p", channel_id="ch1")
        assert out is None

    async def test_providers_exhausted_returns_none(self, reasoner):
        from llm.router import LadderExhausted
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(side_effect=LadderExhausted("llm", [("openai", "boom")])),
        ):
            out = await reasoner.reason(user_prompt="p")
        assert out is None

    async def test_generic_exception_returns_none(self, reasoner):
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(side_effect=RuntimeError("transport closed")),
        ):
            out = await reasoner.reason(user_prompt="p")
        assert out is None

    async def test_accepts_optional_reasoning_steps(self, reasoner):
        payload = {
            "decision_type": "NUDGE",
            "directive": {"action": "NUDGE", "bias": "stronger hook"},
            "reasoning": "scores trending down",
            "reasoning_steps": ["look at scores", "compare to baseline"],
            "confidence": 0.7,
        }
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(return_value=_llm_result(json.dumps(payload))),
        ):
            out = await reasoner.reason(user_prompt="p")
        assert out is not None
        assert out["reasoning_steps"] == ["look at scores", "compare to baseline"]

    async def test_rejects_bad_reasoning_steps_type(self, reasoner):
        payload = {
            "decision_type": "HALT",
            "directive": {},
            "reasoning": "x",
            "reasoning_steps": "should be a list, not a string",
            "confidence": 0.9,
        }
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(return_value=_llm_result(json.dumps(payload))),
        ):
            out = await reasoner.reason(user_prompt="p")
        assert out is None




class TestBrainAgentLLMDecide:
    @pytest.fixture
    def signals(self):
        from src.services.brain.analyser import ChannelSignals
        return ChannelSignals(
            channel_id="ch1",
            avg_composite_score=4.0,
            recent_scores=[4.0, 3.5, 4.2],
            total_delivered=10,
            consecutive_failures=2,
        )

    async def test_llm_path_writes_decision_and_returns_agent_decision(self, signals):
        from src.services.brain.agent import BrainAgent, _llm_decide_impl

        llm_payload = {
            "decision_type": "HALT",
            "directive": {"action": "HALT", "reason": "score crash"},
            "reasoning": "Recent scores show a sustained drop.",
            "reasoning_steps": ["look at recent_scores", "compare avg vs baseline"],
            "confidence": 0.78,
        }
        with (
            patch(
                "src.agents.llm_reasoner.route",
                new=AsyncMock(return_value=_llm_result(json.dumps(llm_payload))),
            ),
            patch(
                "src.services.brain.agent._write_decision",
                new=AsyncMock(return_value={
                    "id": 99,
                    "decision_type": "HALT",
                    "scope": "channel",
                    "scope_id": "ch1",
                    "directive": llm_payload["directive"],
                    "reasoning": llm_payload["reasoning"],
                    "confidence": 0.78,
                    "context_summary": "ctx",
                }),
            ),
        ):
            decision = await _llm_decide_impl(BrainAgent(), signals, None, [])

        assert decision is not None
        assert decision.decision_type == "HALT"
        assert decision.extras["reasoning_path"] == "llm"
        assert decision.extras["reasoning_steps"] == llm_payload["reasoning_steps"]
        assert "Steps:" in decision.reasoning

    async def test_llm_path_returns_none_when_decision_is_none(self, signals):
        """When the LLM returns NONE, the agent should treat it as no-action."""
        from src.services.brain.agent import BrainAgent, _llm_decide_impl

        payload = {
            "decision_type": "NONE",
            "directive": {"action": "NONE"},
            "reasoning": "all signals within healthy range",
            "confidence": 0.4,
        }
        with patch(
            "src.agents.llm_reasoner.route",
            new=AsyncMock(return_value=_llm_result(json.dumps(payload))),
        ):
            decision = await _llm_decide_impl(BrainAgent(), signals, None, [])
        assert decision is None

    async def test_decide_falls_back_to_rules_when_llm_fails(self, signals):
        """If LLMReasoner returns None, BrainAgent.decide() must fall through
        to the rule-based engine."""
        from src.services.brain.agent import BrainAgent

        rule_decision = {
            "id": 7,
            "decision_type": "HALT",
            "scope": "channel",
            "scope_id": "ch1",
            "directive": {"action": "HALT"},
            "reasoning": "rule-based reasoning",
            "confidence": 0.9,
            "context_summary": "ctx",
        }
        async def _flag(key, default=None):
            return key == "brain.llm_reasoning.enabled"

        with (
            patch("src.services.brain.agent.get_flag", side_effect=_flag),
            patch(
                "src.agents.llm_reasoner.route",
                new=AsyncMock(side_effect=RuntimeError("provider down")),
            ),
            patch(
                "src.services.brain.agent._evaluate",
                new=AsyncMock(return_value=rule_decision),
            ),
        ):
            decision = await BrainAgent().decide({
                "signals": signals,
                "content_id": None,
                "memories": [],
            })

        assert decision is not None
        assert decision.decision_type == "HALT"
        assert decision.extras["reasoning_path"] == "rules"

    async def test_decide_uses_rules_when_flag_is_off(self, signals):
        from src.services.brain.agent import BrainAgent

        rule_decision = {
            "id": 8,
            "decision_type": "ADVISE",
            "scope": "channel",
            "scope_id": "ch1",
            "directive": {"action": "ADVISE"},
            "reasoning": "rules only",
            "confidence": 0.5,
            "context_summary": "ctx",
        }
        with (
            patch(
                "src.services.brain.agent.get_flag",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "src.agents.llm_reasoner.route",
                new=AsyncMock(side_effect=AssertionError("LLM must not be called")),
            ),
            patch(
                "src.services.brain.agent._evaluate",
                new=AsyncMock(return_value=rule_decision),
            ),
        ):
            decision = await BrainAgent().decide({
                "signals": signals,
                "content_id": None,
                "memories": [],
            })

        assert decision is not None
        assert decision.extras["reasoning_path"] == "rules"
