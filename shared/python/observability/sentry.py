"""Sentry initialization helper.

Importing this module is a no-op unless ``SENTRY_DSN`` is set; that means
local dev / CI without Sentry keep working unchanged. Every long-running
service (FastAPI apps, Temporal workers) calls :func:`init_sentry` at boot.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

logger = structlog.get_logger()

_initialized: bool = False


def init_sentry(service_name: str, *, traces_sample_rate: float = 0.05) -> None:
    """Initialize Sentry for a process. Idempotent across calls.

    No-op when ``SENTRY_DSN`` is unset. Fails open (logs and returns) if the
    SDK is unavailable, so missing the optional dependency never breaks
    application boot.
    """
    global _initialized
    if _initialized:
        return
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.debug("sentry.disabled", reason="no_dsn", service=service_name)
        _initialized = True
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except Exception as exc:
        logger.warning("sentry.sdk_unavailable", error=str(exc), service=service_name)
        _initialized = True
        return

    integrations: list[Any] = [
        AsyncioIntegration(),
        LoggingIntegration(level=None, event_level=None),  # structlog handles routing
    ]
    # FastAPI integration is added if available; workers don't need it.
    try:
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        integrations.extend([StarletteIntegration(), FastApiIntegration()])
    except Exception:
        pass

    sentry_sdk.init(
        dsn=dsn,
        environment="production",
        release=os.getenv("RELEASE_SHA") or os.getenv("GIT_SHA"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", traces_sample_rate)),
        send_default_pii=False,
        attach_stacktrace=True,
        integrations=integrations,
    )
    sentry_sdk.set_tag("service", service_name)
    _initialized = True
    logger.info("sentry.initialized", service=service_name)


def capture_exception(exc: BaseException, **tags: str) -> None:
    """Best-effort exception capture; safe to call even when Sentry is off."""
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for k, v in tags.items():
                scope.set_tag(k, v)
            sentry_sdk.capture_exception(exc)
    except Exception:
        pass
