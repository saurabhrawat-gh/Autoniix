from __future__ import annotations

import asyncio
import functools
from typing import Any, Awaitable, Callable, TypeVar

import redis.asyncio as aioredis
import structlog
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
)

from core.config import settings

logger = structlog.get_logger()

_redis: aioredis.Redis | None = None
_redis_pubsub: aioredis.Redis | None = None

_T = TypeVar("_T")


def _pool_kwargs() -> dict[str, Any]:
    """Return connection-pool kwargs, tolerating older settings modules
    that don't yet expose ``redis_max_connections``.
    """
    kwargs: dict[str, Any] = {}
    max_conn = getattr(settings, "redis_max_connections", None)
    if max_conn:
        kwargs["max_connections"] = int(max_conn)
    return kwargs


async def get_redis() -> aioredis.Redis:
    """Return the shared Redis client. Auto-reconnects with exp-backoff.

    Notes:
    - ``retry`` (redis-py 5+): the client transparently retries the
      configured errors (transient ConnectionError / TimeoutError).
    - ``max_connections`` bounds the pool so we don't leak sockets under
      a busy worker fleet.
    - ``health_check_interval`` catches idle-connection black-holes.
    """
    global _redis
    if _redis is None:
        logger.info(
            "redis.connecting",
            url=settings.redis_url,
            max_connections=_pool_kwargs().get("max_connections"),
        )
        retry = Retry(ExponentialBackoff(cap=10, base=0.1), retries=3)
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_keepalive=True,
            health_check_interval=30,
            retry=retry,
            retry_on_error=[RedisConnectionError, RedisTimeoutError],
            **_pool_kwargs(),
        )
        await _redis.ping()
        logger.info("redis.connected")
    return _redis


def with_redis_retry(
    max_attempts: int = 3,
    base_delay_s: float = 0.1,
) -> Callable[[Callable[..., Awaitable[_T]]], Callable[..., Awaitable[_T]]]:
    """Decorator: retry a coroutine on transient Redis errors.

    Complementary to the client-level ``retry`` — use this on higher-
    level operations (multi-step transactions, XREADGROUP loops) where
    a single retry inside the client isn't enough.
    """

    def _decorator(func: Callable[..., Awaitable[_T]]) -> Callable[..., Awaitable[_T]]:
        @functools.wraps(func)
        async def _wrapped(*args: Any, **kwargs: Any) -> _T:
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except (RedisConnectionError, RedisTimeoutError) as exc:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    delay = base_delay_s * (2 ** (attempt - 1))
                    logger.warning(
                        "redis.retry",
                        func=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay_s=delay,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)

        return _wrapped

    return _decorator


async def get_pubsub_redis() -> aioredis.Redis:
    """Return a Redis client configured for pub/sub (socket_timeout=None).

    Regular clients in redis-py 8 default to socket_timeout=5s, which kills
    idle pubsub connections every 5 seconds.  Pub/sub subscribers must block
    indefinitely waiting for the next message, so they need no socket timeout.
    """
    global _redis_pubsub
    if _redis_pubsub is None:
        _redis_pubsub = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_keepalive=True,
            socket_timeout=None,
        )
    return _redis_pubsub


async def close_redis() -> None:
    global _redis, _redis_pubsub
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("redis.closed")
    if _redis_pubsub is not None:
        await _redis_pubsub.aclose()
        _redis_pubsub = None
