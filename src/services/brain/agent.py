"""BrainAgent — :class:`BaseAgent` implementation that wraps the existing
analyser / engine into the agentic framework lifecycle.

This is the canonical example of how every future runtime agent
(Preventor, Compliance, …) should be built. It does **not** replace the
existing consumer pipeline; instead it delegates to the same analyser
and engine modules so behaviour is identical, while exposing the full
observe → recall → reason → decide → act → remember surface that the
framework provides.

The agent is opt-in: consumers can pick whether to call this or the
legacy :func:`src.services.brain.consumer.handle_pipeline_event` sequence.
Recall is additionally gated by the ``brain.memory_recall.enabled``
feature flag (default FALSE).

Part of AE-P1 / Agentic Foundation.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, ClassVar

import structlog

from src.agents.base import AgentDecision, AgentObservation, BaseAgent
from src.db import get_pool
from src.events.bus import publish
from src.events.topics import Topic
from src.services.brain.analyser import ChannelSignals, analyse_channel
from src.services.brain.engine import _evaluate

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

    # ── observe ──────────────────────────────────────────────────────────

    async def observe(self, context: dict[str, Any]) -> AgentObservation | None:
        channel_id = (context or {}).get("channel_id")
        if not channel_id:
            logger.warning("brain_agent.missing_channel_id", context=context)
            return None

        content_id = context.get("content_id")
        signals: ChannelSignals = await analyse_channel(channel_id)

        # Carry the full ChannelSignals dict so reason()/decide() have it.
        facts: dict[str, Any] = asdict(signals)
        facts["content_id"] = content_id

        return AgentObservation(
            scope="video" if content_id else "channel",
            scope_id=content_id or channel_id,
            facts=facts,
        )

    # ── reason ───────────────────────────────────────────────────────────

    async def reason(
        self,
        observation: AgentObservation,
        memories: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Reconstruct the ChannelSignals and attach precedent."""
        facts = dict(observation.facts)
        content_id = facts.pop("content_id", None)

        # Recreate the dataclass so the engine's thresholds work unchanged.
        signals = ChannelSignals(**{
            k: v for k, v in facts.items()
            if k in ChannelSignals.__dataclass_fields__
        })

        return {
            "signals": signals,
            "content_id": content_id,
            "memories": memories,
        }

    # ── decide ───────────────────────────────────────────────────────────

    async def decide(self, state: dict[str, Any]) -> AgentDecision | None:
        signals: ChannelSignals = state["signals"]
        content_id: str | None = state["content_id"]
        memories: list[dict[str, Any]] = state["memories"]

        # Delegate the threshold logic to the existing engine. Translate
        # its dict output (or None) back into an AgentDecision.
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
            directive=raw["directive"]
            if isinstance(raw["directive"], dict)
            else json.loads(raw["directive"]),
            reasoning=reasoning,
            confidence=float(raw.get("confidence") or 0),
            context_summary=raw.get("context_summary", ""),
            extras={"decision_id": raw["id"], "memories_used": len(memories)},
        )

    # ── act ──────────────────────────────────────────────────────────────

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

    # ── remember ─────────────────────────────────────────────────────────

    # The legacy engine path already calls embed_and_store inside
    # _write_decision, so the default remember() in BaseAgent would
    # double-embed. Override to a no-op until the legacy path is retired.
    async def remember(
        self,
        decision: AgentDecision,
        acted_row: dict[str, Any],
    ) -> None:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _enrich_reasoning_with_precedent(
    reasoning: str, memories: list[dict[str, Any]]
) -> str:
    """Prepend a compact precedent summary to *reasoning*.

    Format chosen to be human-readable in the dashboard AND machine-parseable
    by downstream consumers via the ``Precedent: `` prefix.
    """
    bits: list[str] = []
    for m in memories[:3]:
        score = float(m.get("score") or 0)
        bits.append(
            f"#{m.get('id')} {m.get('decision_type')} "
            f"(score={score:.2f})"
        )
    precedent_line = "Precedent: " + "; ".join(bits) + "."
    return f"{precedent_line}\n\n{reasoning}"
