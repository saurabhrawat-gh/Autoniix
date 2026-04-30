"""Environment mode helpers — test vs production.

Usage:
    from src.environment import is_test, is_production, get_mode, require_production

The mode is resolved in order:
    1. In-memory override (set by dashboard toggle in same process)
    2. DB cache (read from system_config every _CACHE_TTL_S seconds)
    3. ENVIRONMENT_MODE env var / Settings.environment_mode
    4. Default: 'test'
"""
from __future__ import annotations

import time
import structlog

from src.config import settings

logger = structlog.get_logger()

# ── In-memory override (set by dashboard BFF toggle) ─────────
_db_mode_override: str | None = None

# ── DB read cache (avoids querying on every call) ────────────
_cached_db_mode: str | None = None
_cache_ts: float = 0.0
_CACHE_TTL_S: float = 5.0  # re-read DB at most every 5 seconds


def set_db_mode_override(mode: str) -> None:
    """Called by dashboard BFF when the user toggles the environment."""
    global _db_mode_override, _cached_db_mode, _cache_ts
    _db_mode_override = mode
    _cached_db_mode = mode
    _cache_ts = time.monotonic()
    logger.info("environment.mode_override_set", mode=mode)


def clear_db_mode_override() -> None:
    global _db_mode_override, _cached_db_mode, _cache_ts
    _db_mode_override = None
    _cached_db_mode = None
    _cache_ts = 0.0


def _read_mode_from_db_sync() -> str | None:
    """Non-async DB read for mode. Returns None if DB is unavailable."""
    try:
        import asyncio
        from src.db import get_pool

        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop and loop.is_running():
            # We're inside an async context — can't block here.
            # Return cached value or None (caller will use env var fallback).
            return None

        async def _fetch():
            pool = await get_pool()
            row = await pool.fetchrow(
                "SELECT config_value FROM system_config WHERE config_key = 'environment_mode'"
            )
            return row["config_value"] if row else None

        return asyncio.run(_fetch())
    except Exception:
        return None


async def get_mode_from_db() -> str:
    """Async helper that reads mode directly from DB. Used by services."""
    try:
        from src.db import get_pool
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = 'environment_mode'"
        )
        mode = row["config_value"] if row else "test"
        # Update cache
        global _cached_db_mode, _cache_ts
        _cached_db_mode = mode
        _cache_ts = time.monotonic()
        return mode
    except Exception:
        return _cached_db_mode or settings.environment_mode.lower().strip()


def get_mode() -> str:
    """Return current environment mode: 'test' or 'production'.

    Checks in-memory override first, then DB cache, then env var.
    """
    if _db_mode_override is not None:
        return _db_mode_override
    if _cached_db_mode is not None and (time.monotonic() - _cache_ts) < _CACHE_TTL_S:
        return _cached_db_mode
    return settings.environment_mode.lower().strip()


def is_test() -> bool:
    return get_mode() != "production"


def is_production() -> bool:
    return get_mode() == "production"


def require_production(action_name: str) -> None:
    """Raise if we are not in production mode. Use before expensive operations."""
    if is_test():
        raise EnvironmentModeError(
            f"Action '{action_name}' requires production mode. "
            f"Current mode: {get_mode()}"
        )


def get_storage_prefix() -> str:
    """Return the MinIO key prefix for the current environment."""
    return "prod" if is_production() else "test"


def get_content_id_prefix() -> str:
    """Return content_id prefix based on mode."""
    return "VID" if is_production() else "TEST_VID"


class EnvironmentModeError(RuntimeError):
    """Raised when an action is attempted in the wrong environment mode."""
    pass
