import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DiscoverTopicsRequest(_message.Message):
    __slots__ = ("niche", "channel_id", "count", "constraints")
    class ConstraintsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    NICHE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    CONSTRAINTS_FIELD_NUMBER: _ClassVar[int]
    niche: str
    channel_id: str
    count: int
    constraints: _containers.ScalarMap[str, str]
    def __init__(self, niche: _Optional[str] = ..., channel_id: _Optional[str] = ..., count: _Optional[int] = ..., constraints: _Optional[_Mapping[str, str]] = ...) -> None: ...

class DiscoverTopicsResponse(_message.Message):
    __slots__ = ("topics", "bandit_state")
    TOPICS_FIELD_NUMBER: _ClassVar[int]
    BANDIT_STATE_FIELD_NUMBER: _ClassVar[int]
    topics: _containers.RepeatedCompositeFieldContainer[Topic]
    bandit_state: BanditState
    def __init__(self, topics: _Optional[_Iterable[_Union[Topic, _Mapping]]] = ..., bandit_state: _Optional[_Union[BanditState, _Mapping]] = ...) -> None: ...

class SelectTopicRequest(_message.Message):
    __slots__ = ("niche", "candidate_topics", "channel_id")
    NICHE_FIELD_NUMBER: _ClassVar[int]
    CANDIDATE_TOPICS_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    niche: str
    candidate_topics: _containers.RepeatedScalarFieldContainer[str]
    channel_id: str
    def __init__(self, niche: _Optional[str] = ..., candidate_topics: _Optional[_Iterable[str]] = ..., channel_id: _Optional[str] = ...) -> None: ...

class SelectTopicResponse(_message.Message):
    __slots__ = ("selected_topic", "selection_reason", "bandit_state")
    SELECTED_TOPIC_FIELD_NUMBER: _ClassVar[int]
    SELECTION_REASON_FIELD_NUMBER: _ClassVar[int]
    BANDIT_STATE_FIELD_NUMBER: _ClassVar[int]
    selected_topic: Topic
    selection_reason: str
    bandit_state: BanditState
    def __init__(self, selected_topic: _Optional[_Union[Topic, _Mapping]] = ..., selection_reason: _Optional[str] = ..., bandit_state: _Optional[_Union[BanditState, _Mapping]] = ...) -> None: ...

class CheckSimilarityRequest(_message.Message):
    __slots__ = ("text", "channel_id", "text_type", "top_k")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_TYPE_FIELD_NUMBER: _ClassVar[int]
    TOP_K_FIELD_NUMBER: _ClassVar[int]
    text: str
    channel_id: str
    text_type: str
    top_k: int
    def __init__(self, text: _Optional[str] = ..., channel_id: _Optional[str] = ..., text_type: _Optional[str] = ..., top_k: _Optional[int] = ...) -> None: ...

class CheckSimilarityResponse(_message.Message):
    __slots__ = ("is_duplicate", "matches")
    IS_DUPLICATE_FIELD_NUMBER: _ClassVar[int]
    MATCHES_FIELD_NUMBER: _ClassVar[int]
    is_duplicate: bool
    matches: _containers.RepeatedCompositeFieldContainer[SimilarityMatch]
    def __init__(self, is_duplicate: _Optional[bool] = ..., matches: _Optional[_Iterable[_Union[SimilarityMatch, _Mapping]]] = ...) -> None: ...

class CalculateSaturationRequest(_message.Message):
    __slots__ = ("topic", "niche", "channel_id")
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    NICHE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    topic: str
    niche: str
    channel_id: str
    def __init__(self, topic: _Optional[str] = ..., niche: _Optional[str] = ..., channel_id: _Optional[str] = ...) -> None: ...

class CalculateSaturationResponse(_message.Message):
    __slots__ = ("saturation_score", "competitor_count", "top_competitors")
    SATURATION_SCORE_FIELD_NUMBER: _ClassVar[int]
    COMPETITOR_COUNT_FIELD_NUMBER: _ClassVar[int]
    TOP_COMPETITORS_FIELD_NUMBER: _ClassVar[int]
    saturation_score: float
    competitor_count: int
    top_competitors: _containers.RepeatedCompositeFieldContainer[CompetitorVideo]
    def __init__(self, saturation_score: _Optional[float] = ..., competitor_count: _Optional[int] = ..., top_competitors: _Optional[_Iterable[_Union[CompetitorVideo, _Mapping]]] = ...) -> None: ...

