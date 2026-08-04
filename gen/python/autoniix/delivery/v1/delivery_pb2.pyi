import datetime

from autoniix.common.v1 import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class UploadVideoRequest(_message.Message):
    __slots__ = ("content_id", "channel_id", "content_mode", "title", "description", "tags", "video_url", "thumbnail_url", "privacy_status", "category_id", "is_short", "scheduled_at", "quality_scores", "quality_gate_override", "quality_gate_override_reason", "quality_gate_override_by")
    class QualityScoresEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_MODE_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    VIDEO_URL_FIELD_NUMBER: _ClassVar[int]
    THUMBNAIL_URL_FIELD_NUMBER: _ClassVar[int]
    PRIVACY_STATUS_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_ID_FIELD_NUMBER: _ClassVar[int]
    IS_SHORT_FIELD_NUMBER: _ClassVar[int]
    SCHEDULED_AT_FIELD_NUMBER: _ClassVar[int]
    QUALITY_SCORES_FIELD_NUMBER: _ClassVar[int]
    QUALITY_GATE_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    QUALITY_GATE_OVERRIDE_REASON_FIELD_NUMBER: _ClassVar[int]
    QUALITY_GATE_OVERRIDE_BY_FIELD_NUMBER: _ClassVar[int]
    content_id: str
    channel_id: str
    content_mode: str
    title: str
    description: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    video_url: str
    thumbnail_url: str
    privacy_status: str
    category_id: str
    is_short: bool
    scheduled_at: _timestamp_pb2.Timestamp
    quality_scores: _containers.ScalarMap[str, float]
    quality_gate_override: bool
    quality_gate_override_reason: str
    quality_gate_override_by: str
    def __init__(self, content_id: _Optional[str] = ..., channel_id: _Optional[str] = ..., content_mode: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., video_url: _Optional[str] = ..., thumbnail_url: _Optional[str] = ..., privacy_status: _Optional[str] = ..., category_id: _Optional[str] = ..., is_short: _Optional[bool] = ..., scheduled_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., quality_scores: _Optional[_Mapping[str, float]] = ..., quality_gate_override: _Optional[bool] = ..., quality_gate_override_reason: _Optional[str] = ..., quality_gate_override_by: _Optional[str] = ...) -> None: ...

class UploadVideoResponse(_message.Message):
    __slots__ = ("youtube_video_id", "youtube_url", "privacy_status", "intelligence", "cost_usd")
    YOUTUBE_VIDEO_ID_FIELD_NUMBER: _ClassVar[int]
    YOUTUBE_URL_FIELD_NUMBER: _ClassVar[int]
    PRIVACY_STATUS_FIELD_NUMBER: _ClassVar[int]
    INTELLIGENCE_FIELD_NUMBER: _ClassVar[int]
    COST_USD_FIELD_NUMBER: _ClassVar[int]
    youtube_video_id: str
    youtube_url: str
    privacy_status: str
    intelligence: SEOResult
    cost_usd: float
    def __init__(self, youtube_video_id: _Optional[str] = ..., youtube_url: _Optional[str] = ..., privacy_status: _Optional[str] = ..., intelligence: _Optional[_Union[SEOResult, _Mapping]] = ..., cost_usd: _Optional[float] = ...) -> None: ...

class ComputeMetadataRequest(_message.Message):
    __slots__ = ("content_id", "channel_id", "content_mode", "title", "description", "tags", "niche", "quality_scores", "is_short")
    class QualityScoresEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_MODE_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    NICHE_FIELD_NUMBER: _ClassVar[int]
    QUALITY_SCORES_FIELD_NUMBER: _ClassVar[int]
    IS_SHORT_FIELD_NUMBER: _ClassVar[int]
    content_id: str
    channel_id: str
    content_mode: str
    title: str
    description: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    niche: str
    quality_scores: _containers.ScalarMap[str, float]
    is_short: bool
    def __init__(self, content_id: _Optional[str] = ..., channel_id: _Optional[str] = ..., content_mode: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., niche: _Optional[str] = ..., quality_scores: _Optional[_Mapping[str, float]] = ..., is_short: _Optional[bool] = ...) -> None: ...

