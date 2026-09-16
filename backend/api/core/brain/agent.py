"""BrainAgent — :class:`BaseAgent` implementation that wraps the existing
analyser / engine into the agentic framework lifecycle.

This is the canonical example of how every future runtime agent
(Preventor, Compliance, …) should be built. It does **not** replace the
existing consumer pipeline; instead it delegates to the same analyser
and engine modules so behaviour is identical, while exposing the full
observe → recall → reason → decide → act → remember surface that the
framework provides.

The agent is opt-in: consumers can pick whether to call this or the
legacy :func:`services_api.brain.consumer.handle_pipeline_event` sequence.
Recall is additionally gated by the ``brain.memory_recall.enabled``
feature flag (default FALSE).

Part of AE-P1 / Agentic Foundation.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, ClassVar

import structlog
from agents.base import AgentDecision, AgentObservation, BaseAgent
from agents.llm_reasoner import BRAIN_SYSTEM_PROMPT, LLMReasoner
from events.bus import publish
from events.topics import Topic

from core.db import get_pool
from core.flags import get_flag
from services_api.brain.analyser import ChannelSignals, analyse_channel
from services_api.brain.engine import _evaluate, _write_decision

logger = structlog.get_logger()


class BrainAgent(BaseAgent):
    """Adaptive decision agent for video channels.

    Inputs: ``context = {"channel_id": str, "content_id": str | None}``
    Output: :class:`AgentDecision` matching brain_decisions schema, or None.
    """

    name: ClassVar[str] = "brain"
    decision_table: ClassVar[str] = "brain_decisions"
    flag_prefix: ClassVar[str] = "brain."

    _SOURCE = "brain-agent"
    _ALLOWED_DECISIONS = {"HALT", "HOLD", "NUDGE", "RESUME", "ADVISE", "NONE"}

    async def observe(self, context: dict[str, Any]) -> AgentObservation | None:
        channel_id = (context or {}).get("channel_id")
        if not channel_id:
            logger.warning("brain_agent.missing_channel_id", context=context)
            return None

        content_id = context.get("content_id")
        signals: ChannelSignals = await analyse_channel(channel_id)

        facts: dict[str, Any] = asdict(signals)
        facts["content_id"] = content_id

        return AgentObservation(
            scope="video" if content_id else "channel",
            scope_id=content_id or channel_id,
            facts=facts,
        )

    async def reason(
        self,
        observation: AgentObservation,
        memories: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Reconstruct the ChannelSignals and attach precedent."""
        facts = dict(observation.facts)
        content_id = facts.pop("content_id", None)

        signals = ChannelSignals(**{k: v for k, v in facts.items() if k in ChannelSignals.__dataclass_fields__})

        return {
            "signals": signals,
            "content_id": content_id,
            "memories": memories,
        }

    async def decide(self, state: dict[str, Any]) -> AgentDecision | None:
        """Pick the decision path: LLM reasoning if the flag is on,
        rule-based engine otherwise. Always falls back to rules on any
        LLM failure so the pipeline keeps working.
        """
        signals: ChannelSignals = state["signals"]
        content_id: str | None = state["content_id"]
        memories: list[dict[str, Any]] = state["memories"]

        use_llm = await get_flag("brain.llm_reasoning.enabled", default=False)
        if use_llm:
            llm_decision = await _llm_decide_impl(self, signals, content_id, memories)
            if llm_decision is not None:
                return llm_decision
            logger.info(
                "brain_agent.llm_decide_fallback_to_rules",
                channel_id=signals.channel_id,
            )

        raw = await _evaluate(signals, content_id)
        if raw is None:
            return None

        reasoning = raw.get("reasoning", "")
        if memories:
            reasoning = _enrich_reasoning_with_precedent(reasoning, memories)

        return AgentDecision(
            decision_type=raw["decision_type"],
            scope=raw.get("scope", "channel"),
            scope_id=raw.get("scope_id", signals.channel_id),
            directive=raw["directive"] if isinstance(raw["directive"], dict) else json.loads(raw["directive"]),
            reasoning=reasoning,
            confidence=float(raw.get("confidence") or 0),
            context_summary=raw.get("context_summary", ""),
            extras={
                "decision_id": raw["id"],
                "memories_used": len(memories),
                "reasoning_path": "rules",
            },
        )

    async def act(self, decision: AgentDecision) -> dict[str, Any]:
        """The legacy engine has already persisted the row inside decide();
        we just need to refresh ``reasoning`` if recall enriched it, then
        publish the directive event.
        """
        decision_id = decision.extras.get("decision_id")
        if decision_id is not None and decision.extras.get("memories_used", 0):
            try:
                pool = await get_pool()
                await pool.execute(
                    "UPDATE brain_decisions SET reasoning = $1 WHERE id = $2",
                    decision.reasoning,
                    decision_id,
                )
            except Exception as exc:
                logger.warning(
                    "brain_agent.update_reasoning_failed",
                    decision_id=decision_id,
                    error=str(exc),
                )

        try:
            await publish(
                Topic.BRAIN_DIRECTIVE,
                scope=decision.scope,
                scope_id=decision.scope_id,
                payload={
                    "decision_id": decision_id,
                    "decision_type": decision.decision_type,
                    "directive": decision.directive,
                    "reasoning": decision.reasoning,
                    "confidence": decision.confidence,
                    "memories_used": decision.extras.get("memories_used", 0),
                },
                source_service=self._SOURCE,
                confidence=decision.confidence,
            )
        except Exception as exc:
            logger.warning(
                "brain_agent.directive_publish_failed",
                decision_id=decision_id,
                error=str(exc),
            )

        return {"id": decision_id}

    async def remember(
        self,
        decision: AgentDecision,
        acted_row: dict[str, Any],
    ) -> None:
        return None


