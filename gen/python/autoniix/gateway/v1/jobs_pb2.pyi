import datetime

from autoniix.common.v1 import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ListJobsRequest(_message.Message):
    __slots__ = ("workspace_id", "pagination", "status_filter", "time_range", "sort_by", "sort_desc")
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FILTER_FIELD_NUMBER: _ClassVar[int]
    TIME_RANGE_FIELD_NUMBER: _ClassVar[int]
    SORT_BY_FIELD_NUMBER: _ClassVar[int]
    SORT_DESC_FIELD_NUMBER: _ClassVar[int]
    workspace_id: str
    pagination: _common_pb2.PaginationRequest
    status_filter: _containers.RepeatedScalarFieldContainer[_common_pb2.JobStatus]
    time_range: _common_pb2.TimeRange
    sort_by: str
    sort_desc: bool
    def __init__(self, workspace_id: _Optional[str] = ..., pagination: _Optional[_Union[_common_pb2.PaginationRequest, _Mapping]] = ..., status_filter: _Optional[_Iterable[_Union[_common_pb2.JobStatus, str]]] = ..., time_range: _Optional[_Union[_common_pb2.TimeRange, _Mapping]] = ..., sort_by: _Optional[str] = ..., sort_desc: _Optional[bool] = ...) -> None: ...

class ListJobsResponse(_message.Message):
    __slots__ = ("jobs", "pagination")
    JOBS_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    jobs: _containers.RepeatedCompositeFieldContainer[Job]
    pagination: _common_pb2.PaginationResponse
    def __init__(self, jobs: _Optional[_Iterable[_Union[Job, _Mapping]]] = ..., pagination: _Optional[_Union[_common_pb2.PaginationResponse, _Mapping]] = ...) -> None: ...

class GetJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class GetJobResponse(_message.Message):
    __slots__ = ("job",)
    JOB_FIELD_NUMBER: _ClassVar[int]
    job: Job
    def __init__(self, job: _Optional[_Union[Job, _Mapping]] = ...) -> None: ...

class CreateJobRequest(_message.Message):
    __slots__ = ("workspace_id", "channel_id", "config")
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    workspace_id: str
    channel_id: str
    config: JobConfig
    def __init__(self, workspace_id: _Optional[str] = ..., channel_id: _Optional[str] = ..., config: _Optional[_Union[JobConfig, _Mapping]] = ...) -> None: ...

class CreateJobResponse(_message.Message):
    __slots__ = ("job",)
    JOB_FIELD_NUMBER: _ClassVar[int]
    job: Job
    def __init__(self, job: _Optional[_Union[Job, _Mapping]] = ...) -> None: ...

class UpdateJobRequest(_message.Message):
    __slots__ = ("job_id", "config")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    config: JobConfig
    def __init__(self, job_id: _Optional[str] = ..., config: _Optional[_Union[JobConfig, _Mapping]] = ...) -> None: ...

class UpdateJobResponse(_message.Message):
    __slots__ = ("job",)
    JOB_FIELD_NUMBER: _ClassVar[int]
    job: Job
    def __init__(self, job: _Optional[_Union[Job, _Mapping]] = ...) -> None: ...

class DeleteJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class PauseJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class ResumeJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class RetryJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class StreamJobProgressRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class Job(_message.Message):
    __slots__ = ("id", "workspace_id", "channel_id", "status", "config", "progress", "created_at", "updated_at", "completed_at", "error_message")
    ID_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_AT_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    id: str
    workspace_id: str
    channel_id: str
    status: _common_pb2.JobStatus
    config: JobConfig
    progress: JobProgress
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    completed_at: _timestamp_pb2.Timestamp
    error_message: str
    def __init__(self, id: _Optional[str] = ..., workspace_id: _Optional[str] = ..., channel_id: _Optional[str] = ..., status: _Optional[_Union[_common_pb2.JobStatus, str]] = ..., config: _Optional[_Union[JobConfig, _Mapping]] = ..., progress: _Optional[_Union[JobProgress, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., completed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., error_message: _Optional[str] = ...) -> None: ...

class JobConfig(_message.Message):
    __slots__ = ("num_videos", "niche", "auto_publish", "parameters")
    class ParametersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    NUM_VIDEOS_FIELD_NUMBER: _ClassVar[int]
    NICHE_FIELD_NUMBER: _ClassVar[int]
    AUTO_PUBLISH_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    num_videos: int
    niche: str
    auto_publish: bool
    parameters: _containers.ScalarMap[str, str]
    def __init__(self, num_videos: _Optional[int] = ..., niche: _Optional[str] = ..., auto_publish: _Optional[bool] = ..., parameters: _Optional[_Mapping[str, str]] = ...) -> None: ...

class JobProgress(_message.Message):
    __slots__ = ("total_videos", "completed_videos", "failed_videos", "current_stage", "progress_percent", "started_at", "estimated_completion")
    TOTAL_VIDEOS_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_VIDEOS_FIELD_NUMBER: _ClassVar[int]
    FAILED_VIDEOS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_STAGE_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_PERCENT_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_COMPLETION_FIELD_NUMBER: _ClassVar[int]
    total_videos: int
    completed_videos: int
    failed_videos: int
    current_stage: str
    progress_percent: float
    started_at: _timestamp_pb2.Timestamp
    estimated_completion: _timestamp_pb2.Timestamp
    def __init__(self, total_videos: _Optional[int] = ..., completed_videos: _Optional[int] = ..., failed_videos: _Optional[int] = ..., current_stage: _Optional[str] = ..., progress_percent: _Optional[float] = ..., started_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., estimated_completion: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class JobProgressEvent(_message.Message):
    __slots__ = ("job_id", "status", "progress", "stage", "message", "timestamp")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    STAGE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    status: _common_pb2.JobStatus
    progress: JobProgress
    stage: str
    message: str
    timestamp: _timestamp_pb2.Timestamp
    def __init__(self, job_id: _Optional[str] = ..., status: _Optional[_Union[_common_pb2.JobStatus, str]] = ..., progress: _Optional[_Union[JobProgress, _Mapping]] = ..., stage: _Optional[str] = ..., message: _Optional[str] = ..., timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
