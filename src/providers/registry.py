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
    def get(cls, category: str, *, override: str | None = None) -> Any:
        name = override or os.getenv(_ENV_MAP.get(category, ""), "")
        if not name:
            raise ValueError(f"No provider configured for category '{category}'")

        cache_key = f"{category}:{name}"
        if cache_key in cls._instances:
            return cls._instances[cache_key]

        registry = cls._registries.get(category, {})
        provider_class = registry.get(name)
        if provider_class is None:
            available = list(registry.keys())
            raise ValueError(
                f"Unknown {category} provider '{name}'. Available: {available}"
            )

        instance = provider_class()
        cls._instances[cache_key] = instance
        logger.info("provider.instantiated", category=category, name=name)
        return instance

    @classmethod
    def list_providers(cls, category: str) -> list[str]:
        return list(cls._registries.get(category, {}).keys())

    @classmethod
    def reset(cls) -> None:
        """Clear cached instances (useful for testing)."""
        cls._instances.clear()
