"""CriticAgent — independent safety reviewer over peer agent decisions.

Sits between :meth:`BaseAgent.decide` and :meth:`BaseAgent.act` whenever
both ``critic.enabled`` and the peer's ``<prefix>critic_review.enabled``
flag are TRUE. Returns a :class:`CriticVerdict`:

* ``APPROVE`` — the peer's decision is sound; act() proceeds unchanged.
* ``VETO``    — the decision is unsafe; the peer's framework drops it
                and dead-letters the audit log entry.
* ``MODIFY``  — the direction is right but the type/severity is wrong;
                the peer substitutes ``modified_decision`` for the
                original before act().

Two reasoning paths:

* **LLM** (gated by ``critic.llm_reasoning.enabled``): structured-output
  call via :class:`LLMReasoner` with :data:`CRITIC_SYSTEM_PROMPT`.
* **Rules** (always available, used as fallback): deterministic
  heuristics that catch the most common calibration errors —
  HALT-with-low-confidence, ADVISE-with-overwhelming-confidence,
  malformed directives. Cheap and offline-safe.

Every verdict is persisted to ``critic_decisions`` so the audit trail
is complete even on APPROVE.

Part of AE-P1 / Agentic Foundation.
"""
from __future__ import annotations

import json
from typing import Any, ClassVar

import structlog

from src.agents.base import (
    AgentDecision,
    AgentObservation,
    BaseAgent,
    CRITIC_VERDICTS,
    CriticVerdict,
)
from src.agents.llm_reasoner import CRITIC_SYSTEM_PROMPT, LLMReasoner
from src.db import get_pool
from src.flags import get_flag
from src.llm.embeddings import (
    EmbeddingConfigError,
    EmbeddingError,
    embed_and_store,
)

logger = structlog.get_logger()


_HALT_MIN_CONFIDENCE = 0.5

_ADVISE_MAX_CONFIDENCE = 0.95


