from __future__ import annotations

import os
import threading
from typing import Any, Type

import structlog

logger = structlog.get_logger()

# ── Concurrency guards ────────────────────────────────────────────────────
# ``_registries`` (populated at import time by provider modules) is treated
# as effectively immutable after boot, so a plain dict is fine. ``_instances``
# on the other hand is mutated at call time by any coroutine/thread that
# resolves a provider — we protect it with a threading lock so a stampede of
# concurrent Temporal activity workers never causes two provider instances to
# be constructed for the same cache key (some providers spin up HTTP clients
# with connection pools that would leak).
_INSTANCE_LOCK = threading.Lock()

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
        if override:
            name = override
        else:
            from providers.chain import EMPTY_CHAIN, NoProviderConfigured

            chain = cls._try_db_chain(
                category,
                channel_id=channel_id,
                content_mode=content_mode,
                pipeline_mode=pipeline_mode,
            )
            if chain is EMPTY_CHAIN:
                raise NoProviderConfigured(
                    category,
                    channel_id=channel_id,
                    content_mode=content_mode,
                )
            if chain is not None:
                return chain
            name = os.getenv(_ENV_MAP.get(category, ""), "")

        if not name:
            from providers.chain import NoProviderConfigured

            raise NoProviderConfigured(
                category,
                channel_id=channel_id,
                content_mode=content_mode,
            )

        cache_key = f"{category}:{name}:{channel_id or ''}:{content_mode or ''}"

        # Fast path — no lock needed for a hit against a stable cache.
        cached = cls._instances.get(cache_key)
        if cached is not None:
            return cached

        registry = cls._registries.get(category, {})
        provider_class = registry.get(name)
        if provider_class is None:
            available = list(registry.keys())
            raise ValueError(
                f"Unknown {category} provider '{name}'. Available: {available}. "
                f"Add a credential in /dashboard/providers/{category}."
            )

        # Slow path — construct exactly once even under concurrent stampede.
        with _INSTANCE_LOCK:
            cached = cls._instances.get(cache_key)
            if cached is not None:
                return cached
            instance = provider_class()
            cls._instances[cache_key] = instance
        logger.info(
            "provider.instantiated", category=category, name=name, channel_id=channel_id, content_mode=content_mode
        )
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

            from providers.chain import resolve_chain

            registry = cls._registries.get(category, {})
            try:
                loop = _asyncio.get_running_loop()
            except RuntimeError:
                return _asyncio.run(
                    resolve_chain(
                        category,
                        registry,
                        channel_id=channel_id,
                        content_mode=content_mode,
                        pipeline_mode=pipeline_mode,
                    )
                )
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(
                    _asyncio.run,
                    resolve_chain(
                        category,
                        registry,
                        channel_id=channel_id,
                        content_mode=content_mode,
                        pipeline_mode=pipeline_mode,
                    ),
                )
                return fut.result(timeout=5)
        except Exception as exc:
            logger.debug("provider.db_chain_unavailable", category=category, error=str(exc))
            return None

    @classmethod
    def list_providers(cls, category: str) -> list[str]:
        return list(cls._registries.get(category, {}).keys())

    @classmethod
    def reset(cls) -> None:
        """Clear cached instances (useful for testing)."""
        with _INSTANCE_LOCK:
            cls._instances.clear()
