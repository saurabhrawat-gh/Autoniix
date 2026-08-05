"""Event bus — agentic-vision shared envelope, topic registry, and pub/sub.

Public re-exports so call-sites can do::

    from events import Topic, publish, subscribe, EnvelopeError
"""

from events.bus import EnvelopeError, publish, subscribe, validate_envelope
from events.topics import Topic

__all__ = [
    "Topic",
    "publish",
    "subscribe",
    "validate_envelope",
    "EnvelopeError",
]