class ComputeMetadataResponse(_message.Message):
    __slots__ = ("title", "description", "tags", "hashtags", "category_id", "seo_score", "final_composite_score")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    HASHTAGS_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_ID_FIELD_NUMBER: _ClassVar[int]
    SEO_SCORE_FIELD_NUMBER: _ClassVar[int]
    FINAL_COMPOSITE_SCORE_FIELD_NUMBER: _ClassVar[int]
    title: str
    description: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    hashtags: _containers.RepeatedScalarFieldContainer[str]
    category_id: str
    seo_score: float
    final_composite_score: float
    def __init__(self, title: _Optional[str] = ..., description: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., hashtags: _Optional[_Iterable[str]] = ..., category_id: _Optional[str] = ..., seo_score: _Optional[float] = ..., final_composite_score: _Optional[float] = ...) -> None: ...

class GetSEOScoreRequest(_message.Message):
    __slots__ = ("title", "description", "tags", "niche", "channel_id")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    NICHE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    title: str
    description: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    niche: str
    channel_id: str
    def __init__(self, title: _Optional[str] = ..., description: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., niche: _Optional[str] = ..., channel_id: _Optional[str] = ...) -> None: ...

class GetSEOScoreResponse(_message.Message):
    __slots__ = ("seo_score", "factors", "suggested_tags", "upload_timing")
    class UploadTimingEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    SEO_SCORE_FIELD_NUMBER: _ClassVar[int]
    FACTORS_FIELD_NUMBER: _ClassVar[int]
    SUGGESTED_TAGS_FIELD_NUMBER: _ClassVar[int]
    UPLOAD_TIMING_FIELD_NUMBER: _ClassVar[int]
    seo_score: float
    factors: _containers.RepeatedScalarFieldContainer[str]
    suggested_tags: _containers.RepeatedScalarFieldContainer[str]
    upload_timing: _containers.ScalarMap[str, str]
    def __init__(self, seo_score: _Optional[float] = ..., factors: _Optional[_Iterable[str]] = ..., suggested_tags: _Optional[_Iterable[str]] = ..., upload_timing: _Optional[_Mapping[str, str]] = ...) -> None: ...

class HumanReviewRequest(_message.Message):
    __slots__ = ("content_id", "approved", "reviewer", "notes")
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    APPROVED_FIELD_NUMBER: _ClassVar[int]
    REVIEWER_FIELD_NUMBER: _ClassVar[int]
    NOTES_FIELD_NUMBER: _ClassVar[int]
    content_id: str
    approved: bool
    reviewer: str
    notes: str
    def __init__(self, content_id: _Optional[str] = ..., approved: _Optional[bool] = ..., reviewer: _Optional[str] = ..., notes: _Optional[str] = ...) -> None: ...

class HumanReviewResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: _Optional[bool] = ..., message: _Optional[str] = ...) -> None: ...

class SEOResult(_message.Message):
    __slots__ = ("seo_score", "description_analysis", "optimal_upload_time", "tags_suggested")
    SEO_SCORE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_ANALYSIS_FIELD_NUMBER: _ClassVar[int]
    OPTIMAL_UPLOAD_TIME_FIELD_NUMBER: _ClassVar[int]
    TAGS_SUGGESTED_FIELD_NUMBER: _ClassVar[int]
    seo_score: float
    description_analysis: str
    optimal_upload_time: str
    tags_suggested: int
    def __init__(self, seo_score: _Optional[float] = ..., description_analysis: _Optional[str] = ..., optimal_upload_time: _Optional[str] = ..., tags_suggested: _Optional[int] = ...) -> None: ...
