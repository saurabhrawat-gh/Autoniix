from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ContentMode(str, Enum):
    long_form = "long_form"
    short_form = "short_form"


class VideoStatus(str, Enum):
    pending = "pending"
    researching = "researching"
    scripting = "scripting"
    generating_voice = "generating_voice"
    generating_assets = "generating_assets"
    directing = "directing"
    assembling = "assembling"
    rendering = "rendering"
    pending_review = "pending_review"
    awaiting_review = "awaiting_review"
    delivering = "delivering"
    delivered = "delivered"
    test_delivered = "test_delivered"
    retrying = "retrying"
    stopped = "stopped"
    superseded = "superseded"
    failed = "failed"
    rejected = "rejected"


class ServiceResponse(BaseModel):
    status: str = "success"
    data: Any = None
    error: str | None = None
    cost: dict | None = None
    idempotency_key: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    service: str
    status: str = "healthy"
    version: str = "0.1.0"


class ResearchRequest(BaseModel):
    channel_id: str
    content_mode: str = "long_form"
    topic_candidates: list[str] = []
    budget_guard: dict = Field(default_factory=lambda: {"max_cost_usd": 2.50, "accrued_cost_usd": 0.0})


class ResearchResponse(BaseModel):
    selected_topic: str
    title_candidates: list[str] = []
    research_depth_score: float = 0.0
    sources: list[dict] = []
    fact_claims: list[dict] = []
    trend_data: dict = {}
    competitor_analysis: dict = {}


@dataclass
class VideoParams:
    channel_id: str
    content_mode: str = "long_form"
    topic_candidates: list[str] = field(default_factory=list)
    max_cost_usd: float = 2.50
    human_review_required: bool = False
    resume_from: str | None = None
    original_content_id: str | None = None
    content_id: str | None = None
    environment: str = "production"


@dataclass
class VideoResult:
    status: str = "pending"
    content_id: str | None = None
    youtube_video_id: str | None = None
    cost: float = 0.0
    reason: str | None = None


@dataclass
class BudgetGuard:
    max_cost_usd: float = 2.50
    accrued_cost_usd: float = 0.0
