"""Canonical Redis pub/sub topic registry for the agentic vision.

A single string-Enum is the source of truth for every topic. Importing
``Topic`` instead of typing literals gives IDE autocomplete, prevents
typos, and lets the linter catch unknown topic names at review time.

Topic names map 1:1 to the locked envelope contract in
``src/events/schema.json`` and the spec on AE-509 / AE-342.

When a future phase needs a new topic, add it here. The matching
:class:`Topic.is_known` test guards subscribe() against unknown topics.
"""
from __future__ import annotations

from enum import Enum


class Topic(str, Enum):
    """All Redis pub/sub topics produced by the agentic stack."""

    # ── Brain → downstream services
    BRAIN_COMPLIANCE_ALERT = "brain.compliance.alert"
    BRAIN_STRATEGY_BRIEF = "brain.strategy.brief"
    BRAIN_PREVENTOR_RISK = "brain.preventor.risk"
    BRAIN_ANALYST_GAP = "brain.analyst.gap"
    BRAIN_EMOTION_PROFILE = "brain.emotion.profile"
    BRAIN_DIRECTIVE = "brain.directive"
    BRAIN_VELOCITY = "brain.velocity"
    BRAIN_SEO_BRIEF = "brain.seo.brief"

    # ── Pipeline → Brain
    PIPELINE_VIDEO_COMPLETE = "pipeline.video.complete"
    PIPELINE_VIDEO_FAILED = "pipeline.video.failed"
    PIPELINE_SURGE_SIGNAL = "pipeline.surge.signal"

    # ── Internal/system
    SYSTEM_CHAOS_TEST = "system.chaos.test"

    @classmethod
    def is_known(cls, value: str) -> bool:
        try:
            cls(value)
        except ValueError:
            return False
        return True


# Convenience: comma-separated string for docs / logging
ALL_TOPICS: tuple[Topic, ...] = tuple(Topic)
