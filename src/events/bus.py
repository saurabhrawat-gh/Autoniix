"""Thin async pub/sub wrapper around Redis with envelope validation.

The "thin" part matters — every later agentic service publishes through the
same ``publish()`` so that:

* Envelope shape is uniform across the fleet (the locked schema in
  ``schema.json``);
* An invalid payload at publish time fails LOUDLY here, not on a
  subscriber three services downstream;
* Subscribers can trust the envelope without re-validating in each
  handler;
* A single Prometheus counter (``events_invalid_total``) shows real-time
  schema violations across the system.

This module is part of AE-509 / P0 — Agentic Foundation.

Usage
-----

Publishing::

    from src.events import Topic, publish
    event_id = await publish(
        Topic.BRAIN_DIRECTIVE,
        scope="channel",
        scope_id="BS001",
        payload={"action": "HOLD", "reason": "high copyright risk"},
        confidence=0.92,
        source_service="the-brain",
    )

Subscribing (e.g. a long-running worker)::

    from src.events import Topic, subscribe

    async def on_directive(envelope: dict) -> None:
        ...

    await subscribe([Topic.BRAIN_DIRECTIVE], on_directive)
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Awaitable, Callable, Iterable

import structlog
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as JsonSchemaError

from src.events.topics import Topic
from src.redis_client import get_redis

logger = structlog.get_logger()

_SCHEMA_PATH = Path(__file__).with_name("schema.json")
_schema = json.loads(_SCHEMA_PATH.read_text())
_validator = Draft7Validator(_schema)


class EnvelopeError(ValueError):
    """Raised when an envelope fails schema validation at publish time."""


# Prometheus metrics — best-effort, no-op when client missing.
try:  # pragma: no cover - import guard
    from prometheus_client import Counter

    EVENTS_INVALID_TOTAL = Counter(
        "events_invalid_total",
        "Envelopes that failed schema validation by topic and direction.",
        labelnames=("topic", "direction"),  # direction: publish | subscribe
    )
    EVENTS_PUBLISHED_TOTAL = Counter(
        "events_published_total",
        "Successfully published envelopes by topic.",
        labelnames=("topic",),
    )
except Exception:  # pragma: no cover
    EVENTS_INVALID_TOTAL = None  # type: ignore[assignment]
    EVENTS_PUBLISHED_TOTAL = None  # type: ignore[assignment]


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _topic_value(topic: Topic | str) -> str:
    return topic.value if isinstance(topic, Topic) else str(topic)


def validate_envelope(envelope: dict) -> None:
    """Raise :class:`EnvelopeError` if ``envelope`` is not schema-conformant."""
    try:
        _validator.validate(envelope)
    except JsonSchemaError as exc:
        raise EnvelopeError(f"invalid envelope: {exc.message}") from exc
    if not Topic.is_known(envelope["topic"]):
        raise EnvelopeError(f"unknown topic: {envelope['topic']!r}")
    if envelope["scope"] == "global" and envelope.get("scope_id") is not None:
        # Soft policy: 'global' must not carry an id. Catching this early
        # prevents subscribers from misrouting fan-out events.
        raise EnvelopeError("scope='global' must have scope_id=null")


async def publish(
    topic: Topic | str,
    *,
    scope: str,
    scope_id: str | None,
    payload: dict,
    source_service: str,
    confidence: float | None = None,
) -> str:
    """Validate + publish an envelope to Redis. Returns the ``event_id``.

    Raises :class:`EnvelopeError` if the envelope is invalid (you don't
    want to discover that on the subscriber side). All other Redis errors
    bubble up unchanged — the caller is expected to wrap them in
    retry/backoff at the service layer.
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
    await redis.publish(topic_value, json.dumps(envelope, separators=(",", ":")))
    if EVENTS_PUBLISHED_TOTAL is not None:
        EVENTS_PUBLISHED_TOTAL.labels(topic=topic_value).inc()
    return envelope["event_id"]


async def subscribe(
    topics: Iterable[Topic | str],
    handler: Callable[[dict], Awaitable[None]],
    *,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Subscribe to one or more topics and dispatch valid envelopes to ``handler``.

    * Invalid envelopes are dropped + counted (``events_invalid_total``) so
      a poisoned producer cannot crash a worker loop.
    * Handler exceptions are logged + counted but do not break the loop —
      one bad message must not stop the stream.
    * ``stop_event`` is the cooperative shutdown signal; the loop exits at
      the next message boundary when set.
    """
    redis = await get_redis()
    pubsub = redis.pubsub()
    topic_values = [_topic_value(t) for t in topics]
    if not topic_values:
        raise ValueError("subscribe requires at least one topic")
    await pubsub.subscribe(*topic_values)
    logger.info("events.subscribed", topics=topic_values)

    try:
        async for message in pubsub.listen():
            if stop_event is not None and stop_event.is_set():
                break
            if message.get("type") != "message":
                continue
            topic_value = message.get("channel", "")
            try:
                envelope = json.loads(message["data"])
                validate_envelope(envelope)
            except (json.JSONDecodeError, EnvelopeError) as exc:
                logger.warning(
                    "events.invalid_message",
                    topic=topic_value,
                    error=str(exc),
                )
                if EVENTS_INVALID_TOTAL is not None:
                    EVENTS_INVALID_TOTAL.labels(
                        topic=topic_value, direction="subscribe"
                    ).inc()
                continue
            try:
                await handler(envelope)
            except Exception as exc:  # noqa: BLE001 — handler isolation
                logger.warning(
                    "events.handler_failed",
                    topic=topic_value,
                    event_id=envelope.get("event_id"),
                    error=str(exc),
                )
    finally:
        try:
            await pubsub.unsubscribe(*topic_values)
            await pubsub.close()
        except Exception:  # pragma: no cover — defensive cleanup
            pass
