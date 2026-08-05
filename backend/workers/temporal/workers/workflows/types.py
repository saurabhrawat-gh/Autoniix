"""Shared types and constants for Python workflows.

Mirrors ``go-workflows/types.go``. Retry policies match the Go originals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Sequence

from temporalio.common import RetryPolicy

# ── Input/output types (mirror src/schemas/common.py) ─────────────────────────


@dataclass
class VideoParams:
    """Input to VideoProductionWorkflow."""

    channel_id: str
    content_mode: str
    topic_candidates: Sequence[str] = field(default_factory=list)
    max_cost_usd: float = 2.50
    human_review_required: bool = False
    resume_from: str = ""
    original_content_id: str = ""
    content_id: str = ""
    environment: str = ""


@dataclass
class VideoResult:
    """Output of VideoProductionWorkflow."""

    status: str = ""
    content_id: str = ""
    youtube_video_id: str = ""
    cost: float = 0.0
    reason: str = ""


# ── Ordered production-phase list ─────────────────────────────────────────────

WORKFLOW_PHASES: list[str] = [
    "researching",
    "brand_check",
    "scripting",
    "generating_voice",
    "generating_assets",
    "directing",
    "post_production",
    "rendering",
    "finishing",
    "delivering",
    "analytics",
]


# ── Retry policies (mirror Python constants in the Go original) ──────────────

RETRY_STANDARD = RetryPolicy(
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
    non_retryable_error_types=["BudgetExceededError", "ValidationError"],
)

RETRY_RENDER = RetryPolicy(
    initial_interval=timedelta(seconds=30),
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=2,
)

RETRY_FINISH = RetryPolicy(
    initial_interval=timedelta(seconds=30),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=3,
)

RETRY_LIGHT = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=2,
)


# ── Phase helpers ─────────────────────────────────────────────────────────────


def should_skip(phase: str, resume_from: str) -> bool:
    """Return True when ``phase`` was already completed before ``resume_from``."""
    if not resume_from:
        return False
    try:
        phase_idx = WORKFLOW_PHASES.index(phase)
        resume_idx = WORKFLOW_PHASES.index(resume_from)
    except ValueError:
        return False
    return phase_idx < resume_idx


def add_cost(result: dict[str, Any] | None) -> float:
    """Extract ``cost.cost_usd`` from an activity result, defaulting to 0."""
    if not result:
        return 0.0
    cost = result.get("cost")
    if not isinstance(cost, dict):
        return 0.0
    v = cost.get("cost_usd", 0.0)
    return float(v) if isinstance(v, (int, float)) else 0.0
