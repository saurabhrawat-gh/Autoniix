"""AgentRegistry — discovery + lookup for runtime agents.

Tiny, in-process. Modeled on :class:`providers.registry.ProviderRegistry`
so the mental model is familiar.

Why a registry rather than direct imports:

* Decouples *event routing* from *agent implementation*. The consumer
  layer can ask "which agents care about this event?" without importing
  every agent module.
* Makes it trivial to add a second agent (Preventor, Compliance) — just
  register it; nothing else changes.
* Tests can register a stub agent under the same name.

Part of AE-P1 / Agentic Foundation.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base import BaseAgent


class AgentRegistry:
    """Process-global registry of runtime agents, keyed by ``agent.name``."""

    _agents: dict[str, "BaseAgent"] = {}

    @classmethod
    def register(cls, agent: "BaseAgent") -> None:
        """Register *agent*. Idempotent — re-registering the same name
        replaces the previous instance (useful in tests)."""
        if not agent.name:
            raise ValueError("agent.name must be set before registering")
        cls._agents[agent.name] = agent

    @classmethod
    def get(cls, name: str) -> "BaseAgent | None":
        return cls._agents.get(name)

    @classmethod
    def all(cls) -> list["BaseAgent"]:
        return list(cls._agents.values())

    @classmethod
    def clear(cls) -> None:
        """For tests — empties the registry."""
        cls._agents.clear()
