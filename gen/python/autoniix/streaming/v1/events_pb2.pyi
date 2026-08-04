import datetime

from autoniix.common.v1 import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SubscribeRequest(_message.Message):
    __slots__ = ("workspace_id", "event_types", "last_event_id", "replay_from_last")
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPES_FIELD_NUMBER: _ClassVar[int]
    LAST_EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    REPLAY_FROM_LAST_FIELD_NUMBER: _ClassVar[int]
    workspace_id: str
    event_types: _containers.RepeatedScalarFieldContainer[str]
    last_event_id: str
    replay_from_last: bool
    def __init__(self, workspace_id: _Optional[str] = ..., event_types: _Optional[_Iterable[str]] = ..., last_event_id: _Optional[str] = ..., replay_from_last: _Optional[bool] = ...) -> None: ...

class PublishRequest(_message.Message):
    __slots__ = ("event",)
    EVENT_FIELD_NUMBER: _ClassVar[int]
    event: Event
    def __init__(self, event: _Optional[_Union[Event, _Mapping]] = ...) -> None: ...

class AcknowledgeRequest(_message.Message):
    __slots__ = ("event_id", "subscriber_id")
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    SUBSCRIBER_ID_FIELD_NUMBER: _ClassVar[int]
    event_id: str
    subscriber_id: str
    def __init__(self, event_id: _Optional[str] = ..., subscriber_id: _Optional[str] = ...) -> None: ...

class Event(_message.Message):
    __slots__ = ("id", "type", "workspace_id", "timestamp", "job_event", "video_event", "system_event", "notification_event")
    ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    JOB_EVENT_FIELD_NUMBER: _ClassVar[int]
    VIDEO_EVENT_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_EVENT_FIELD_NUMBER: _ClassVar[int]
    NOTIFICATION_EVENT_FIELD_NUMBER: _ClassVar[int]
    id: str
    type: str
    workspace_id: str
    timestamp: _timestamp_pb2.Timestamp
    job_event: JobEvent
    video_event: VideoEvent
    system_event: SystemEvent
    notification_event: NotificationEvent
    def __init__(self, id: _Optional[str] = ..., type: _Optional[str] = ..., workspace_id: _Optional[str] = ..., timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., job_event: _Optional[_Union[JobEvent, _Mapping]] = ..., video_event: _Optional[_Union[VideoEvent, _Mapping]] = ..., system_event: _Optional[_Union[SystemEvent, _Mapping]] = ..., notification_event: _Optional[_Union[NotificationEvent, _Mapping]] = ...) -> None: ...

class JobEvent(_message.Message):
    __slots__ = ("job_id", "status", "stage", "progress_percent", "message")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STAGE_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_PERCENT_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    status: _common_pb2.JobStatus
    stage: str
    progress_percent: float
    message: str
    def __init__(self, job_id: _Optional[str] = ..., status: _Optional[_Union[_common_pb2.JobStatus, str]] = ..., stage: _Optional[str] = ..., progress_percent: _Optional[float] = ..., message: _Optional[str] = ...) -> None: ...

class VideoEvent(_message.Message):
    __slots__ = ("video_id", "action", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    VIDEO_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    video_id: str
    action: str
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, video_id: _Optional[str] = ..., action: _Optional[str] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...

class SystemEvent(_message.Message):
    __slots__ = ("component", "level", "message", "details")
    class DetailsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    COMPONENT_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    component: str
    level: str
    message: str
    details: _containers.ScalarMap[str, str]
    def __init__(self, component: _Optional[str] = ..., level: _Optional[str] = ..., message: _Optional[str] = ..., details: _Optional[_Mapping[str, str]] = ...) -> None: ...

class NotificationEvent(_message.Message):
    __slots__ = ("title", "message", "severity", "action_url")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    ACTION_URL_FIELD_NUMBER: _ClassVar[int]
    title: str
    message: str
    severity: str
    action_url: str
    def __init__(self, title: _Optional[str] = ..., message: _Optional[str] = ..., severity: _Optional[str] = ..., action_url: _Optional[str] = ...) -> None: ...
