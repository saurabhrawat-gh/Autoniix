"""Event bus — agentic-vision shared envelope, topic registry, pub/sub + Streams.

Legacy pub/sub API (best-effort broadcast, no delivery guarantees):

    from events import Topic, publish, subscribe

Durable Streams API (consumer groups, XACK, XAUTOCLAIM reclaim):

    from events import publish_stream, consume_stream

Migration path (dual-write): during transition, publishers should call
``publish_dual_write`` — legacy subscribers keep working AND new
Streams consumers get durable delivery.
"""

from events.bus import EnvelopeError, publish, subscribe, validate_envelope
from events.streams import (
    consume_stream,
    publish_dual_write,
    publish_stream,
)
from events.topics import Topic

__all__ = [
    "Topic",
    "publish",
    "subscribe",
    "validate_envelope",
    "EnvelopeError",
    "publish_stream",
    "publish_dual_write",
    "consume_stream",
]
