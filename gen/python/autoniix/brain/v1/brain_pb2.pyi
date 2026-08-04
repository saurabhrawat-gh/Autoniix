from autoniix.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class MakeDecisionRequest(_message.Message):
    __slots__ = ("content_id", "metrics", "channel_id", "decision_type")
    class MetricsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: MetricValue
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[MetricValue, _Mapping]] = ...) -> None: ...
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    DECISION_TYPE_FIELD_NUMBER: _ClassVar[int]
    content_id: str
    metrics: _containers.MessageMap[str, MetricValue]
    channel_id: str
    decision_type: str
    def __init__(self, content_id: _Optional[str] = ..., metrics: _Optional[_Mapping[str, MetricValue]] = ..., channel_id: _Optional[str] = ..., decision_type: _Optional[str] = ...) -> None: ...

class MakeDecisionResponse(_message.Message):
    __slots__ = ("decision", "confidence", "fired_rules", "reasoning")
    DECISION_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    FIRED_RULES_FIELD_NUMBER: _ClassVar[int]
    REASONING_FIELD_NUMBER: _ClassVar[int]
    decision: str
    confidence: float
    fired_rules: _containers.RepeatedCompositeFieldContainer[Rule]
    reasoning: str
    def __init__(self, decision: _Optional[str] = ..., confidence: _Optional[float] = ..., fired_rules: _Optional[_Iterable[_Union[Rule, _Mapping]]] = ..., reasoning: _Optional[str] = ...) -> None: ...

class EvaluateQualityRequest(_message.Message):
    __slots__ = ("content_id", "channel_id", "metrics")
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    content_id: str
    channel_id: str
    metrics: QualityMetrics
    def __init__(self, content_id: _Optional[str] = ..., channel_id: _Optional[str] = ..., metrics: _Optional[_Union[QualityMetrics, _Mapping]] = ...) -> None: ...

class EvaluateQualityResponse(_message.Message):
    __slots__ = ("passed", "quality_score", "gates", "recommendation")
    PASSED_FIELD_NUMBER: _ClassVar[int]
    QUALITY_SCORE_FIELD_NUMBER: _ClassVar[int]
    GATES_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDATION_FIELD_NUMBER: _ClassVar[int]
    passed: bool
    quality_score: float
    gates: _containers.RepeatedCompositeFieldContainer[QualityGate]
    recommendation: str
    def __init__(self, passed: _Optional[bool] = ..., quality_score: _Optional[float] = ..., gates: _Optional[_Iterable[_Union[QualityGate, _Mapping]]] = ..., recommendation: _Optional[str] = ...) -> None: ...

class UpdateThresholdsRequest(_message.Message):
    __slots__ = ("channel_id", "thresholds")
    class ThresholdsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    THRESHOLDS_FIELD_NUMBER: _ClassVar[int]
    channel_id: str
    thresholds: _containers.ScalarMap[str, float]
    def __init__(self, channel_id: _Optional[str] = ..., thresholds: _Optional[_Mapping[str, float]] = ...) -> None: ...

class GetThresholdsRequest(_message.Message):
    __slots__ = ("channel_id",)
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    channel_id: str
    def __init__(self, channel_id: _Optional[str] = ...) -> None: ...

class GetThresholdsResponse(_message.Message):
    __slots__ = ("thresholds",)
    class ThresholdsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    THRESHOLDS_FIELD_NUMBER: _ClassVar[int]
    thresholds: _containers.ScalarMap[str, float]
    def __init__(self, thresholds: _Optional[_Mapping[str, float]] = ...) -> None: ...

class MetricValue(_message.Message):
    __slots__ = ("numeric", "text", "boolean")
    NUMERIC_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    BOOLEAN_FIELD_NUMBER: _ClassVar[int]
    numeric: float
    text: str
    boolean: bool
    def __init__(self, numeric: _Optional[float] = ..., text: _Optional[str] = ..., boolean: _Optional[bool] = ...) -> None: ...

class Rule(_message.Message):
    __slots__ = ("id", "name", "condition", "action", "priority")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CONDITION_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    condition: str
    action: str
    priority: int
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., condition: _Optional[str] = ..., action: _Optional[str] = ..., priority: _Optional[int] = ...) -> None: ...

class QualityMetrics(_message.Message):
    __slots__ = ("script_coherence", "voice_quality", "visual_quality", "engagement_predicted", "brand_alignment")
    SCRIPT_COHERENCE_FIELD_NUMBER: _ClassVar[int]
    VOICE_QUALITY_FIELD_NUMBER: _ClassVar[int]
    VISUAL_QUALITY_FIELD_NUMBER: _ClassVar[int]
    ENGAGEMENT_PREDICTED_FIELD_NUMBER: _ClassVar[int]
    BRAND_ALIGNMENT_FIELD_NUMBER: _ClassVar[int]
    script_coherence: float
    voice_quality: float
    visual_quality: float
    engagement_predicted: float
    brand_alignment: float
    def __init__(self, script_coherence: _Optional[float] = ..., voice_quality: _Optional[float] = ..., visual_quality: _Optional[float] = ..., engagement_predicted: _Optional[float] = ..., brand_alignment: _Optional[float] = ...) -> None: ...

class QualityGate(_message.Message):
    __slots__ = ("name", "passed", "threshold", "actual_value", "severity")
    NAME_FIELD_NUMBER: _ClassVar[int]
    PASSED_FIELD_NUMBER: _ClassVar[int]
    THRESHOLD_FIELD_NUMBER: _ClassVar[int]
    ACTUAL_VALUE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    name: str
    passed: bool
    threshold: float
    actual_value: float
    severity: str
    def __init__(self, name: _Optional[str] = ..., passed: _Optional[bool] = ..., threshold: _Optional[float] = ..., actual_value: _Optional[float] = ..., severity: _Optional[str] = ...) -> None: ...
