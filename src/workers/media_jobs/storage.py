"""Thin storage adapter for media-jobs handlers.

Wraps the existing ``ProviderRegistry`` storage so handlers can be unit-tested
by patching this single function instead of monkey-patching the registry.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger()


async def download_bytes(key: str) -> bytes | None:
    """Best-effort fetch of an object from the configured storage provider.

    Returns the bytes on success or ``None`` if anything fails. Handlers
    treat ``None`` as a retryable error and the runner will reschedule.
    """
    try:
        from src.providers.registry import ProviderRegistry

        storage = ProviderRegistry.get("storage")
    except Exception as exc:
        logger.warning("media_jobs.storage_unavailable", error=str(exc))
        return None

    try:
        return await storage.download(key)  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("media_jobs.download_failed", key=key, error=str(exc))
        return None