class GetCompetitorInsightsRequest(_message.Message):
    __slots__ = ("niche", "limit")
    NICHE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    niche: str
    limit: int
    def __init__(self, niche: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class GetCompetitorInsightsResponse(_message.Message):
    __slots__ = ("videos", "last_updated")
    VIDEOS_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATED_FIELD_NUMBER: _ClassVar[int]
    videos: _containers.RepeatedCompositeFieldContainer[CompetitorVideo]
    last_updated: _timestamp_pb2.Timestamp
    def __init__(self, videos: _Optional[_Iterable[_Union[CompetitorVideo, _Mapping]]] = ..., last_updated: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Topic(_message.Message):
    __slots__ = ("id", "text", "cluster", "score", "saturation_score", "keywords", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    CLUSTER_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    SATURATION_SCORE_FIELD_NUMBER: _ClassVar[int]
    KEYWORDS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    text: str
    cluster: str
    score: float
    saturation_score: float
    keywords: _containers.RepeatedScalarFieldContainer[str]
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., text: _Optional[str] = ..., cluster: _Optional[str] = ..., score: _Optional[float] = ..., saturation_score: _Optional[float] = ..., keywords: _Optional[_Iterable[str]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class BanditState(_message.Message):
    __slots__ = ("arms", "total_pulls", "last_updated")
    class ArmsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: ArmState
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[ArmState, _Mapping]] = ...) -> None: ...
    ARMS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_PULLS_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATED_FIELD_NUMBER: _ClassVar[int]
    arms: _containers.MessageMap[str, ArmState]
    total_pulls: int
    last_updated: _timestamp_pb2.Timestamp
    def __init__(self, arms: _Optional[_Mapping[str, ArmState]] = ..., total_pulls: _Optional[int] = ..., last_updated: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ArmState(_message.Message):
    __slots__ = ("alpha", "beta", "pulls", "successes")
    ALPHA_FIELD_NUMBER: _ClassVar[int]
    BETA_FIELD_NUMBER: _ClassVar[int]
    PULLS_FIELD_NUMBER: _ClassVar[int]
    SUCCESSES_FIELD_NUMBER: _ClassVar[int]
    alpha: float
    beta: float
    pulls: int
    successes: int
    def __init__(self, alpha: _Optional[float] = ..., beta: _Optional[float] = ..., pulls: _Optional[int] = ..., successes: _Optional[int] = ...) -> None: ...

class SimilarityMatch(_message.Message):
    __slots__ = ("id", "text", "cosine_similarity", "hamming_distance", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    COSINE_SIMILARITY_FIELD_NUMBER: _ClassVar[int]
    HAMMING_DISTANCE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    text: str
    cosine_similarity: float
    hamming_distance: int
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., text: _Optional[str] = ..., cosine_similarity: _Optional[float] = ..., hamming_distance: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CompetitorVideo(_message.Message):
    __slots__ = ("video_id", "title", "channel_id", "view_count", "engagement_rate", "published_at", "embedding")
    VIDEO_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    VIEW_COUNT_FIELD_NUMBER: _ClassVar[int]
    ENGAGEMENT_RATE_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_AT_FIELD_NUMBER: _ClassVar[int]
    EMBEDDING_FIELD_NUMBER: _ClassVar[int]
    video_id: str
    title: str
    channel_id: str
    view_count: int
    engagement_rate: float
    published_at: _timestamp_pb2.Timestamp
    embedding: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, video_id: _Optional[str] = ..., title: _Optional[str] = ..., channel_id: _Optional[str] = ..., view_count: _Optional[int] = ..., engagement_rate: _Optional[float] = ..., published_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., embedding: _Optional[_Iterable[float]] = ...) -> None: ...
