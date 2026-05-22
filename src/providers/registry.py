from __future__ import annotations

import os
from typing import Any, Type

import structlog

logger = structlog.get_logger()

# Maps category → env var name
_ENV_MAP: dict[str, str] = {
    "tts": "TTS_PROVIDER",
    "llm": "LLM_PROVIDER",
    "llm.research": "LLM_RESEARCH_PROVIDER",
    "llm.script": "LLM_SCRIPT_PROVIDER",
    "llm.factcheck": "LLM_FACTCHECK_PROVIDER",
    "llm.qc": "LLM_QC_PROVIDER",
    "llm.vision": "LLM_VISION_PROVIDER",
    "llm.ideation": "LLM_IDEATION_PROVIDER",
    "llm.hook": "LLM_HOOK_PROVIDER",
    "llm.direction": "LLM_DIRECTION_PROVIDER",
    "llm.emotion": "LLM_EMOTION_PROVIDER",
    "search": "SEARCH_PROVIDER",
    "image": "IMAGE_PROVIDER",
    "storage": "STORAGE_PROVIDER",
}

# Test mode remaps expensive providers to free alternatives.
# Storage stays the same (MinIO is self-hosted, just paths change).
_TEST_PROVIDER_MAP: dict[str, str] = {
    "tts": "edge_tts",
    "llm": "mock_llm",
    "llm.research": "mock_llm",
    "llm.script": "mock_llm",
    "llm.factcheck": "mock_llm",
    "llm.qc": "mock_llm",
    "llm.vision": "mock_llm",
    "llm.ideation": "mock_llm",
    "llm.hook": "mock_llm",
    "llm.direction": "mock_llm",
    "llm.emotion": "mock_llm",
    "search": "mock_search",
    "image": "placeholder",
    # storage: NOT remapped — MinIO is free (self-hosted)
}


class ProviderRegistry:
    """Config-driven provider factory.  Read provider name from env vars."""

    _registries: dict[str, dict[str, Type]] = {}
    _instances: dict[str, Any] = {}

    @classmethod
    def register(cls, category: str, name: str, provider_class: Type) -> None:
        if category not in cls._registries:
            cls._registries[category] = {}
        cls._registries[category][name] = provider_class
        logger.debug("provider.registered", category=category, name=name)

    @classmethod
    def get(
        cls,
        category: str,
        *,
        override: str | None = None,
        channel_id: str | None = None,
        content_mode: str | None = None,
        pipeline_mode: str = "production",
    ) -> Any:
        from src.environment import is_test

        # 1) Explicit override always wins
        if override:
            name = override
        # 2) Test mode short-circuits to free providers
        elif is_test() and category in _TEST_PROVIDER_MAP:
            name = _TEST_PROVIDER_MAP[category]
        else:
            # 3) Try the DB-driven priority chain. Three outcomes:
            #      • FallbackProvider — DB chain resolved, use it.
            #      • EMPTY_CHAIN     — DB reachable, no enabled creds.
            #                          Raise NoProviderConfigured so the
            #                          UI surfaces a clear error instead
            #                          of a silent env-var "ghost" provider.
            #      • None            — DB unreachable / flag off, fall
            #                          back to env-var resolution.
            from src.providers.chain import EMPTY_CHAIN, NoProviderConfigured
            chain = cls._try_db_chain(
                category, channel_id=channel_id, content_mode=content_mode,
                pipeline_mode=pipeline_mode,
            )
            if chain is EMPTY_CHAIN:
                raise NoProviderConfigured(
                    category, channel_id=channel_id, content_mode=content_mode,
                )
            if chain is not None:
                return chain
            name = os.getenv(_ENV_MAP.get(category, ""), "")

        if not name:
            from src.providers.chain import NoProviderConfigured
            raise NoProviderConfigured(
                category, channel_id=channel_id, content_mode=content_mode,
            )

        # Cache key includes the resolution axes so that two channels
        # with different overrides can't poison each other's instance.
        cache_key = f"{category}:{name}:{channel_id or ''}:{content_mode or ''}"
        if cache_key in cls._instances:
            return cls._instances[cache_key]

        registry = cls._registries.get(category, {})
        provider_class = registry.get(name)
        if provider_class is None:
            available = list(registry.keys())
            raise ValueError(
                f"Unknown {category} provider '{name}'. Available: {available}. "
                f"Add a credential in /dashboard/providers/{category}."
            )

        instance = provider_class()
        cls._instances[cache_key] = instance
        logger.info("provider.instantiated", category=category, name=name,
                    channel_id=channel_id, content_mode=content_mode)
        return instance

    @classmethod
    def _try_db_chain(
        cls,
        category: str,
        *,
        channel_id: str | None = None,
        content_mode: str | None = None,
        pipeline_mode: str = "production",
    ) -> Any | None:
        """Best-effort DB chain resolution. Returns None on any failure
        so callers fall back to env-based lookup unchanged.
        """
        try:
            import asyncio as _asyncio
            from src.providers.chain import resolve_chain
            registry = cls._registries.get(category, {})
            try:
                loop = _asyncio.get_running_loop()
            except RuntimeError:
                # No running loop — safe to run synchronously
                return _asyncio.run(resolve_chain(
                    category, registry,
                    channel_id=channel_id, content_mode=content_mode,
                    pipeline_mode=pipeline_mode,
                ))
            # We're inside an event loop; schedule and wait on a
            # background thread to keep the call signature sync.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_asyncio.run, resolve_chain(
                    category, registry,
                    channel_id=channel_id, content_mode=content_mode,
                    pipeline_mode=pipeline_mode,
                ))
                return fut.result(timeout=5)
        except Exception as exc:
            logger.debug("provider.db_chain_unavailable",
                         category=category, error=str(exc))
            return None

    @classmethod
    def list_providers(cls, category: str) -> list[str]:
        return list(cls._registries.get(category, {}).keys())

    @classmethod
    def reset(cls) -> None:
        """Clear cached instances (useful for testing)."""
        cls._instances.clear()
