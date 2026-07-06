"""Unit tests for events — AE-509 / P0."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from events import EnvelopeError, Topic, publish, validate_envelope
from events.bus import subscribe
from events.topics import ALL_TOPICS




def test_all_12_topics_are_registered():
    """The spec on AE-509 locks 12 topics; ensure none are dropped."""
    assert len(ALL_TOPICS) == 12


def test_known_topic_strings_are_recognized():
    for topic in ALL_TOPICS:
        assert Topic.is_known(topic.value)


def test_unknown_topic_is_rejected():
    assert not Topic.is_known("brain.unknown.topic")




def _good_envelope(**overrides):
    base = {
        "topic": Topic.BRAIN_DIRECTIVE.value,
        "event_id": str(uuid.uuid4()),
        "scope": "channel",
        "scope_id": "BS001",
        "payload": {"action": "HOLD"},
        "confidence": 0.9,
        "timestamp": "2026-06-13T14:32:00+00:00",
        "source_service": "the-brain",
    }
    base.update(overrides)
    return base


def test_valid_envelope_passes_validation():
    validate_envelope(_good_envelope())


def test_missing_required_field_is_rejected():
    env = _good_envelope()
    del env["event_id"]
    with pytest.raises(EnvelopeError):
        validate_envelope(env)


def test_unknown_scope_is_rejected():
    with pytest.raises(EnvelopeError):
        validate_envelope(_good_envelope(scope="universe"))


def test_unknown_topic_in_envelope_is_rejected():
    with pytest.raises(EnvelopeError):
        validate_envelope(_good_envelope(topic="brain.bogus.topic"))


def test_global_scope_must_have_null_id():
    """Soft policy from AE-509 — global events are fan-out, must not carry id."""
    with pytest.raises(EnvelopeError):
        validate_envelope(_good_envelope(scope="global", scope_id="BS001"))


def test_global_scope_with_null_id_is_accepted():
    validate_envelope(_good_envelope(scope="global", scope_id=None))


def test_confidence_above_one_is_rejected():
    with pytest.raises(EnvelopeError):
        validate_envelope(_good_envelope(confidence=1.5))




@pytest.mark.asyncio
async def test_publish_validates_envelope_and_returns_event_id():
    fake_redis = AsyncMock()
    fake_redis.publish = AsyncMock(return_value=1)
    with patch("events.bus.get_redis", AsyncMock(return_value=fake_redis)):
        event_id = await publish(
            Topic.BRAIN_DIRECTIVE,
            scope="channel",
            scope_id="BS001",
            payload={"action": "HOLD"},
            source_service="the-brain",
            confidence=0.8,
        )
    assert isinstance(event_id, str) and len(event_id) > 0
    args, _ = fake_redis.publish.call_args
    assert args[0] == Topic.BRAIN_DIRECTIVE.value
    sent = json.loads(args[1])
    assert sent["scope_id"] == "BS001"
    assert sent["payload"] == {"action": "HOLD"}
    assert sent["event_id"] == event_id


@pytest.mark.asyncio
async def test_publish_rejects_bad_envelope_before_redis_call():
    fake_redis = AsyncMock()
    fake_redis.publish = AsyncMock()
    with patch("events.bus.get_redis", AsyncMock(return_value=fake_redis)):
        with pytest.raises(EnvelopeError):
            await publish(
                Topic.BRAIN_DIRECTIVE,
                scope="universe",
                scope_id="x",
                payload={},
                source_service="the-brain",
            )
    fake_redis.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscribe_drops_invalid_messages_and_dispatches_valid_ones():
    """A subscriber must survive a poisoned producer."""
    good = _good_envelope(payload={"action": "HOLD"})
    bad = {"missing": "fields"}
    stream = [
        {"type": "subscribe"},
        {"type": "message", "channel": Topic.BRAIN_DIRECTIVE.value, "data": "{not-json"},
        {"type": "message", "channel": Topic.BRAIN_DIRECTIVE.value, "data": json.dumps(bad)},
        {"type": "message", "channel": Topic.BRAIN_DIRECTIVE.value, "data": json.dumps(good)},
    ]

    class _FakePubSub:
        def __init__(self):
            self.subscribe = AsyncMock()
            self.unsubscribe = AsyncMock()
            self.close = AsyncMock()
        async def listen(self):
            for msg in stream:
                yield msg

    fake_pubsub = _FakePubSub()
    fake_redis = AsyncMock()
    fake_redis.pubsub = lambda: fake_pubsub
    received: list[dict] = []

    async def handler(env):
        received.append(env)
        raise StopIteration

    with patch("events.bus.get_redis", AsyncMock(return_value=fake_redis)), \
         patch("events.bus.get_pubsub_redis", AsyncMock(return_value=fake_redis)):
        import asyncio
        stop = asyncio.Event()

        async def handler2(env):
            received.append(env)
            stop.set()

        await subscribe([Topic.BRAIN_DIRECTIVE], handler2, stop_event=stop)

    assert len(received) == 1
    assert received[0]["payload"] == {"action": "HOLD"}