async def _llm_decide_impl(
    agent: "BrainAgent",
    signals: ChannelSignals,
    content_id: str | None,
    memories: list[dict[str, Any]],
) -> AgentDecision | None:
    """LLM-driven decision path.

    Composes a structured prompt from the channel signals + precedent,
    asks the router for a JSON response, validates it, persists via the
    same ``_write_decision`` path the rule engine uses, and returns an
    AgentDecision. Any failure returns ``None`` so the caller can fall
    back to rules.
    """
    user_prompt = _compose_user_prompt(signals, memories)
    reasoner = LLMReasoner(
        category="llm",
        system_prompt=BRAIN_SYSTEM_PROMPT,
        temperature=0.2,
        max_tokens=1024,
    )
    parsed = await reasoner.reason(
        user_prompt=user_prompt,
        channel_id=signals.channel_id,
        content_id=content_id or "",
        allowed_decision_types=agent._ALLOWED_DECISIONS,
    )
    if parsed is None:
        return None

    decision_type = parsed["decision_type"]
    if decision_type == "NONE":
        logger.info(
            "brain_agent.llm_decided_none",
            channel_id=signals.channel_id,
            confidence=parsed.get("confidence"),
        )
        return None

    reasoning_steps = parsed.get("reasoning_steps", [])
    reasoning = parsed["reasoning"]
    if reasoning_steps:
        reasoning += "\n\nSteps:\n- " + "\n- ".join(reasoning_steps)

    scope = "video" if content_id else "channel"
    scope_id = content_id or signals.channel_id

    written = await _write_decision(
        signals=signals,
        content_id=content_id,
        decision_type=decision_type,
        confidence=float(parsed["confidence"]),
        directive=parsed["directive"],
        reasoning=reasoning,
    )
    if written is None:
        return None

    return AgentDecision(
        decision_type=decision_type,
        scope=scope,
        scope_id=scope_id,
        directive=parsed["directive"],
        reasoning=reasoning,
        confidence=float(parsed["confidence"]),
        context_summary=written.get("context_summary", ""),
        extras={
            "decision_id": written["id"],
            "memories_used": len(memories),
            "reasoning_path": "llm",
            "reasoning_steps": reasoning_steps,
        },
    )


def _compose_user_prompt(signals: ChannelSignals, memories: list[dict[str, Any]]) -> str:
    """Build the user-side of the LLM prompt.

    Format is deliberately schema-like to anchor the model: every line
    is ``key: value`` so the LLM doesn't drift into narrative.
    """
    parts: list[str] = [
        "# Channel signals (current snapshot)",
        f"channel_id: {signals.channel_id}",
        f"total_delivered: {signals.total_delivered}",
        f"avg_composite_score: {signals.avg_composite_score}",
        f"recent_scores (newest first): {signals.recent_scores}",
        f"consecutive_failures: {signals.consecutive_failures}",
    ]
    if memories:
        parts.append("")
        parts.append("# Precedent (past decisions on this channel)")
        for m in memories[:5]:
            score = float(m.get("score") or 0)
            parts.append(
                f"- id={m.get('id')} type={m.get('decision_type')} "
                f"score={score:.2f} reasoning={(m.get('reasoning') or '')[:160]!r}"
            )
    else:
        parts.append("")
        parts.append("# Precedent: none")
    parts.append("")
    parts.append("Decide. Return the JSON object only.")
    return "\n".join(parts)


def _enrich_reasoning_with_precedent(reasoning: str, memories: list[dict[str, Any]]) -> str:
    """Prepend a compact precedent summary to *reasoning*.

    Format chosen to be human-readable in the dashboard AND machine-parseable
    by downstream consumers via the ``Precedent: `` prefix.
    """
    bits: list[str] = []
    for m in memories[:3]:
        score = float(m.get("score") or 0)
        bits.append(f"#{m.get('id')} {m.get('decision_type')} (score={score:.2f})")
    precedent_line = "Precedent: " + "; ".join(bits) + "."
    return f"{precedent_line}\n\n{reasoning}"
