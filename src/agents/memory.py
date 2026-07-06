"""AgentMemory — RAG-style retrieval over an agent's past decisions.

Wraps :func:`llm.embeddings.semantic_search` with two opinions:

1. Scope is always the agent's *own* decision table — agents don't read
   each other's memories directly. Cross-agent learning, when we want it,
   is a deliberate design step, not an accident of shared tables.

2. The recall query is composed from the observation, not free-form
   user input. This makes the embedding-API cost predictable: one
   recall call per decision opportunity.

The class is small on purpose. The interesting behaviour lives in
:func:`semantic_search` (cosine distance + relevance decay). This
wrapper just gives every agent a typed, well-named entry point.

Part of AE-P1 / Agentic Foundation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from core.flags import get_flag
from llm.embeddings import (
    EmbeddingConfigError,
    EmbeddingError,
    embed_and_store,
    semantic_search,
)

logger = structlog.get_logger()


@dataclass
class MemoryRecallResult:
    """Result of an :meth:`AgentMemory.recall` call.

    ``rows`` is the list of past-decision rows (DB columns plus
    ``cosine_sim`` and ``score``). ``query_text`` is the exact string we
    embedded — captured so the agent can log it for audit.
    """
    rows: list[dict[str, Any]]
    query_text: str
    skipped_reason: str | None = None


class AgentMemory:
    """Per-agent RAG memory over the agent's decision table.

    Example::

        mem = AgentMemory(agent_name="brain", table="brain_decisions")
        result = await mem.recall_for_observation(obs, top_k=3)
        for r in result.rows:
    """

    DEFAULT_TOP_K = 3
    DEFAULT_SCORE_THRESHOLD = 0.55

    def __init__(
        self,
        *,
        agent_name: str,
        table: str,
        embedding_column: str = "embedding",
    ) -> None:
        self.agent_name = agent_name
        self.table = table
        self.embedding_column = embedding_column


    async def recall(
        self,
        query: str,
        *,
        top_k: int | None = None,
        score_threshold: float | None = None,
        scope: str | None = None,
        scope_id: str | None = None,
    ) -> MemoryRecallResult:
        """Semantic-search past decisions matching ``query``.

        Honours the per-agent feature flag ``<agent>.memory_recall.enabled``
        (default FALSE — recall is **opt-in** so existing behaviour is
        preserved). When disabled, returns an empty result tagged with
        ``skipped_reason="disabled_by_flag"``.

        Optional ``scope`` / ``scope_id`` narrow recall to the same scope
        (e.g. only this channel's past decisions).
        """
        enabled = await get_flag(
            f"{self.agent_name}.memory_recall.enabled", default=False
        )
        if not enabled:
            return MemoryRecallResult(
                rows=[], query_text=query, skipped_reason="disabled_by_flag"
            )

        top_k = top_k or self.DEFAULT_TOP_K
        threshold = (
            score_threshold
            if score_threshold is not None
            else self.DEFAULT_SCORE_THRESHOLD
        )

        where, where_params = self._build_scope_filter(scope, scope_id)

        try:
            rows = await semantic_search(
                query,
                table=self.table,
                top_k=top_k,
                column=self.embedding_column,
                select_columns=(
                    "id, decision_type, scope, scope_id, directive, "
                    "reasoning, confidence, created_at"
                ),
                where=where,
                where_params=where_params,
            )
        except (EmbeddingError, EmbeddingConfigError) as exc:
            logger.warning(
                "agent_memory.semantic_search_failed",
                agent=self.agent_name,
                table=self.table,
                error=str(exc),
            )
            return MemoryRecallResult(
                rows=[], query_text=query, skipped_reason="embedding_failed"
            )

        filtered = [r for r in rows if float(r.get("score") or 0) >= threshold]
        return MemoryRecallResult(rows=filtered, query_text=query)

    async def recall_for_observation(
        self,
        observation: Any,
        *,
        top_k: int | None = None,
    ) -> MemoryRecallResult:
        """Convenience: compose the recall query from an
        :class:`~src.agents.base.AgentObservation` and call :meth:`recall`.

        The query is the JSON-ish flattening of ``observation.facts`` —
        good enough for cosine-similarity matching of structurally
        similar past situations.
        """
        from src.agents.base import AgentObservation
        if not isinstance(observation, AgentObservation):
            raise TypeError(
                "recall_for_observation expects AgentObservation; "
                f"got {type(observation).__name__}"
            )

        query = self._observation_to_query(observation)
        return await self.recall(
            query,
            top_k=top_k,
            scope=observation.scope,
            scope_id=observation.scope_id,
        )

    async def remember(
        self,
        decision: Any,
        acted_row: dict[str, Any],
    ) -> None:
        """Write the decision's embedding into its row for future recall.

        The embedding text is ``"<type>: <reasoning>\\n\\nContext: <ctx>"``.
        Skipped silently (logged) if embeddings are not configured.
        """
        from src.agents.base import AgentDecision
        if not isinstance(decision, AgentDecision):
            raise TypeError(
                "remember expects AgentDecision; got "
                f"{type(decision).__name__}"
            )

        row_id = acted_row.get("id")
        if row_id is None:
            logger.warning(
                "agent_memory.remember_missing_row_id",
                agent=self.agent_name,
                decision_type=decision.decision_type,
            )
            return

        text = (
            f"{decision.decision_type}: {decision.reasoning}\n\n"
            f"Context: {decision.context_summary}"
        )
        try:
            await embed_and_store(
                text,
                table=self.table,
                row_id=row_id,
                column=self.embedding_column,
            )
        except (EmbeddingError, EmbeddingConfigError) as exc:
            logger.warning(
                "agent_memory.remember_skipped",
                agent=self.agent_name,
                row_id=row_id,
                error=str(exc),
            )


    @staticmethod
    def _build_scope_filter(
        scope: str | None, scope_id: str | None
    ) -> tuple[str | None, tuple | None]:
        if scope_id is None:
            return None, None
        if scope is None:
            return "scope_id = $2", (scope_id,)
        return "scope = $2 AND scope_id = $3", (scope, scope_id)

    @staticmethod
    def _observation_to_query(observation: Any) -> str:
        """Flatten an observation into a stable query string.

        Order matters for embedding similarity, so we sort keys for
        determinism. We deliberately do *not* json.dumps — the embedding
        model handles natural-language-ish strings better than escaped
        JSON braces.
        """
        from src.agents.base import AgentObservation
        assert isinstance(observation, AgentObservation)
        parts = [f"scope={observation.scope}", f"scope_id={observation.scope_id}"]
        for key in sorted(observation.facts.keys()):
            value = observation.facts[key]
            parts.append(f"{key}={value}")
        return " ".join(parts)
