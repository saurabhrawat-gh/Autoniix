"""BaseAgent — canonical lifecycle every runtime agent inherits.

The lifecycle is intentionally explicit:

    obs        = await agent.observe(context)        # structured facts
    memories   = await agent.recall(obs)             # similar past decisions
    state      = await agent.reason(obs, memories)   # internal reasoning state
    decision   = await agent.decide(state)           # AgentDecision | None
    if decision is not None:
        await agent.act(decision)
        await agent.remember(decision)

The framework guarantees:

* Every step is async and isolated — subclasses can override only what they
  need; defaults are sensible no-ops.
* Exceptions in any step are caught at the orchestration layer
  (:meth:`BaseAgent.run`) so a buggy ``recall`` never blocks ``decide``.
* The decision is structurally typed (:class:`AgentDecision`) so downstream
  consumers (event bus, Temporal signals) never have to introspect.

Subclasses choose their own:

* ``decision_table`` — the SQL table where past decisions live (used by
  :class:`AgentMemory` for recall).
* ``flag_prefix`` — the feature-flag prefix used by the agent
  (e.g. ``brain.``, ``preventor.``). This makes every threshold and toggle
  per-agent tunable via the ``feature_flags`` table without a deploy.

Part of AE-P1 / Agentic Foundation.
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, ClassVar

import structlog

logger = structlog.get_logger()


# ─────────────────────────────────────────────────────────────────────────────
# Data carriers
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AgentObservation:
    """Structured observation produced by ``observe()``.

    ``scope`` / ``scope_id`` mirror the event-bus envelope convention so
    downstream events stay routable.
    """
    scope: str
    scope_id: str
    facts: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentDecision:
    """Output of ``decide()``.

    The shape matches what gets written to ``<decision_table>`` and what
    gets published on the event bus, so ``act()`` is a trivial mapping.
    """
    decision_type: str
    scope: str
    scope_id: str
    directive: dict[str, Any]
    reasoning: str
    confidence: float
    # Free-form structured context summary string — kept for parity with
    # brain_decisions schema. Subclasses can build it however they like.
    context_summary: str = ""
    # Optional: subclass-specific extras carried into act() / remember().
    extras: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# BaseAgent
# ─────────────────────────────────────────────────────────────────────────────


class BaseAgent(ABC):
    """Canonical lifecycle for runtime/product agents.

    Subclasses **must** set :attr:`name`, :attr:`decision_table`, and
    :attr:`flag_prefix`. Override the lifecycle methods you need; the rest
    stay as safe no-ops.
    """

    #: Short stable identifier for the agent. Used in logs, metrics, and as
    #: the key in :class:`AgentRegistry`.
    name: ClassVar[str] = ""

    #: SQL table where this agent's decisions are persisted. The table must
    #: have the columns ``id, decision_type, scope, scope_id, directive,
    #: reasoning, confidence, embedding, created_at`` for default
    #: :class:`AgentMemory` recall to work.
    decision_table: ClassVar[str] = ""

    #: Feature-flag prefix (e.g. ``"brain."``) — every flag this agent
    #: reads should start with this prefix to make per-agent tuning easy.
    flag_prefix: ClassVar[str] = ""

    def __init__(self) -> None:
        if not self.name or not self.decision_table or not self.flag_prefix:
            raise TypeError(
                f"{type(self).__name__} must define name, decision_table, "
                "and flag_prefix class attributes."
            )

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def observe(self, context: dict[str, Any]) -> AgentObservation | None:
        """Pull structured facts from the world.

        Default is a no-op returning ``None`` (which short-circuits the
        rest of the loop). Subclasses typically query the DB here.
        """
        return None

    async def recall(
        self, observation: AgentObservation
    ) -> list[dict[str, Any]]:
        """Return similar past decisions for ``observation``.

        Default uses the agent's :class:`AgentMemory` instance. Override
        only when you need a non-standard retrieval strategy.

        Failure is non-fatal: returns ``[]`` and logs a warning.
        """
        try:
            from src.agents.memory import AgentMemory
            memory = AgentMemory(
                agent_name=self.name,
                table=self.decision_table,
            )
            result = await memory.recall_for_observation(observation)
            return result.rows
        except Exception as exc:
            logger.warning(
                "agent.recall_failed",
                agent=self.name,
                scope_id=observation.scope_id,
                error=str(exc),
            )
            return []

    async def reason(
        self,
        observation: AgentObservation,
        memories: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Combine observation + memories into an internal reasoning state.

        Default returns a dict carrying both. Subclasses typically merge,
        score, or compute derived metrics here.
        """
        return {"observation": observation, "memories": memories}

    async def decide(
        self, state: dict[str, Any]
    ) -> AgentDecision | None:
        """Produce a structured decision, or ``None`` for no-op.

        This is the only method most agents *must* override.
        """
        return None

    async def act(self, decision: AgentDecision) -> dict[str, Any]:
        """Persist the decision and emit side-effects.

        Default raises :class:`NotImplementedError` — every agent must
        implement this; it's the side-effect boundary. Returns the
        persisted row (or any structured ack) so :meth:`remember` can
        reference it.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.act() must be implemented."
        )

    async def remember(
        self,
        decision: AgentDecision,
        acted_row: dict[str, Any],
    ) -> None:
        """Persist embedding (or other long-term memory) for this decision.

        Default delegates to :class:`AgentMemory.remember`. Override to
        change embedding text composition or to skip embedding entirely.
        """
        try:
            from src.agents.memory import AgentMemory
            memory = AgentMemory(
                agent_name=self.name,
                table=self.decision_table,
            )
            await memory.remember(decision, acted_row)
        except Exception as exc:
            logger.warning(
                "agent.remember_failed",
                agent=self.name,
                decision_id=acted_row.get("id"),
                error=str(exc),
            )

    # ── Orchestration ────────────────────────────────────────────────────

    async def run(self, context: dict[str, Any]) -> AgentDecision | None:
        """Run the full lifecycle for one input context.

        Each phase is isolated: a failure in ``recall`` or ``remember``
        does not block ``decide`` / ``act``. Only ``decide`` and ``act``
        propagate exceptions (the caller decides what to do).
        """
        observation = await self.observe(context)
        if observation is None:
            logger.debug("agent.observe_returned_none", agent=self.name)
            return None

        memories = await self.recall(observation)

        state = await self.reason(observation, memories)

        decision = await self.decide(state)
        if decision is None:
            logger.debug(
                "agent.no_decision",
                agent=self.name,
                scope_id=observation.scope_id,
            )
            return None

        acted = await self.act(decision)

        # remember() is fire-and-forget at the loop level — failures are
        # already swallowed inside.
        await self.remember(decision, acted)

        logger.info(
            "agent.decision_complete",
            agent=self.name,
            decision_type=decision.decision_type,
            scope_id=observation.scope_id,
            confidence=decision.confidence,
            memories_recalled=len(memories),
        )
        return decision
