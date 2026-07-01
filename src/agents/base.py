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

import asyncio
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, ClassVar

import structlog

logger = structlog.get_logger()

AGENT_DECISION_SCHEMA_VERSION = 1

DEFAULT_PHASE_TIMEOUTS_S: dict[str, float] = {
    "observe": 10.0,
    "recall": 8.0,
    "reason": 5.0,
    "decide": 30.0,
    "critique": 30.0,
    "act": 15.0,
    "remember": 30.0,
}

DEFAULT_ACT_MAX_ATTEMPTS = 3
DEFAULT_ACT_INITIAL_DELAY_S = 0.5
DEFAULT_ACT_MAX_DELAY_S = 4.0




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

    ``schema_version`` lets downstream consumers detect new optional
    fields (e.g. ``reasoning_steps`` once Critic / LLM-decide land).
    """
    decision_type: str
    scope: str
    scope_id: str
    directive: dict[str, Any]
    reasoning: str
    confidence: float
    context_summary: str = ""
    extras: dict[str, Any] = field(default_factory=dict)
    schema_version: int = AGENT_DECISION_SCHEMA_VERSION


CRITIC_VERDICTS = ("APPROVE", "VETO", "MODIFY")


@dataclass
class CriticVerdict:
    """Output of a Critic reviewing a peer agent's :class:`AgentDecision`.

    * ``APPROVE`` \u2192 original decision proceeds unchanged.
    * ``VETO``    \u2192 decision is dropped (logged as dead-letter).
    * ``MODIFY``  \u2192 caller substitutes ``modified_decision`` (which is
      a fresh AgentDecision) for the original. ``modified_decision`` MUST
      be set when verdict is ``MODIFY``.

    The Critic's reasoning is always recorded so the audit trail is
    complete \u2014 even on APPROVE.
    """
    verdict: str
    reasoning: str
    confidence: float
    reviewed_decision_type: str = ""
    reviewed_scope_id: str = ""
    modified_decision: "AgentDecision | None" = None
    extras: dict[str, Any] = field(default_factory=dict)




class BaseAgent(ABC):
    """Canonical lifecycle for runtime/product agents.

    Subclasses **must** set :attr:`name`, :attr:`decision_table`, and
    :attr:`flag_prefix`. Override the lifecycle methods you need; the rest
    stay as safe no-ops.
    """

    name: ClassVar[str] = ""

    decision_table: ClassVar[str] = ""

    flag_prefix: ClassVar[str] = ""

    phase_timeouts_s: ClassVar[dict[str, float]] = {}

    def __init__(self) -> None:
        if not self.name or not self.decision_table or not self.flag_prefix:
            raise TypeError(
                f"{type(self).__name__} must define name, decision_table, "
                "and flag_prefix class attributes."
            )

    def _timeout_for(self, phase: str) -> float:
        return float(
            self.phase_timeouts_s.get(phase, DEFAULT_PHASE_TIMEOUTS_S[phase])
        )


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


    async def run(self, context: dict[str, Any]) -> AgentDecision | None:
        """Run the full lifecycle for one input context.

        Each phase is:

        * **time-bounded** — wrapped in :func:`asyncio.wait_for` so a
          hung phase can't block the consumer indefinitely.
        * **isolated** — observe / recall / reason / remember failures
          are logged and don't kill the loop. decide / act failures
          propagate so the caller can apply its own policy.
        * **retried with backoff** — only ``act()``, because it's the
          one phase with externally-visible side-effects.
        """
        observation = await self._run_phase(
            "observe", lambda: self.observe(context), default=None
        )
        if observation is None:
            logger.debug("agent.observe_returned_none", agent=self.name)
            return None

        memories = await self._run_phase(
            "recall", lambda: self.recall(observation), default=[]
        )

        state = await self._run_phase(
            "reason",
            lambda: self.reason(observation, memories),
            default={"observation": observation, "memories": memories},
        )

        decision = await self._run_decide(state, observation)
        if decision is None:
            logger.debug(
                "agent.no_decision",
                agent=self.name,
                scope_id=observation.scope_id,
            )
            return None

        decision = await self._run_critique(decision, observation)
        if decision is None:
            return None

        acted = await self._run_act_with_retry(decision)
        if acted is None:
            await self._dead_letter(decision)
            return None

        asyncio.create_task(
            self._run_remember_bg(decision, acted),
            name=f"agent-remember-{self.name}",
        )

        logger.info(
            "agent.decision_complete",
            agent=self.name,
            decision_type=decision.decision_type,
            scope_id=observation.scope_id,
            confidence=decision.confidence,
            memories_recalled=len(memories),
        )
        return decision


    async def _run_phase(self, name: str, coro_fn, *, default):
        """Run ``coro_fn`` with a per-phase timeout, swallowing failures.

        Used for phases where partial / default results are acceptable:
        observe (None → skip), recall ([] → no precedent), reason
        (fallback state).
        """
        timeout = self._timeout_for(name)
        try:
            return await asyncio.wait_for(coro_fn(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "agent.phase_timeout", agent=self.name, phase=name,
                timeout_s=timeout,
            )
            return default
        except Exception as exc:
            logger.warning(
                "agent.phase_failed", agent=self.name, phase=name,
                error=str(exc),
            )
            return default

    async def _run_decide(self, state, observation):
        timeout = self._timeout_for("decide")
        try:
            return await asyncio.wait_for(self.decide(state), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(
                "agent.phase_timeout", agent=self.name, phase="decide",
                timeout_s=timeout, scope_id=observation.scope_id,
            )
            return None

    async def _run_act_with_retry(
        self, decision: AgentDecision
    ) -> dict[str, Any] | None:
        """Run ``act()`` with exponential backoff + jitter.

        Returns the acted-row dict on success, or ``None`` after all
        attempts fail (caller dead-letters).
        """
        import random
        timeout = self._timeout_for("act")
        delay = DEFAULT_ACT_INITIAL_DELAY_S
        last_error: str | None = None
        for attempt in range(1, DEFAULT_ACT_MAX_ATTEMPTS + 1):
            try:
                return await asyncio.wait_for(
                    self.act(decision), timeout=timeout
                )
            except asyncio.TimeoutError:
                last_error = f"timeout after {timeout}s"
            except Exception as exc:
                last_error = str(exc)
            logger.warning(
                "agent.act_attempt_failed", agent=self.name,
                attempt=attempt, max_attempts=DEFAULT_ACT_MAX_ATTEMPTS,
                error=last_error, decision_type=decision.decision_type,
            )
            if attempt < DEFAULT_ACT_MAX_ATTEMPTS:
                await asyncio.sleep(
                    random.uniform(0, min(delay, DEFAULT_ACT_MAX_DELAY_S))
                )
                delay *= 2
        logger.error(
            "agent.act_exhausted", agent=self.name,
            decision_type=decision.decision_type, last_error=last_error,
        )
        return None

    async def _run_critique(
        self,
        decision: AgentDecision,
        observation: AgentObservation,
    ) -> AgentDecision | None:
        """Optionally run a Critic peer over ``decision`` before act().

        Two flags must both be TRUE for critique to fire:

        * ``critic.enabled`` — global kill switch
        * ``<flag_prefix>critic_review.enabled`` — per-agent opt-in

        On VETO the decision is dead-lettered and ``None`` is returned.
        On MODIFY the substituted decision is returned. On APPROVE (or
        any failure / disabled state) the original decision passes through
        unchanged. The Critic itself is never critiqued (no recursion).
        """
        if self.name == "critic":
            return decision

        try:
            from src.flags import get_flag
            global_on = await get_flag("critic.enabled", default=False)
            if not global_on:
                return decision
            agent_on = await get_flag(
                f"{self.flag_prefix}critic_review.enabled", default=False
            )
            if not agent_on:
                return decision
        except Exception as exc:
            logger.warning(
                "agent.critique_flag_read_failed",
                agent=self.name, error=str(exc),
            )
            return decision

        try:
            from src.agents.registry import AgentRegistry
            critic = AgentRegistry.get("critic")
        except Exception:
            critic = None
        if critic is None:
            logger.warning(
                "agent.critique_skipped_no_critic", agent=self.name,
            )
            return decision

        review = getattr(critic, "review", None)
        if review is None:
            logger.warning(
                "agent.critique_skipped_no_review_method", agent=self.name,
            )
            return decision

        timeout = self._timeout_for("critique")
        try:
            verdict: CriticVerdict = await asyncio.wait_for(
                review(
                    decision=decision,
                    observation=observation,
                    peer_agent_name=self.name,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "agent.critique_timeout", agent=self.name,
                timeout_s=timeout, scope_id=observation.scope_id,
            )
            return decision
        except Exception as exc:
            logger.warning(
                "agent.critique_failed", agent=self.name,
                error=str(exc), scope_id=observation.scope_id,
            )
            return decision

        verdict_str = getattr(verdict, "verdict", None)
        if verdict_str == "VETO":
            logger.info(
                "agent.critique_vetoed",
                agent=self.name,
                decision_type=decision.decision_type,
                scope_id=observation.scope_id,
                critic_reasoning=getattr(verdict, "reasoning", "")[:200],
                critic_confidence=getattr(verdict, "confidence", None),
            )
            await self._dead_letter(decision)
            return None
        if verdict_str == "MODIFY":
            modified = getattr(verdict, "modified_decision", None)
            if modified is None:
                logger.warning(
                    "agent.critique_modify_without_decision",
                    agent=self.name,
                )
                return decision
            logger.info(
                "agent.critique_modified",
                agent=self.name,
                original_type=decision.decision_type,
                modified_type=modified.decision_type,
                scope_id=observation.scope_id,
                critic_reasoning=getattr(verdict, "reasoning", "")[:200],
            )
            return modified
        if verdict_str == "APPROVE":
            logger.debug(
                "agent.critique_approved", agent=self.name,
                scope_id=observation.scope_id,
            )
        else:
            logger.warning(
                "agent.critique_unknown_verdict",
                agent=self.name, verdict=verdict_str,
            )
        return decision

    async def _run_remember_bg(
        self, decision: AgentDecision, acted_row: dict[str, Any]
    ) -> None:
        """Background task entry-point for :meth:`remember`.

        Wraps :meth:`remember` in a timeout + try/except so a stuck
        embedding call can never leak a runaway task.
        """
        timeout = self._timeout_for("remember")
        try:
            await asyncio.wait_for(
                self.remember(decision, acted_row), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                "agent.remember_timeout", agent=self.name,
                timeout_s=timeout,
                decision_id=acted_row.get("id"),
            )
        except Exception as exc:
            logger.warning(
                "agent.remember_bg_failed", agent=self.name,
                decision_id=acted_row.get("id"),
                error=str(exc),
            )

    async def _dead_letter(self, decision: AgentDecision) -> None:
        """Record a decision whose ``act()`` failed past all retries.

        Default writes a structured log entry. Subclasses can override to
        push to a DLQ table or alerting channel.
        """
        logger.error(
            "agent.decision_dead_lettered",
            agent=self.name,
            decision_type=decision.decision_type,
            scope=decision.scope,
            scope_id=decision.scope_id,
            reasoning=decision.reasoning[:200],
            confidence=decision.confidence,
        )