class CriticAgent(BaseAgent):
    """Reviews peer agent decisions and emits a :class:`CriticVerdict`.

    Unlike a normal agent the Critic doesn't observe events from the
    bus directly; the entry point is :meth:`review`, which the
    framework's :meth:`BaseAgent._run_critique` calls. We still inherit
    from :class:`BaseAgent` so we get name/decision_table/flag_prefix
    bookkeeping and the same telemetry conventions.
    """

    name: ClassVar[str] = "critic"
    decision_table: ClassVar[str] = "critic_decisions"
    flag_prefix: ClassVar[str] = "critic."

    _ALLOWED_VERDICTS = set(CRITIC_VERDICTS)
    _ALLOWED_DECISION_TYPES = {
        "HALT", "HOLD", "NUDGE", "RESUME", "ADVISE", "NONE",
    }


    async def review(
        self,
        *,
        decision: AgentDecision,
        observation: AgentObservation,
        peer_agent_name: str,
    ) -> CriticVerdict:
        """Review a peer's :class:`AgentDecision` and return a verdict.

        Persistence is best-effort: if the DB write fails the verdict is
        still returned so the caller can act on it. The framework's
        critique phase fail-opens on any uncaught exception, so this
        method is conservative — every internal error becomes APPROVE
        (with a logged warning) rather than blocking the peer.
        """
        verdict: CriticVerdict | None = None
        reasoning_path = "rules"
        try:
            llm_on = await get_flag(
                "critic.llm_reasoning.enabled", default=False
            )
        except Exception:
            llm_on = False

        if llm_on:
            try:
                verdict = await self._llm_review(
                    decision=decision,
                    observation=observation,
                    peer_agent_name=peer_agent_name,
                )
                if verdict is not None:
                    reasoning_path = "llm"
            except Exception as exc:
                logger.warning(
                    "critic.llm_review_raised",
                    peer=peer_agent_name, error=str(exc),
                )
                verdict = None

        if verdict is None:
            verdict = self._rule_review(decision)

        try:
            await self._persist_verdict(
                verdict=verdict,
                decision=decision,
                observation=observation,
                peer_agent_name=peer_agent_name,
                reasoning_path=reasoning_path,
            )
        except Exception as exc:
            logger.warning(
                "critic.persist_failed",
                peer=peer_agent_name,
                verdict=verdict.verdict,
                error=str(exc),
            )

        return verdict


    def _rule_review(self, decision: AgentDecision) -> CriticVerdict:
        """Deterministic heuristics. Always returns a valid verdict.

        The rules here are deliberately small. They exist to (a) keep the
        Critic functional when the LLM path is disabled or failing, and
        (b) provide a safety floor that catches the most obvious
        calibration mistakes without depending on an external service.
        """
        dtype = decision.decision_type
        conf = float(decision.confidence or 0.0)

        if not isinstance(decision.directive, dict) or not decision.directive:
            return CriticVerdict(
                verdict="VETO",
                reasoning=(
                    "Empty or non-dict directive on a "
                    f"{dtype} decision — refusing to act."
                ),
                confidence=0.95,
                reviewed_decision_type=dtype,
                reviewed_scope_id=decision.scope_id,
            )

        if dtype == "HALT" and conf < _HALT_MIN_CONFIDENCE:
            return CriticVerdict(
                verdict="VETO",
                reasoning=(
                    f"HALT at confidence={conf:.2f} is below the "
                    f"{_HALT_MIN_CONFIDENCE:.2f} safety floor."
                ),
                confidence=0.85,
                reviewed_decision_type=dtype,
                reviewed_scope_id=decision.scope_id,
            )

        if dtype == "ADVISE" and conf > _ADVISE_MAX_CONFIDENCE:
            modified = AgentDecision(
                decision_type="NUDGE",
                scope=decision.scope,
                scope_id=decision.scope_id,
                directive={
                    **decision.directive,
                    "action": "NUDGE",
                    "escalated_from": "ADVISE",
                },
                reasoning=decision.reasoning,
                confidence=conf,
                context_summary=decision.context_summary,
                extras={**decision.extras, "modified_by_critic": True},
            )
            return CriticVerdict(
                verdict="MODIFY",
                reasoning=(
                    f"ADVISE at confidence={conf:.2f} is under-reactive; "
                    "escalating to NUDGE so the bias is auto-applied."
                ),
                confidence=0.7,
                reviewed_decision_type=dtype,
                reviewed_scope_id=decision.scope_id,
                modified_decision=modified,
            )

        return CriticVerdict(
            verdict="APPROVE",
            reasoning=(
                f"{dtype} at confidence={conf:.2f} is within calibration "
                "bounds; no safety concern detected."
            ),
            confidence=0.6,
            reviewed_decision_type=dtype,
            reviewed_scope_id=decision.scope_id,
        )


    async def _llm_review(
        self,
        *,
        decision: AgentDecision,
        observation: AgentObservation,
        peer_agent_name: str,
    ) -> CriticVerdict | None:
        """Run the LLM reasoner. Returns ``None`` on any failure so
        :meth:`review` falls back to rules.
        """
        user_prompt = self._compose_user_prompt(
            decision=decision,
            observation=observation,
            peer_agent_name=peer_agent_name,
        )
        reasoner = LLMReasoner(
            category="llm",
            system_prompt=CRITIC_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=768,
        )
        parsed = await reasoner.reason(
            user_prompt=user_prompt,
            channel_id="",
            content_id=decision.scope_id or "",
            allowed_decision_types=None,
        )
        if parsed is None:
            return None

        return self._verdict_from_decision_shaped_response(parsed, decision)

    @staticmethod
    def _verdict_from_decision_shaped_response(
        parsed: dict[str, Any], original: AgentDecision
    ) -> CriticVerdict:
        """Translate a decision-shaped LLM response into a CriticVerdict.

        :class:`LLMReasoner` validates against the decision schema, so
        any response we receive here looks like a fresh AgentDecision.
        We map it as follows:

        * Same decision_type + directive as ``original`` → APPROVE
        * decision_type == "NONE" with a clear reasoning           → VETO
        * Any other decision_type / directive                       → MODIFY
          (carry the new decision_type + directive into the verdict)

        This is a pragmatic adapter; once a verdict-native LLM call
        path lands we'll switch to it.
        """
        new_type = parsed["decision_type"]
        new_directive = parsed["directive"]
        new_reasoning = parsed["reasoning"]
        new_conf = float(parsed["confidence"])

        if new_type == original.decision_type and new_directive == original.directive:
            return CriticVerdict(
                verdict="APPROVE",
                reasoning=new_reasoning,
                confidence=new_conf,
                reviewed_decision_type=original.decision_type,
                reviewed_scope_id=original.scope_id,
            )
        if new_type == "NONE":
            return CriticVerdict(
                verdict="VETO",
                reasoning=new_reasoning,
                confidence=new_conf,
                reviewed_decision_type=original.decision_type,
                reviewed_scope_id=original.scope_id,
            )
        modified = AgentDecision(
            decision_type=new_type,
            scope=original.scope,
            scope_id=original.scope_id,
            directive=new_directive,
            reasoning=new_reasoning,
            confidence=new_conf,
            context_summary=original.context_summary,
            extras={**original.extras, "modified_by_critic": True},
        )
        return CriticVerdict(
            verdict="MODIFY",
            reasoning=new_reasoning,
            confidence=new_conf,
            reviewed_decision_type=original.decision_type,
            reviewed_scope_id=original.scope_id,
            modified_decision=modified,
        )

    @staticmethod
    def _compose_user_prompt(
        *,
        decision: AgentDecision,
        observation: AgentObservation,
        peer_agent_name: str,
    ) -> str:
        parts = [
            f"# Peer agent under review: {peer_agent_name}",
            "",
            "# Observed signals at decide() time",
            f"scope: {observation.scope}",
            f"scope_id: {observation.scope_id}",
        ]
        for k in sorted(observation.facts):
            parts.append(f"{k}: {observation.facts[k]}")
        parts += [
            "",
            "# Peer's proposed decision",
            f"decision_type: {decision.decision_type}",
            f"confidence: {decision.confidence}",
            f"directive: {json.dumps(decision.directive, sort_keys=True)}",
            f"reasoning: {decision.reasoning}",
            "",
            "Review the decision against the signals. Return JSON only.",
        ]
        return "\n".join(parts)


    async def _persist_verdict(
        self,
        *,
        verdict: CriticVerdict,
        decision: AgentDecision,
        observation: AgentObservation,
        peer_agent_name: str,
        reasoning_path: str,
    ) -> None:
        modified_directive = (
            verdict.modified_decision.directive
            if verdict.modified_decision is not None
            else None
        )
        modified_decision_type = (
            verdict.modified_decision.decision_type
            if verdict.modified_decision is not None
            else None
        )
        original_decision_id = decision.extras.get("decision_id")

        pool = await get_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO critic_decisions
                (original_decision_id, original_agent, reviewed_decision_type,
                 verdict, reasoning, confidence, modified_directive,
                 modified_decision_type, scope, scope_id, reasoning_path)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10, $11)
            RETURNING id
            """,
            original_decision_id,
            peer_agent_name,
            decision.decision_type,
            verdict.verdict,
            verdict.reasoning,
            round(float(verdict.confidence or 0), 2),
            json.dumps(modified_directive) if modified_directive else None,
            modified_decision_type,
            observation.scope,
            observation.scope_id,
            reasoning_path,
        )

        critic_id = row["id"] if row else None
        if critic_id is None:
            return

        embed_text = (
            f"{verdict.verdict} of {peer_agent_name} {decision.decision_type} "
            f"@ {observation.scope}:{observation.scope_id}\n"
            f"reasoning: {verdict.reasoning}"
        )
        try:
            await embed_and_store(
                embed_text,
                table="critic_decisions",
                row_id=critic_id,
                column="embedding",
            )
        except (EmbeddingError, EmbeddingConfigError) as exc:
            logger.warning(
                "critic.embed_skipped",
                critic_id=critic_id, error=str(exc),
            )

        logger.info(
            "critic.verdict_written",
            critic_id=critic_id,
            peer=peer_agent_name,
            verdict=verdict.verdict,
            reviewed_type=decision.decision_type,
            scope_id=observation.scope_id,
            reasoning_path=reasoning_path,
        )
