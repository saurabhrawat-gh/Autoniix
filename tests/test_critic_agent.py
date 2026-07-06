"""Unit tests for CriticAgent and the BaseAgent critique phase.

All external I/O is patched. No DB, Redis, or LLM calls.

Coverage:
  * CriticAgent._rule_review for APPROVE / VETO-low-conf-HALT /
    MODIFY-overconfident-ADVISE / VETO-empty-directive
  * CriticAgent.review chooses LLM path when flag is on, falls back to
    rules on LLM failure, and persists every verdict.
  * BaseAgent.run() critique-phase wiring:
      - flags off → critique skipped (legacy behaviour)
      - VETO     → decision dropped, dead-letter logged, run() returns None
      - MODIFY   → modified decision is what reaches act() / remember()
      - APPROVE  → original decision proceeds unchanged
      - critic.review raises → fail-open (original decision proceeds)
      - no critic registered → skip with warning, original proceeds
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.base import (
    AgentDecision,
    AgentObservation,
    BaseAgent,
    CriticVerdict,
)
from agents.critic import CriticAgent
from agents.registry import AgentRegistry




def _decision(
    *,
    decision_type: str = "HALT",
    confidence: float = 0.9,
    directive: dict | None = None,
    extras: dict | None = None,
) -> AgentDecision:
    return AgentDecision(
        decision_type=decision_type,
        scope="channel",
        scope_id="ch1",
        directive=directive if directive is not None else {"action": decision_type},
        reasoning=f"{decision_type} because reasons.",
        confidence=confidence,
        context_summary="ctx",
        extras=extras or {"decision_id": 42},
    )


def _observation() -> AgentObservation:
    return AgentObservation(
        scope="channel",
        scope_id="ch1",
        facts={"avg_score": 6.0, "consecutive_failures": 3},
    )


class _PeerAgent(BaseAgent):
    """Minimal peer used to exercise BaseAgent.run() critique wiring."""

    name = "peer"
    decision_table = "peer_decisions"
    flag_prefix = "peer."

    def __init__(self, *, decision: AgentDecision | None = None) -> None:
        super().__init__()
        self._decision = decision or _decision()
        self.acted_with: AgentDecision | None = None

    async def observe(self, context):
        return _observation()

    async def recall(self, observation):
        return []

    async def reason(self, observation, memories):
        return {"observation": observation, "memories": memories}

    async def decide(self, state):
        return self._decision

    async def act(self, decision):
        self.acted_with = decision
        return {"id": 7}

    async def remember(self, decision, acted_row):
        return None




class TestCriticRuleReview:
    def test_approve_well_calibrated(self):
        critic = CriticAgent()
        v = critic._rule_review(_decision(decision_type="HALT", confidence=0.9))
        assert v.verdict == "APPROVE"
        assert v.modified_decision is None

    def test_veto_low_confidence_halt(self):
        critic = CriticAgent()
        v = critic._rule_review(_decision(decision_type="HALT", confidence=0.4))
        assert v.verdict == "VETO"
        assert "0.40" in v.reasoning

    def test_modify_overconfident_advise(self):
        critic = CriticAgent()
        v = critic._rule_review(
            _decision(decision_type="ADVISE", confidence=0.99)
        )
        assert v.verdict == "MODIFY"
        assert v.modified_decision is not None
        assert v.modified_decision.decision_type == "NUDGE"
        assert v.modified_decision.directive.get("escalated_from") == "ADVISE"

    def test_veto_empty_directive(self):
        critic = CriticAgent()
        v = critic._rule_review(_decision(directive={}))
        assert v.verdict == "VETO"
        assert "directive" in v.reasoning.lower()




class TestCriticReview:
    async def test_review_uses_rules_when_llm_disabled(self):
        critic = CriticAgent()
        decision = _decision(decision_type="HALT", confidence=0.4)
        with (
            patch(
                "agents.critic.get_flag", new=AsyncMock(return_value=False)
            ),
            patch.object(
                critic, "_persist_verdict", new=AsyncMock()
            ) as persist,
        ):
            verdict = await critic.review(
                decision=decision,
                observation=_observation(),
                peer_agent_name="brain",
            )
        assert verdict.verdict == "VETO"
        persist.assert_awaited_once()
        assert persist.await_args.kwargs["reasoning_path"] == "rules"

    async def test_review_falls_back_to_rules_on_llm_failure(self):
        critic = CriticAgent()
        decision = _decision(decision_type="HALT", confidence=0.4)
        with (
            patch(
                "agents.critic.get_flag", new=AsyncMock(return_value=True)
            ),
            patch.object(
                critic, "_llm_review", new=AsyncMock(return_value=None)
            ),
            patch.object(
                critic, "_persist_verdict", new=AsyncMock()
            ) as persist,
        ):
            verdict = await critic.review(
                decision=decision,
                observation=_observation(),
                peer_agent_name="brain",
            )
        assert verdict.verdict == "VETO"
        assert persist.await_args.kwargs["reasoning_path"] == "rules"

    async def test_review_uses_llm_path_when_flag_on(self):
        critic = CriticAgent()
        decision = _decision(decision_type="HALT", confidence=0.9)
        synthetic = CriticVerdict(
            verdict="APPROVE",
            reasoning="LLM agrees",
            confidence=0.8,
            reviewed_decision_type="HALT",
            reviewed_scope_id="ch1",
        )
        with (
            patch(
                "agents.critic.get_flag", new=AsyncMock(return_value=True)
            ),
            patch.object(
                critic, "_llm_review", new=AsyncMock(return_value=synthetic)
            ),
            patch.object(
                critic, "_persist_verdict", new=AsyncMock()
            ) as persist,
        ):
            verdict = await critic.review(
                decision=decision,
                observation=_observation(),
                peer_agent_name="brain",
            )
        assert verdict is synthetic
        assert persist.await_args.kwargs["reasoning_path"] == "llm"

    async def test_review_persistence_failure_does_not_block_verdict(self):
        critic = CriticAgent()
        with (
            patch(
                "agents.critic.get_flag", new=AsyncMock(return_value=False)
            ),
            patch.object(
                critic,
                "_persist_verdict",
                new=AsyncMock(side_effect=RuntimeError("db down")),
            ),
        ):
            verdict = await critic.review(
                decision=_decision(),
                observation=_observation(),
                peer_agent_name="brain",
            )
        assert verdict.verdict in {"APPROVE", "VETO", "MODIFY"}




@pytest.fixture
def fresh_registry():
    """Snapshot + restore the registry around each test in this section."""
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


def _flag_map(flags: dict[str, bool]):
    """Build an AsyncMock side-effect that returns ``flags[key]`` per call."""

    async def _get_flag(key, default=False):  # noqa: ANN001
        return flags.get(key, default)

    return _get_flag


class TestBaseAgentCritiqueWiring:
    async def test_critique_skipped_when_flags_off(self, fresh_registry):
        peer = _PeerAgent()
        with patch(
            "core.flags.get_flag",
            new=AsyncMock(return_value=False),
        ):
            decision = await peer.run({})
        assert decision is not None
        assert peer.acted_with is decision
        assert decision.decision_type == "HALT"

    async def test_critique_veto_drops_decision(self, fresh_registry):
        peer = _PeerAgent()

        class _VetoCritic(CriticAgent):
            async def review(self, *, decision, observation, peer_agent_name):
                return CriticVerdict(
                    verdict="VETO",
                    reasoning="too risky",
                    confidence=0.9,
                    reviewed_decision_type=decision.decision_type,
                    reviewed_scope_id=decision.scope_id,
                )

        AgentRegistry.register(_VetoCritic())

        with patch(
            "core.flags.get_flag",
            side_effect=_flag_map({
                "critic.enabled": True,
                "peer.critic_review.enabled": True,
            }),
        ):
            decision = await peer.run({})

        assert decision is None
        assert peer.acted_with is None

    async def test_critique_modify_substitutes_decision(self, fresh_registry):
        peer = _PeerAgent()
        replacement = _decision(decision_type="NUDGE", confidence=0.8)

        class _ModifyCritic(CriticAgent):
            async def review(self, *, decision, observation, peer_agent_name):
                return CriticVerdict(
                    verdict="MODIFY",
                    reasoning="HALT was too aggressive; downgrade to NUDGE",
                    confidence=0.7,
                    reviewed_decision_type=decision.decision_type,
                    reviewed_scope_id=decision.scope_id,
                    modified_decision=replacement,
                )

        AgentRegistry.register(_ModifyCritic())

        with patch(
            "core.flags.get_flag",
            side_effect=_flag_map({
                "critic.enabled": True,
                "peer.critic_review.enabled": True,
            }),
        ):
            decision = await peer.run({})

        assert decision is replacement
        assert peer.acted_with is replacement
        assert peer.acted_with.decision_type == "NUDGE"

    async def test_critique_approve_passes_through(self, fresh_registry):
        peer = _PeerAgent()
        original = peer._decision

        class _ApproveCritic(CriticAgent):
            async def review(self, *, decision, observation, peer_agent_name):
                return CriticVerdict(
                    verdict="APPROVE",
                    reasoning="signals support HALT",
                    confidence=0.85,
                    reviewed_decision_type=decision.decision_type,
                    reviewed_scope_id=decision.scope_id,
                )

        AgentRegistry.register(_ApproveCritic())

        with patch(
            "core.flags.get_flag",
            side_effect=_flag_map({
                "critic.enabled": True,
                "peer.critic_review.enabled": True,
            }),
        ):
            decision = await peer.run({})

        assert decision is original
        assert peer.acted_with is original

    async def test_critique_failure_fails_open(self, fresh_registry):
        peer = _PeerAgent()
        original = peer._decision

        class _BrokenCritic(CriticAgent):
            async def review(self, *, decision, observation, peer_agent_name):
                raise RuntimeError("critic crashed")

        AgentRegistry.register(_BrokenCritic())

        with patch(
            "core.flags.get_flag",
            side_effect=_flag_map({
                "critic.enabled": True,
                "peer.critic_review.enabled": True,
            }),
        ):
            decision = await peer.run({})

        assert decision is original
        assert peer.acted_with is original

    async def test_critique_skipped_when_no_critic_registered(
        self, fresh_registry
    ):
        peer = _PeerAgent()
        original = peer._decision
        with patch(
            "core.flags.get_flag",
            side_effect=_flag_map({
                "critic.enabled": True,
                "peer.critic_review.enabled": True,
            }),
        ):
            decision = await peer.run({})

        assert decision is original
        assert peer.acted_with is original

    async def test_critic_does_not_critique_itself(self, fresh_registry):
        """Recursion guard: when the running agent IS the critic, the
        critique branch must short-circuit without registry lookup or
        flag reads."""
        critic = CriticAgent()

        decision = _decision()
        with patch(
            "core.flags.get_flag",
            new=AsyncMock(side_effect=AssertionError("flags should not be read")),
        ):
            out = await critic._run_critique(decision, _observation())
        assert out is decision
