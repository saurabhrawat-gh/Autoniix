import datetime

from autoniix.common.v1 import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetDashboardStatsRequest(_message.Message):
    __slots__ = ("workspace_id", "time_range")
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_RANGE_FIELD_NUMBER: _ClassVar[int]
    workspace_id: str
    time_range: _common_pb2.TimeRange
    def __init__(self, workspace_id: _Optional[str] = ..., time_range: _Optional[_Union[_common_pb2.TimeRange, _Mapping]] = ...) -> None: ...

class GetDashboardStatsResponse(_message.Message):
    __slots__ = ("total_videos", "pending_review", "published_videos", "total_views", "total_revenue", "total_cost", "daily_stats")
    TOTAL_VIDEOS_FIELD_NUMBER: _ClassVar[int]
    PENDING_REVIEW_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_VIDEOS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_VIEWS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_REVENUE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_COST_FIELD_NUMBER: _ClassVar[int]
    DAILY_STATS_FIELD_NUMBER: _ClassVar[int]
    total_videos: int
    pending_review: int
    published_videos: int
    total_views: float
    total_revenue: float
    total_cost: float
    daily_stats: _containers.RepeatedCompositeFieldContainer[DailyStat]
    def __init__(self, total_videos: _Optional[int] = ..., pending_review: _Optional[int] = ..., published_videos: _Optional[int] = ..., total_views: _Optional[float] = ..., total_revenue: _Optional[float] = ..., total_cost: _Optional[float] = ..., daily_stats: _Optional[_Iterable[_Union[DailyStat, _Mapping]]] = ...) -> None: ...

class GetChannelMetricsRequest(_message.Message):
    __slots__ = ("channel_id", "time_range")
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_RANGE_FIELD_NUMBER: _ClassVar[int]
    channel_id: str
    time_range: _common_pb2.TimeRange
    def __init__(self, channel_id: _Optional[str] = ..., time_range: _Optional[_Union[_common_pb2.TimeRange, _Mapping]] = ...) -> None: ...

class GetChannelMetricsResponse(_message.Message):
    __slots__ = ("total_views", "total_subscribers", "avg_view_duration", "engagement_rate", "time_series")
    TOTAL_VIEWS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SUBSCRIBERS_FIELD_NUMBER: _ClassVar[int]
    AVG_VIEW_DURATION_FIELD_NUMBER: _ClassVar[int]
    ENGAGEMENT_RATE_FIELD_NUMBER: _ClassVar[int]
    TIME_SERIES_FIELD_NUMBER: _ClassVar[int]
    total_views: int
    total_subscribers: int
    avg_view_duration: float
    engagement_rate: float
    time_series: _containers.RepeatedCompositeFieldContainer[MetricTimeSeries]
    def __init__(self, total_views: _Optional[int] = ..., total_subscribers: _Optional[int] = ..., avg_view_duration: _Optional[float] = ..., engagement_rate: _Optional[float] = ..., time_series: _Optional[_Iterable[_Union[MetricTimeSeries, _Mapping]]] = ...) -> None: ...

class GetVideoPerformanceRequest(_message.Message):
    __slots__ = ("video_id",)
    VIDEO_ID_FIELD_NUMBER: _ClassVar[int]
    video_id: str
    def __init__(self, video_id: _Optional[str] = ...) -> None: ...

class GetVideoPerformanceResponse(_message.Message):
    __slots__ = ("metrics", "insights")
    METRICS_FIELD_NUMBER: _ClassVar[int]
    INSIGHTS_FIELD_NUMBER: _ClassVar[int]
    metrics: VideoMetrics
    insights: _containers.RepeatedCompositeFieldContainer[PerformanceInsight]
    def __init__(self, metrics: _Optional[_Union[VideoMetrics, _Mapping]] = ..., insights: _Optional[_Iterable[_Union[PerformanceInsight, _Mapping]]] = ...) -> None: ...

class GetCostAnalysisRequest(_message.Message):
    __slots__ = ("workspace_id", "time_range")
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_RANGE_FIELD_NUMBER: _ClassVar[int]
    workspace_id: str
    time_range: _common_pb2.TimeRange
    def __init__(self, workspace_id: _Optional[str] = ..., time_range: _Optional[_Union[_common_pb2.TimeRange, _Mapping]] = ...) -> None: ...

