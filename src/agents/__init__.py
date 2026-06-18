"""Agentic framework — shared base for runtime/product agents.

This package is the **foundation** every runtime agent (Brain, Preventor,
Compliance, …) plugs into. It encodes the canonical observe → recall →
reason → decide → act → remember loop so that:

* every agent has the same auditable lifecycle,
* RAG-style memory is a first-class step (not an afterthought),
* a new agent can be added by subclassing :class:`BaseAgent` and
  implementing 1-2 methods — nothing else.

Why the loop has 6 steps, and not 1 LLM call:

  observe()  — pull structured facts from the world (DB rows, signals)
  recall()   — semantic-search the agent's own past decisions for precedent
  reason()   — combine observations + precedent into an internal state
  decide()   — output a structured decision (or None)
  act()      — persist the decision, emit events, signal workflows
  remember() — write/update embedding for future recall

The class is intentionally **policy-light**: subclasses can leave any
method as the default no-op when they don't need that phase. The
framework is a discipline, not a straitjacket.

Part of AE-P1 / Agentic Foundation.
"""
from __future__ import annotations

from src.agents.base import AgentDecision, AgentObservation, BaseAgent
from src.agents.memory import AgentMemory, MemoryRecallResult
from src.agents.registry import AgentRegistry

__all__ = [
    "AgentDecision",
    "AgentMemory",
    "AgentObservation",
    "AgentRegistry",
    "BaseAgent",
    "MemoryRecallResult",
]
