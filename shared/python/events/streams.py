"""Redis Streams adapter — delivery-guaranteed event bus for Autoniix.

Motivation:  Redis pub/sub (``events/bus.py``) drops any message whose
subscriber is offline at publish time. That's fine for realtime UI
fan-out (subscribers reconnect and just resume from "now") but wrong for
notifications, audit events, and pipeline progress — anything the system
must eventually deliver.

This module adds Redis **Streams** with **consumer groups** so:

  * Every published event is durable (survives subscriber restarts and
    Redis restarts, subject to Redis AOF/RDB config).
  * Multiple worker replicas share load via a consumer group (each event
    goes to exactly one consumer within the group).
  * Consumers explicitly ``XACK`` events; anything unacked eventually gets
    re-delivered via ``XAUTOCLAIM`` to a healthy consumer.

Migration strategy (per plan): **dual-write**. During transition,
``publish_dual_write()`` fires both the pub/sub payload (legacy consumers
keep working) AND the stream entry (new consumers use Streams). Once all
consumers migrate, drop the pub/sub side.

Streams naming: one stream per topic, e.g. ``stream:brain.directive``.
The consumer-group name is chosen by the consumer (typically the
service name). Two independent services on the same topic use two
different groups so each gets its own copy — same shape as fan-out
subscribers on pub/sub.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import uuid
from typing import Awaitable, Callable, Iterable

import structlog

from core.redis_client import get_redis
from events.bus import (
    EVENTS_INVALID_TOTAL,
    EVENTS_PUBLISHED_TOTAL,
    EnvelopeError,
    validate_envelope,
)
from events.topics import Topic

logger = structlog.get_logger()

STREAM_PREFIX = "stream:"
DEFAULT_STREAM_MAXLEN = 10_000  # approximate trim to bound storage
DEFAULT_BLOCK_MS = 5_000
DEFAULT_BATCH = 16
DEFAULT_CLAIM_IDLE_MS = 60_000  # reclaim pending entries idle > 60s


try:  # pragma: no cover
    from prometheus_client import Counter

    EVENTS_STREAM_PUBLISHED_TOTAL = Counter(
        "events_stream_published_total",
        "Events written to Redis Streams by topic.",
        labelnames=("topic",),
    )
    EVENTS_STREAM_CONSUMED_TOTAL = Counter(
        "events_stream_consumed_total",
        "Events successfully processed via Streams by topic and consumer group.",
        labelnames=("topic", "group"),
    )
    EVENTS_STREAM_FAILED_TOTAL = Counter(
        "events_stream_failed_total",
        "Events whose handler raised (still ACKed after N retries).",
        labelnames=("topic", "group"),
    )
    EVENTS_STREAM_RECLAIMED_TOTAL = Counter(
        "events_stream_reclaimed_total",
        "Pending stream entries reclaimed from another consumer.",
        labelnames=("topic", "group"),
    )
except Exception:  # pragma: no cover

    class _Noop:
        def labels(self, *a, **kw):
            return self

        def inc(self, *a, **kw):
            return None

    EVENTS_STREAM_PUBLISHED_TOTAL = _Noop()  # type: ignore[assignment]
    EVENTS_STREAM_CONSUMED_TOTAL = _Noop()  # type: ignore[assignment]
    EVENTS_STREAM_FAILED_TOTAL = _Noop()  # type: ignore[assignment]
    EVENTS_STREAM_RECLAIMED_TOTAL = _Noop()  # type: ignore[assignment]


def _stream_key(topic: str) -> str:
    return f"{STREAM_PREFIX}{topic}"


def _topic_value(topic: Topic | str) -> str:
    return topic.value if isinstance(topic, Topic) else str(topic)


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


async def publish_stream(
    topic: Topic | str,
    *,
    scope: str,
    scope_id: str | None,
    payload: dict,
    source_service: str,
    confidence: float | None = None,
    maxlen: int = DEFAULT_STREAM_MAXLEN,
) -> tuple[str, str]:
    """Publish a validated envelope to a Redis Stream.

    Returns ``(event_id, stream_id)`` — ``event_id`` is our UUID (same as
    pub/sub); ``stream_id`` is Redis's monotonic ID (used for XACK).
    """
    topic_value = _topic_value(topic)
    envelope = {
        "topic": topic_value,
        "event_id": str(uuid.uuid4()),
        "scope": scope,
        "scope_id": scope_id,
        "payload": payload,
        "confidence": confidence,
        "timestamp": _utc_now_iso(),
        "source_service": source_service,
    }
    try:
        validate_envelope(envelope)
    except EnvelopeError:
        if EVENTS_INVALID_TOTAL is not None:
            EVENTS_INVALID_TOTAL.labels(topic=topic_value, direction="publish").inc()
        raise

    redis = await get_redis()
    stream_id = await redis.xadd(
        _stream_key(topic_value),
        {"envelope": json.dumps(envelope, separators=(",", ":"))},
        maxlen=maxlen,
        approximate=True,
    )
    EVENTS_STREAM_PUBLISHED_TOTAL.labels(topic=topic_value).inc()
    return envelope["event_id"], stream_id


async def publish_dual_write(
    topic: Topic | str,
    *,
    scope: str,
    scope_id: str | None,
    payload: dict,
    source_service: str,
    confidence: float | None = None,
    maxlen: int = DEFAULT_STREAM_MAXLEN,
) -> str:
    """Publish to BOTH Redis pub/sub (legacy) AND Redis Streams (new).

    Legacy consumers on ``events.subscribe`` keep receiving events;
    new consumers on ``consume_stream`` get durable delivery. Returns
    the ``event_id`` (same across both writes so consumers can dedup).
    """
    topic_value = _topic_value(topic)
    envelope = {
        "topic": topic_value,
        "event_id": str(uuid.uuid4()),
        "scope": scope,
        "scope_id": scope_id,
        "payload": payload,
        "confidence": confidence,
        "timestamp": _utc_now_iso(),
        "source_service": source_service,
    }
    try:
        validate_envelope(envelope)
    except EnvelopeError:
        if EVENTS_INVALID_TOTAL is not None:
            EVENTS_INVALID_TOTAL.labels(topic=topic_value, direction="publish").inc()
        raise

    payload_json = json.dumps(envelope, separators=(",", ":"))
    redis = await get_redis()

    # Fire pub/sub first (best-effort broadcast to any live subscriber).
    try:
        await redis.publish(topic_value, payload_json)
        if EVENTS_PUBLISHED_TOTAL is not None:
            EVENTS_PUBLISHED_TOTAL.labels(topic=topic_value).inc()
    except Exception as exc:  # noqa: BLE001 — pub/sub failure must not lose the event; Streams is the durable path
        logger.warning("events.pubsub_publish_failed", topic=topic_value, error=str(exc))

    # Streams write is the source of truth. If this fails, raise.
    await redis.xadd(
        _stream_key(topic_value),
        {"envelope": payload_json},
        maxlen=maxlen,
        approximate=True,
    )
    EVENTS_STREAM_PUBLISHED_TOTAL.labels(topic=topic_value).inc()
    return envelope["event_id"]


async def _ensure_group(redis, stream_key: str, group: str) -> None:
    """Create the consumer group if it doesn't exist yet.

    We ignore ``BUSYGROUP`` (group already exists) which is the expected
    outcome on every restart after the first.
    """
    try:
        await redis.xgroup_create(
            name=stream_key,
            groupname=group,
            id="0",
            mkstream=True,
        )
        logger.info("events.stream_group_created", stream=stream_key, group=group)
    except Exception as exc:  # noqa: BLE001 — expected on second+ startup
        msg = str(exc).upper()
        if "BUSYGROUP" not in msg:
            raise
        logger.debug("events.stream_group_exists", stream=stream_key, group=group)


async def consume_stream(
    topics: Iterable[Topic | str],
    handler: Callable[[dict], Awaitable[None]],
    *,
    group: str,
    consumer: str | None = None,
    stop_event: asyncio.Event | None = None,
    batch_size: int = DEFAULT_BATCH,
    block_ms: int = DEFAULT_BLOCK_MS,
    claim_idle_ms: int = DEFAULT_CLAIM_IDLE_MS,
    max_handler_retries: int = 3,
) -> None:
    """Consume events from one or more streams with delivery guarantees.

    * Uses Redis consumer groups — within ``group``, each event is
      delivered to exactly one ``consumer``.
    * Auto-creates the group + stream on first read.
    * Periodically calls ``XAUTOCLAIM`` to steal pending entries from
      dead consumers (any entry idle > ``claim_idle_ms``).
    * Handler exceptions are retried up to ``max_handler_retries`` times
      before the entry is ACKed (with a metric bump). This bounds
      poison-pill damage.
    * ``stop_event`` — cooperative shutdown.
    """
    topic_values = [_topic_value(t) for t in topics]
    if not topic_values:
        raise ValueError("consume_stream requires at least one topic")
    consumer = consumer or f"consumer-{uuid.uuid4().hex[:8]}"

    redis = await get_redis()
    stream_keys = [_stream_key(t) for t in topic_values]
    for sk in stream_keys:
        await _ensure_group(redis, sk, group)

    logger.info(
        "events.stream_consumer_started",
        topics=topic_values,
        group=group,
        consumer=consumer,
    )

    last_autoclaim = 0.0
    autoclaim_interval_s = max(5.0, claim_idle_ms / 1000 / 4)

    while True:
        if stop_event is not None and stop_event.is_set():
            logger.info("events.stream_consumer_stopping", group=group, consumer=consumer)
            return

        # Periodically reclaim entries stuck at other consumers.
        now = asyncio.get_event_loop().time()
        if now - last_autoclaim > autoclaim_interval_s:
            for sk, topic in zip(stream_keys, topic_values):
                try:
                    _next_id, reclaimed, _deleted = await redis.xautoclaim(
                        name=sk,
                        groupname=group,
                        consumername=consumer,
                        min_idle_time=claim_idle_ms,
                        start_id="0-0",
                        count=batch_size,
                    )
                    if reclaimed:
                        EVENTS_STREAM_RECLAIMED_TOTAL.labels(topic=topic, group=group).inc(len(reclaimed))
                        logger.info(
                            "events.stream_reclaimed",
                            topic=topic,
                            group=group,
                            count=len(reclaimed),
                        )
                        for entry_id, fields in reclaimed:
                            await _process_entry(
                                redis,
                                sk,
                                group,
                                entry_id,
                                fields,
                                handler,
                                topic,
                                max_handler_retries,
                            )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("events.autoclaim_failed", stream=sk, error=str(exc))
            last_autoclaim = now

        # Read new entries (blocking).
        try:
            streams = {sk: ">" for sk in stream_keys}
            resp = await redis.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams=streams,
                count=batch_size,
                block=block_ms,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("events.xreadgroup_failed", error=str(exc))
            await asyncio.sleep(1.0)
            continue

        if not resp:
            continue

        for stream_key, entries in resp:
            topic = stream_key.split(STREAM_PREFIX, 1)[-1] if STREAM_PREFIX in stream_key else stream_key
            for entry_id, fields in entries:
                await _process_entry(
                    redis,
                    stream_key,
                    group,
                    entry_id,
                    fields,
                    handler,
                    topic,
                    max_handler_retries,
                )


async def _process_entry(
    redis,
    stream_key: str,
    group: str,
    entry_id: str,
    fields: dict,
    handler: Callable[[dict], Awaitable[None]],
    topic: str,
    max_handler_retries: int,
) -> None:
    """Decode + validate + hand off + ACK a single stream entry.

    Invalid envelopes are ACKed (so we don't loop) and counted.
    Handler exceptions are retried in-process; after ``max_handler_retries``
    the entry is ACKed anyway and counted as failed so a single poison-pill
    can't wedge the consumer.
    """
    raw = fields.get("envelope") if isinstance(fields, dict) else None
    if raw is None:
        # Bare-fields form (some pipelines XADD flat fields instead of {"envelope": ...})
        try:
            envelope = dict(fields)
        except Exception:
            envelope = None
    else:
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            envelope = None

    if envelope is None:
        logger.warning("events.stream_undecodable", stream=stream_key, entry=entry_id)
        if EVENTS_INVALID_TOTAL is not None:
            EVENTS_INVALID_TOTAL.labels(topic=topic, direction="subscribe").inc()
        await redis.xack(stream_key, group, entry_id)
        return

    try:
        validate_envelope(envelope)
    except EnvelopeError as exc:
        logger.warning(
            "events.stream_invalid_envelope",
            stream=stream_key,
            entry=entry_id,
            error=str(exc),
        )
        if EVENTS_INVALID_TOTAL is not None:
            EVENTS_INVALID_TOTAL.labels(topic=topic, direction="subscribe").inc()
        await redis.xack(stream_key, group, entry_id)
        return

    last_exc: Exception | None = None
    for attempt in range(1, max_handler_retries + 1):
        try:
            await handler(envelope)
            await redis.xack(stream_key, group, entry_id)
            EVENTS_STREAM_CONSUMED_TOTAL.labels(topic=topic, group=group).inc()
            return
        except Exception as exc:  # noqa: BLE001 — retry a few times before giving up
            last_exc = exc
            logger.warning(
                "events.stream_handler_error",
                stream=stream_key,
                entry=entry_id,
                event_id=envelope.get("event_id"),
                attempt=attempt,
                error=str(exc),
            )
            if attempt < max_handler_retries:
                await asyncio.sleep(min(2**attempt, 8))

    # Exhausted retries — ACK to unblock the consumer, count as failed.
    logger.error(
        "events.stream_handler_gave_up",
        stream=stream_key,
        entry=entry_id,
        event_id=envelope.get("event_id"),
        error=str(last_exc) if last_exc else "unknown",
    )
    EVENTS_STREAM_FAILED_TOTAL.labels(topic=topic, group=group).inc()
    await redis.xack(stream_key, group, entry_id)
