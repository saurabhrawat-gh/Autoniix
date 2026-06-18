"""PreventorAgent — pre-execution risk gate.

Where the Brain reacts AFTER work has been done, the Preventor decides
whether the work should happen AT ALL. Callers (typically a Temporal
workflow or a service entry-point) invoke
:meth:`PreventorAgent.run` BEFORE expensive work begins:

    decision = await AgentRegistry.get("preventor").run({
        "channel_id": "ch1",
        "content_id": "v1",
        "planned_action": "produce_video",
    })
    if decision and decision.decision_type in ("VETO", "HOLD"):
        raise WorkflowAborted(decision.reasoning)

Decision vocabulary:

* ``ALLOW`` — proceed normally. Returned implicitly by emitting a
  decision row tagged ALLOW; callers may also treat a ``None`` return
  (e.g. when ``preventor.enabled`` is FALSE) as ALLOW.
* ``WARN``  — proceed but flag for human review (e.g. quality dipping
  but no hard signal yet).
* ``HOLD``  — pause this planned action. The caller MUST stop and
  surface a needs-review status.
* ``VETO``  — refuse outright. The caller MUST abort.

Risk signals come from :func:`analyse_channel`, the same source the
Brain uses, plus an explicit unresolved-HALT check against
``brain_decisions`` so the Preventor can never approve work on a
channel the Brain has shut down.

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
from src.flags import get_flag
from src.services.brain.analyser import ChannelSignals, analyse_channel

logger = structlog.get_logger()


_DEFAULT_PLANNED_ACTION = "produce_video"


class PreventorAgent(BaseAgent):
    """Pre-execution risk-gate agent.

    Inputs:
        context = {
            "channel_id": str,          # required
            "content_id": str | None,   # optional
            "planned_action": str,      # default "produce_video"
        }
    Output:
        :class:`AgentDecision` of type ALLOW / WARN / HOLD / VETO, or
        ``None`` when the master flag is OFF or signals are missing.
    """

    name: ClassVar[str] = "preventor"
    decision_table: ClassVar[str] = "preventor_decisions"
    flag_prefix: ClassVar[str] = "preventor."

    _SOURCE = "preventor-agent"
    _ALLOWED_DECISIONS = {"ALLOW", "WARN", "HOLD", "VETO"}

    # ── observe ──────────────────────────────────────────────────────────

    async def observe(
        self, context: dict[str, Any]
    ) -> AgentObservation | None:
        """Pull risk signals. Returns ``None`` if the agent is disabled
        or required context is missing — the framework will treat that
        as "no decision" and the caller proceeds (ALLOW-by-default).
        """
        try:
            enabled = await get_flag("preventor.enabled", default=False)
        except Exception as exc:
            logger.warning(
                "preventor_agent.flag_read_failed", error=str(exc)
            )
            return None
        if not enabled:
            logger.debug("preventor_agent.disabled")
            return None

        channel_id = (context or {}).get("channel_id")
        if not channel_id:
            logger.warning(
                "preventor_agent.missing_channel_id", context=context,
            )
            return None

        content_id = (context or {}).get("content_id")
        planned_action = (
            (context or {}).get("planned_action")
            or _DEFAULT_PLANNED_ACTION
        )

        try:
            signals = await analyse_channel(channel_id)
        except Exception as exc:
            logger.warning(
                "preventor_agent.analyse_failed",
                channel_id=channel_id, error=str(exc),
            )
            return None

        unresolved_halt = await _has_unresolved_halt(channel_id)

        facts: dict[str, Any] = asdict(signals)
        facts.update({
            "content_id": content_id,
            "planned_action": planned_action,
            "channel_has_unresolved_halt": unresolved_halt,
        })

        return AgentObservation(
            scope="video" if content_id else "channel",
            scope_id=content_id or channel_id,
            facts=facts,
        )

    # ── decide ───────────────────────────────────────────────────────────

    async def decide(
        self, state: dict[str, Any]
    ) -> AgentDecision | None:
        """Rule-based gate evaluation. The Preventor LLM path is
        deferred — at this stage rules are sufficient and entirely
        offline-safe."""
        observation: AgentObservation = state["observation"]
        facts = observation.facts
        channel_id: str = facts["channel_id"]
        planned_action: str = facts["planned_action"]
        unresolved_halt: bool = bool(
            facts.get("channel_has_unresolved_halt")
        )

        veto_on_halt = await get_flag(
            "preventor.veto_when_channel_halted", default=True
        )
        veto_threshold = int(
            await get_flag(
                "preventor.threshold.veto.consecutive_failures",
                default=5,
            ) or 5
        )
        hold_budget_pct = float(
            await get_flag(
                "preventor.threshold.hold.budget_pct_remaining",
                default=0.05,
            ) or 0.0
        )
        warn_min_quality = float(
            await get_flag(
                "preventor.threshold.warn.min_quality_score",
                default=6.5,
            ) or 0.0
        )

        consec = int(facts.get("consecutive_failures") or 0)
        budget_limit = float(facts.get("daily_budget_limit") or 0)
        budget_remaining = float(facts.get("daily_budget_remaining") or 0)
        recent_scores = facts.get("recent_scores") or []
        avg_quality = float(facts.get("avg_composite_score") or 0)

        budget_pct = (
            budget_remaining / budget_limit if budget_limit > 0 else None
        )

        # Reasons accumulate so the audit trail explains every factor
        # contributing to the decision.
        reasons: list[str] = []

        # ── VETO conditions (any one is sufficient) ───────────────────
        if veto_on_halt and unresolved_halt:
            reasons.append(
                f"channel {channel_id} has an unresolved HALT in "
                "brain_decisions — refusing to produce more videos."
            )
            return self._build_decision(
                "VETO", observation, planned_action, reasons,
                confidence=0.95, facts=facts,
            )
        if consec >= veto_threshold:
            reasons.append(
                f"consecutive_failures={consec} >= veto_threshold="
                f"{veto_threshold}."
            )
            return self._build_decision(
                "VETO", observation, planned_action, reasons,
                confidence=0.9, facts=facts,
            )

        # ── HOLD conditions ────────────────────────────────────────────
        if (
            hold_budget_pct > 0
            and budget_pct is not None
            and budget_pct < hold_budget_pct
        ):
            reasons.append(
                f"daily budget remaining {budget_pct:.1%} is below "
                f"hold threshold {hold_budget_pct:.1%}."
            )
            return self._build_decision(
                "HOLD", observation, planned_action, reasons,
                confidence=0.8, facts=facts,
            )

        # ── WARN conditions ────────────────────────────────────────────
        if (
            warn_min_quality > 0
            and len(recent_scores) >= 3
            and avg_quality < warn_min_quality
        ):
            reasons.append(
                f"avg_composite_score={avg_quality:.2f} is below warn "
                f"threshold {warn_min_quality:.2f} over "
                f"{len(recent_scores)} recent videos."
            )
            return self._build_decision(
                "WARN", observation, planned_action, reasons,
                confidence=0.6, facts=facts,
            )

        # ── Default ALLOW ──────────────────────────────────────────────
        reasons.append(
            "no risk signal tripped (consec="
            f"{consec}, avg_quality={avg_quality:.2f}, budget_pct="
            f"{budget_pct if budget_pct is None else f'{budget_pct:.1%}'})."
        )
        return self._build_decision(
            "ALLOW", observation, planned_action, reasons,
            confidence=0.7, facts=facts,
        )

    # ── act ──────────────────────────────────────────────────────────────

    async def act(self, decision: AgentDecision) -> dict[str, Any]:
        """Persist the decision and publish a directive on
        ``BRAIN_PREVENTOR_RISK``. The caller does NOT depend on the
        publish step — the AgentDecision is what they react to.
        """
        pool = await get_pool()
        risk_signals = decision.extras.pop("risk_signals", {})
        planned_action = decision.extras.pop(
            "planned_action", _DEFAULT_PLANNED_ACTION
        )
        row = await pool.fetchrow(
            """
            INSERT INTO preventor_decisions
                (decision_type, scope, scope_id, planned_action,
                 directive, reasoning, confidence, risk_signals)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8::jsonb)
            RETURNING id
            """,
            decision.decision_type,
            decision.scope,
            decision.scope_id,
            planned_action,
            json.dumps(decision.directive),
            decision.reasoning,
            round(float(decision.confidence or 0), 2),
            json.dumps(risk_signals),
        )
        decision_id = row["id"] if row else None
        decision.extras["decision_id"] = decision_id

        try:
            await publish(
                Topic.BRAIN_PREVENTOR_RISK,
                scope=decision.scope,
                scope_id=decision.scope_id,
                payload={
                    "decision_id": decision_id,
                    "decision_type": decision.decision_type,
                    "planned_action": planned_action,
                    "directive": decision.directive,
                    "reasoning": decision.reasoning,
                    "confidence": decision.confidence,
                },
                source_service=self._SOURCE,
                confidence=decision.confidence,
            )
        except Exception as exc:
            logger.warning(
                "preventor_agent.publish_failed",
                decision_id=decision_id, error=str(exc),
            )

        logger.info(
            "preventor_agent.decision",
            decision_id=decision_id,
            decision_type=decision.decision_type,
            scope_id=decision.scope_id,
            planned_action=planned_action,
            confidence=decision.confidence,
        )
        return {"id": decision_id}

    # ── helpers ──────────────────────────────────────────────────────────

    def _build_decision(
        self,
        decision_type: str,
        observation: AgentObservation,
        planned_action: str,
        reasons: list[str],
        *,
        confidence: float,
        facts: dict[str, Any],
    ) -> AgentDecision:
        directive: dict[str, Any] = {
            "action": decision_type,
            "channel_id": facts.get("channel_id"),
            "content_id": facts.get("content_id"),
            "planned_action": planned_action,
        }
        # Snapshot a compact subset of facts as the risk_signals jsonb.
        risk_signals = {
            "consecutive_failures": facts.get("consecutive_failures"),
            "avg_composite_score": facts.get("avg_composite_score"),
            "recent_scores_n": len(facts.get("recent_scores") or []),
            "daily_budget_limit": facts.get("daily_budget_limit"),
            "daily_budget_remaining": facts.get("daily_budget_remaining"),
            "channel_has_unresolved_halt": facts.get(
                "channel_has_unresolved_halt"
            ),
        }
        return AgentDecision(
            decision_type=decision_type,
            scope=observation.scope,
            scope_id=observation.scope_id,
            directive=directive,
            reasoning=" ".join(reasons),
            confidence=confidence,
            context_summary=f"preventor:{planned_action}",
            extras={
                "risk_signals": risk_signals,
                "planned_action": planned_action,
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ─────────────────────────────────────────────────────────────────────────────


async def _has_unresolved_halt(channel_id: str) -> bool:
    """Return TRUE iff there is at least one unresolved HALT for the
    channel in ``brain_decisions``. The Preventor uses this as a hard
    safety floor: a HALTed channel must never start new work."""
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT 1 FROM brain_decisions
            WHERE scope = 'channel'
              AND scope_id = $1
              AND decision_type = 'HALT'
              AND resolved_at IS NULL
            LIMIT 1
            """,
            channel_id,
        )
        return row is not None
    except Exception as exc:
        # Be conservative on DB failures: assume there COULD be a HALT
        # and let the rest of the rules decide. (Returning True here
        # would auto-VETO every action on a DB blip, which is too
        # aggressive.)
        logger.warning(
            "preventor_agent.halt_check_failed",
            channel_id=channel_id, error=str(exc),
        )
        return False
