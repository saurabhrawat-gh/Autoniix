"""Event bus — agentic-vision shared envelope, topic registry, and pub/sub.

Public re-exports so call-sites can do::

    from src.events import Topic, publish, subscribe, EnvelopeError
"""
from src.events.bus import EnvelopeError, publish, subscribe, validate_envelope
from src.events.topics import Topic

__all__ = [
    "Topic",
    "publish",
    "subscribe",
    "validate_envelope",
    "EnvelopeError",
]
