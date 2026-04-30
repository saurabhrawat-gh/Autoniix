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
    def get(cls, category: str, *, override: str | None = None) -> Any:
        from src.environment import is_test

        if override:
            name = override
        elif is_test() and category in _TEST_PROVIDER_MAP:
            name = _TEST_PROVIDER_MAP[category]
        else:
            name = os.getenv(_ENV_MAP.get(category, ""), "")

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