class GetCostAnalysisResponse(_message.Message):
    __slots__ = ("total_cost", "breakdown", "trends")
    TOTAL_COST_FIELD_NUMBER: _ClassVar[int]
    BREAKDOWN_FIELD_NUMBER: _ClassVar[int]
    TRENDS_FIELD_NUMBER: _ClassVar[int]
    total_cost: float
    breakdown: CostBreakdown
    trends: _containers.RepeatedCompositeFieldContainer[CostTrend]
    def __init__(self, total_cost: _Optional[float] = ..., breakdown: _Optional[_Union[CostBreakdown, _Mapping]] = ..., trends: _Optional[_Iterable[_Union[CostTrend, _Mapping]]] = ...) -> None: ...

class DailyStat(_message.Message):
    __slots__ = ("date", "videos_created", "views", "cost", "revenue")
    DATE_FIELD_NUMBER: _ClassVar[int]
    VIDEOS_CREATED_FIELD_NUMBER: _ClassVar[int]
    VIEWS_FIELD_NUMBER: _ClassVar[int]
    COST_FIELD_NUMBER: _ClassVar[int]
    REVENUE_FIELD_NUMBER: _ClassVar[int]
    date: _timestamp_pb2.Timestamp
    videos_created: int
    views: int
    cost: float
    revenue: float
    def __init__(self, date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., videos_created: _Optional[int] = ..., views: _Optional[int] = ..., cost: _Optional[float] = ..., revenue: _Optional[float] = ...) -> None: ...

class MetricTimeSeries(_message.Message):
    __slots__ = ("metric_name", "points")
    METRIC_NAME_FIELD_NUMBER: _ClassVar[int]
    POINTS_FIELD_NUMBER: _ClassVar[int]
    metric_name: str
    points: _containers.RepeatedCompositeFieldContainer[DataPoint]
    def __init__(self, metric_name: _Optional[str] = ..., points: _Optional[_Iterable[_Union[DataPoint, _Mapping]]] = ...) -> None: ...

class DataPoint(_message.Message):
    __slots__ = ("timestamp", "value")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    timestamp: _timestamp_pb2.Timestamp
    value: float
    def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., value: _Optional[float] = ...) -> None: ...

class VideoMetrics(_message.Message):
    __slots__ = ("video_id", "views", "likes", "comments", "avg_view_percentage", "click_through_rate", "engagement_rate")
    VIDEO_ID_FIELD_NUMBER: _ClassVar[int]
    VIEWS_FIELD_NUMBER: _ClassVar[int]
    LIKES_FIELD_NUMBER: _ClassVar[int]
    COMMENTS_FIELD_NUMBER: _ClassVar[int]
    AVG_VIEW_PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
    CLICK_THROUGH_RATE_FIELD_NUMBER: _ClassVar[int]
    ENGAGEMENT_RATE_FIELD_NUMBER: _ClassVar[int]
    video_id: str
    views: int
    likes: int
    comments: int
    avg_view_percentage: float
    click_through_rate: float
    engagement_rate: float
    def __init__(self, video_id: _Optional[str] = ..., views: _Optional[int] = ..., likes: _Optional[int] = ..., comments: _Optional[int] = ..., avg_view_percentage: _Optional[float] = ..., click_through_rate: _Optional[float] = ..., engagement_rate: _Optional[float] = ...) -> None: ...

class PerformanceInsight(_message.Message):
    __slots__ = ("type", "message", "severity", "impact_score")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    IMPACT_SCORE_FIELD_NUMBER: _ClassVar[int]
    type: str
    message: str
    severity: str
    impact_score: float
    def __init__(self, type: _Optional[str] = ..., message: _Optional[str] = ..., severity: _Optional[str] = ..., impact_score: _Optional[float] = ...) -> None: ...

class CostBreakdown(_message.Message):
    __slots__ = ("llm_cost", "voice_cost", "asset_cost", "infrastructure_cost", "other_cost")
    LLM_COST_FIELD_NUMBER: _ClassVar[int]
    VOICE_COST_FIELD_NUMBER: _ClassVar[int]
    ASSET_COST_FIELD_NUMBER: _ClassVar[int]
    INFRASTRUCTURE_COST_FIELD_NUMBER: _ClassVar[int]
    OTHER_COST_FIELD_NUMBER: _ClassVar[int]
    llm_cost: float
    voice_cost: float
    asset_cost: float
    infrastructure_cost: float
    other_cost: float
    def __init__(self, llm_cost: _Optional[float] = ..., voice_cost: _Optional[float] = ..., asset_cost: _Optional[float] = ..., infrastructure_cost: _Optional[float] = ..., other_cost: _Optional[float] = ...) -> None: ...

class CostTrend(_message.Message):
    __slots__ = ("date", "category", "amount")
    DATE_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    date: _timestamp_pb2.Timestamp
    category: str
    amount: float
    def __init__(self, date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., category: _Optional[str] = ..., amount: _Optional[float] = ...) -> None: ...
