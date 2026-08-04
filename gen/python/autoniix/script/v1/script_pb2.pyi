from autoniix.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GenerateScriptRequest(_message.Message):
    __slots__ = ("topic", "niche", "channel_id", "target_duration_seconds", "style", "parameters")
    class ParametersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    NICHE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_DURATION_SECONDS_FIELD_NUMBER: _ClassVar[int]
    STYLE_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    topic: str
    niche: str
    channel_id: str
    target_duration_seconds: int
    style: str
    parameters: _containers.ScalarMap[str, str]
    def __init__(self, topic: _Optional[str] = ..., niche: _Optional[str] = ..., channel_id: _Optional[str] = ..., target_duration_seconds: _Optional[int] = ..., style: _Optional[str] = ..., parameters: _Optional[_Mapping[str, str]] = ...) -> None: ...

class GenerateScriptResponse(_message.Message):
    __slots__ = ("script", "generation_cost", "generation_time_ms")
    SCRIPT_FIELD_NUMBER: _ClassVar[int]
    GENERATION_COST_FIELD_NUMBER: _ClassVar[int]
    GENERATION_TIME_MS_FIELD_NUMBER: _ClassVar[int]
    script: Script
    generation_cost: float
    generation_time_ms: int
    def __init__(self, script: _Optional[_Union[Script, _Mapping]] = ..., generation_cost: _Optional[float] = ..., generation_time_ms: _Optional[int] = ...) -> None: ...

class ExpandScriptRequest(_message.Message):
    __slots__ = ("script_id", "outline", "channel_id", "parameters")
    class ParametersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    SCRIPT_ID_FIELD_NUMBER: _ClassVar[int]
    OUTLINE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    script_id: str
    outline: str
    channel_id: str
    parameters: _containers.ScalarMap[str, str]
    def __init__(self, script_id: _Optional[str] = ..., outline: _Optional[str] = ..., channel_id: _Optional[str] = ..., parameters: _Optional[_Mapping[str, str]] = ...) -> None: ...

class ExpandScriptResponse(_message.Message):
    __slots__ = ("script",)
    SCRIPT_FIELD_NUMBER: _ClassVar[int]
    script: Script
    def __init__(self, script: _Optional[_Union[Script, _Mapping]] = ...) -> None: ...

class ValidateScriptRequest(_message.Message):
    __slots__ = ("script_id", "content")
    SCRIPT_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    script_id: str
    content: str
    def __init__(self, script_id: _Optional[str] = ..., content: _Optional[str] = ...) -> None: ...

class ValidateScriptResponse(_message.Message):
    __slots__ = ("valid", "issues", "quality_score")
    VALID_FIELD_NUMBER: _ClassVar[int]
    ISSUES_FIELD_NUMBER: _ClassVar[int]
    QUALITY_SCORE_FIELD_NUMBER: _ClassVar[int]
    valid: bool
    issues: _containers.RepeatedCompositeFieldContainer[ValidationIssue]
    quality_score: float
    def __init__(self, valid: _Optional[bool] = ..., issues: _Optional[_Iterable[_Union[ValidationIssue, _Mapping]]] = ..., quality_score: _Optional[float] = ...) -> None: ...

class GetScriptHistoryRequest(_message.Message):
    __slots__ = ("channel_id", "pagination")
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    channel_id: str
    pagination: _common_pb2.PaginationRequest
    def __init__(self, channel_id: _Optional[str] = ..., pagination: _Optional[_Union[_common_pb2.PaginationRequest, _Mapping]] = ...) -> None: ...

class GetScriptHistoryResponse(_message.Message):
    __slots__ = ("scripts", "pagination")
    SCRIPTS_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    scripts: _containers.RepeatedCompositeFieldContainer[Script]
    pagination: _common_pb2.PaginationResponse
    def __init__(self, scripts: _Optional[_Iterable[_Union[Script, _Mapping]]] = ..., pagination: _Optional[_Union[_common_pb2.PaginationResponse, _Mapping]] = ...) -> None: ...

class Script(_message.Message):
    __slots__ = ("id", "topic", "content", "segments", "duration_seconds", "word_count", "style", "metadata")
    ID_FIELD_NUMBER: _ClassVar[int]
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    SEGMENTS_FIELD_NUMBER: _ClassVar[int]
    DURATION_SECONDS_FIELD_NUMBER: _ClassVar[int]
    WORD_COUNT_FIELD_NUMBER: _ClassVar[int]
    STYLE_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    id: str
    topic: str
    content: str
    segments: _containers.RepeatedCompositeFieldContainer[ScriptSegment]
    duration_seconds: int
    word_count: int
    style: str
    metadata: _common_pb2.ResourceMetadata
    def __init__(self, id: _Optional[str] = ..., topic: _Optional[str] = ..., content: _Optional[str] = ..., segments: _Optional[_Iterable[_Union[ScriptSegment, _Mapping]]] = ..., duration_seconds: _Optional[int] = ..., word_count: _Optional[int] = ..., style: _Optional[str] = ..., metadata: _Optional[_Union[_common_pb2.ResourceMetadata, _Mapping]] = ...) -> None: ...

class ScriptSegment(_message.Message):
    __slots__ = ("index", "text", "start_time_ms", "end_time_ms", "scene_type")
    INDEX_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    START_TIME_MS_FIELD_NUMBER: _ClassVar[int]
    END_TIME_MS_FIELD_NUMBER: _ClassVar[int]
    SCENE_TYPE_FIELD_NUMBER: _ClassVar[int]
    index: int
    text: str
    start_time_ms: int
    end_time_ms: int
    scene_type: str
    def __init__(self, index: _Optional[int] = ..., text: _Optional[str] = ..., start_time_ms: _Optional[int] = ..., end_time_ms: _Optional[int] = ..., scene_type: _Optional[str] = ...) -> None: ...

class ValidationIssue(_message.Message):
    __slots__ = ("type", "message", "severity", "line_number")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    LINE_NUMBER_FIELD_NUMBER: _ClassVar[int]
    type: str
    message: str
    severity: str
    line_number: int
    def __init__(self, type: _Optional[str] = ..., message: _Optional[str] = ..., severity: _Optional[str] = ..., line_number: _Optional[int] = ...) -> None: ...
