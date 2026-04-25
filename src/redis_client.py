from __future__ import annotations

import redis.asyncio as aioredis
import structlog

from src.config import settings

logger = structlog.get_logger()

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        logger.info("redis.connecting", url=settings.redis_url)
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis.ping()
        logger.info("redis.connected")
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
        logger.info("redis.closed")
