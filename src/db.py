from __future__ import annotations

import asyncpg
import structlog

from src.config import settings

logger = structlog.get_logger()

_pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Apply per-connection guardrails when a pool slot is created.

    ``statement_timeout`` is the single most important runaway-query
    guard: any query that exceeds it is killed by Postgres rather than
    hanging an activity slot forever. Set at the connection level so it
    inherits to every transaction and never relies on a SET LOCAL that a
    caller might forget.
    """
    timeout_ms = max(1, int(settings.db_statement_timeout_ms))
    await conn.execute(f"SET statement_timeout = {timeout_ms}")


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        logger.info("db.connecting",
                    host=settings.db_host, db=settings.db_name,
                    pool_min=settings.db_pool_min_size,
                    pool_max=settings.db_pool_max_size,
                    statement_timeout_ms=settings.db_statement_timeout_ms)
        _pool = await asyncpg.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            init=_init_connection,
        )
        logger.info("db.connected")
    return _pool


def get_pool_stats() -> dict:
    """Snapshot pool-level counters for the fleet-health endpoint.

    Returns zeros (not None) when the pool hasn't been created yet so
    consumers can sum across services without null-handling.
    """
    if _pool is None:
        return {"size": 0, "idle": 0, "min_size": 0, "max_size": 0}
    try:
        return {
            "size":     _pool.get_size(),
            "idle":     _pool.get_idle_size(),
            "min_size": _pool.get_min_size(),
            "max_size": _pool.get_max_size(),
        }
    except Exception:
        return {"size": -1, "idle": -1, "min_size": 0, "max_size": 0}


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("db.closed")
