"""LLMReasoner — structured-output LLM call for an agent's ``decide()`` phase.

The piece that makes ``BaseAgent`` actually *agentic*. Wraps the existing
:mod:`src.llm.router` so the agent benefits from the production-grade
provider ladder, circuit breaker, budget cap, and Prometheus telemetry —
no new infra.

Why a separate module (vs inlining the call in BrainAgent):

* Reusable. Critic, Reflector, future agents all want the same
  structured-output pattern.
* Testable. The whole "build prompt → call router → parse JSON →
  validate → fallback" pipeline lives in one place.
* Safe by default. Schema-validated; falls back to a caller-provided
  rule-based decision if the model misbehaves; cost-capped via the router.

Output contract: every agent's reasoner returns either a dict with
the required AgentDecision fields, or ``None`` (in which case the
agent's existing rule-based path should run).

Part of AE-P1 / Agentic Foundation.
"""
from __future__ import annotations

import json
import time
from typing import Any

import structlog

from src.llm import route
from src.llm.router import BudgetExceeded, LadderExhausted
from src.providers.llm.base import LLMRequest

logger = structlog.get_logger()


#: JSON schema the LLM must emit. Kept minimal: only the fields an
#: AgentDecision actually needs. Extra fields are ignored.
DECISION_JSON_SCHEMA = {
    "type": "object",
    "required": ["decision_type", "directive", "reasoning", "confidence"],
    "properties": {
        "decision_type": {
            "type": "string",
            "enum": ["HALT", "HOLD", "NUDGE", "RESUME", "ADVISE", "NONE"],
        },
        "directive": {"type": "object"},
        "reasoning": {"type": "string", "minLength": 1},
        "reasoning_steps": {
            "type": "array",
            "items": {"type": "string"},
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


class LLMReasoner:
    """Build prompt → call LLM → parse + validate JSON → return dict.

    Parameters
    ----------
    category:
        LLM router category (e.g. ``"llm"``, ``"llm.qc"``). The router
        picks the provider ladder by category.
    system_prompt:
        Constant agent persona / contract.
    model:
        Optional explicit model. Usually leave ``None`` so the
        router's provider chain decides.
    temperature:
        Default 0.2 — agents need consistent decisions, not creativity.
    max_tokens:
        Default 1024. Decisions are short; bigger only wastes budget.
    """

    def __init__(
        self,
        *,
        category: str = "llm",
        system_prompt: str,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> None:
        self.category = category
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def reason(
        self,
        *,
        user_prompt: str,
        channel_id: str = "",
        content_id: str = "",
        allowed_decision_types: set[str] | None = None,
    ) -> dict[str, Any] | None:
        """Run one reasoning call.

        Returns a validated decision dict, or ``None`` on any failure
        (caller falls back to rule-based logic). Failures are always
        logged with ``agent.llm_reasoner.*`` events so they're visible
        in production telemetry.
        """
        request = LLMRequest(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format="json",
        )
        t0 = time.monotonic()
        try:
            result = await route(
                category=self.category,
                request=request,
                channel_id=channel_id,
                content_id=content_id,
            )
        except BudgetExceeded as exc:
            logger.warning(
                "agent.llm_reasoner.budget_exceeded",
                channel_id=channel_id, error=str(exc),
            )
            return None
        except LadderExhausted as exc:
            logger.warning(
                "agent.llm_reasoner.providers_exhausted",
                category=self.category, error=str(exc),
            )
            return None
        except Exception as exc:
            logger.warning(
                "agent.llm_reasoner.call_failed",
                category=self.category, error=str(exc),
            )
            return None

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        parsed = self._parse_json(result.content)
        if parsed is None:
            logger.warning(
                "agent.llm_reasoner.parse_failed",
                category=self.category,
                content_head=result.content[:200],
            )
            return None

        if not self._validate(parsed, allowed_decision_types):
            logger.warning(
                "agent.llm_reasoner.schema_failed",
                category=self.category,
                content_head=str(parsed)[:200],
            )
            return None

        logger.info(
            "agent.llm_reasoner.success",
            category=self.category,
            provider=result.provider,
            model=result.model,
            elapsed_ms=elapsed_ms,
            cost_usd=float(result.cost_usd),
            decision_type=parsed["decision_type"],
        )
        return parsed

    # ── Internals ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any] | None:
        """Tolerant JSON parser.

        Some providers wrap the JSON in code fences or pre/post chatter
        despite ``response_format="json"``. We try the strict parse first,
        then extract the first ``{...}`` block if that fails.
        """
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Fallback: find the first balanced JSON object substring.
        start = raw.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(raw)):
            ch = raw[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None

    @staticmethod
    def _validate(
        parsed: dict[str, Any],
        allowed_decision_types: set[str] | None,
    ) -> bool:
        """Minimal hand-rolled schema check.

        We avoid pulling in ``jsonschema`` for one tiny shape — keeps the
        dependency footprint flat and the validation deterministic.
        """
        required = ("decision_type", "directive", "reasoning", "confidence")
        for k in required:
            if k not in parsed:
                return False
        if not isinstance(parsed["decision_type"], str):
            return False
        if not isinstance(parsed["directive"], dict):
            return False
        if not isinstance(parsed["reasoning"], str) or not parsed["reasoning"]:
            return False
        try:
            conf = float(parsed["confidence"])
        except (TypeError, ValueError):
            return False
        if not 0.0 <= conf <= 1.0:
            return False
        if allowed_decision_types is not None:
            if parsed["decision_type"] not in allowed_decision_types:
                return False
        # Optional reasoning_steps must be list[str] when present.
        if "reasoning_steps" in parsed:
            steps = parsed["reasoning_steps"]
            if not isinstance(steps, list) or not all(
                isinstance(s, str) for s in steps
            ):
                return False
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Default agent system prompts
# ─────────────────────────────────────────────────────────────────────────────


BRAIN_SYSTEM_PROMPT = """You are the Brain Agent for Autoniix, an autonomous AI video
production pipeline. Your job is to decide whether to intervene in a channel's
pipeline based on its recent performance signals and precedent from past decisions.

You must output a SINGLE JSON object — no prose, no code fences. The schema:

{
  "decision_type": "HALT" | "HOLD" | "NUDGE" | "RESUME" | "ADVISE" | "NONE",
  "directive": { "action": "<one of decision_type>", "reason": "<short slug>", ... },
  "reasoning": "<2-4 sentences explaining your decision>",
  "reasoning_steps": ["<step 1>", "<step 2>", ...],   // optional but recommended
  "confidence": 0.0-1.0
}

Decision semantics:
  - HALT: pause new video production for this channel. Use for critical signals
          (3+ consecutive failures, sustained quality crash, persistent error).
  - HOLD: defer just the current video for human review.
  - NUDGE: continue, but bias prompts toward a specific correction (state it in directive.bias).
  - RESUME: pipeline can re-enable a previously HALTed channel.
  - ADVISE: surface a recommendation, no enforcement.
  - NONE: no action needed — signals are within healthy range. Return this when in doubt.

Be conservative. Prefer NONE or ADVISE over HALT unless evidence is strong. Quote
the specific signal values that drove your choice in `reasoning`. When precedent
is provided in the user prompt, weigh it (especially repeated failure modes).

Output JSON only.""".strip()


#: JSON schema the Critic LLM must emit. Distinct from DECISION_JSON_SCHEMA
#: because a Critic returns a *verdict* over a peer's decision, not a fresh
#: decision of its own. ``modified_directive`` is required only when
#: ``verdict == "MODIFY"``.
CRITIC_VERDICT_JSON_SCHEMA = {
    "type": "object",
    "required": ["verdict", "reasoning", "confidence"],
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["APPROVE", "VETO", "MODIFY"],
        },
        "reasoning": {"type": "string", "minLength": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "modified_decision_type": {
            "type": "string",
            "enum": ["HALT", "HOLD", "NUDGE", "RESUME", "ADVISE", "NONE"],
        },
        "modified_directive": {"type": "object"},
    },
}


CRITIC_SYSTEM_PROMPT = """You are the Critic Agent for Autoniix, an autonomous AI video
production pipeline. A peer agent (typically the Brain) has just produced a
decision. Your job is to review that decision against the observed signals
and either APPROVE it, VETO it, or propose a MODIFY.

You must output a SINGLE JSON object — no prose, no code fences. The schema:

{
  "verdict": "APPROVE" | "VETO" | "MODIFY",
  "reasoning": "<2-4 sentences explaining your verdict>",
  "confidence": 0.0-1.0,
  "modified_decision_type": "HALT" | "HOLD" | "NUDGE" | "RESUME" | "ADVISE" | "NONE",  // required only for MODIFY
  "modified_directive": { ... }                                                          // required only for MODIFY
}

Verdict semantics:
  - APPROVE: the peer's decision is well-supported by the signals. Default
             when in doubt — do not VETO without strong evidence.
  - VETO:    the decision is unsafe or unsupported. Use sparingly. Examples:
             HALT issued at confidence < 0.5; ADVISE at confidence > 0.95
             that should have been a stronger action; decisions that
             contradict the most recent precedent without explanation.
  - MODIFY:  the decision direction is correct but the type/severity is
             wrong. Provide ``modified_decision_type`` and a fresh
             ``modified_directive``. Stay close to the peer's intent.

Be conservative. The peer is generally trustworthy; your role is to catch
clear safety / calibration errors, not to second-guess judgement calls.
Quote specific signal values that support your verdict in ``reasoning``.

Output JSON only.""".strip()
