from autoniix.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GenerateThumbnailRequest(_message.Message):
    __slots__ = ("content_id", "channel_id", "title", "niche", "content_mode", "parameters")
    class ParametersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    NICHE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_MODE_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    content_id: str
    channel_id: str
    title: str
    niche: str
    content_mode: str
    parameters: _containers.ScalarMap[str, str]
    def __init__(self, content_id: _Optional[str] = ..., channel_id: _Optional[str] = ..., title: _Optional[str] = ..., niche: _Optional[str] = ..., content_mode: _Optional[str] = ..., parameters: _Optional[_Mapping[str, str]] = ...) -> None: ...

class GenerateThumbnailResponse(_message.Message):
    __slots__ = ("selected_thumbnail", "all_variants", "thumbnail_score", "thumbnail_ctr_prediction", "concepts_generated", "cost_usd")
    SELECTED_THUMBNAIL_FIELD_NUMBER: _ClassVar[int]
    ALL_VARIANTS_FIELD_NUMBER: _ClassVar[int]
    THUMBNAIL_SCORE_FIELD_NUMBER: _ClassVar[int]
    THUMBNAIL_CTR_PREDICTION_FIELD_NUMBER: _ClassVar[int]
    CONCEPTS_GENERATED_FIELD_NUMBER: _ClassVar[int]
    COST_USD_FIELD_NUMBER: _ClassVar[int]
    selected_thumbnail: ThumbnailVariant
    all_variants: _containers.RepeatedCompositeFieldContainer[ThumbnailVariant]
    thumbnail_score: float
    thumbnail_ctr_prediction: float
    concepts_generated: int
    cost_usd: float
    def __init__(self, selected_thumbnail: _Optional[_Union[ThumbnailVariant, _Mapping]] = ..., all_variants: _Optional[_Iterable[_Union[ThumbnailVariant, _Mapping]]] = ..., thumbnail_score: _Optional[float] = ..., thumbnail_ctr_prediction: _Optional[float] = ..., concepts_generated: _Optional[int] = ..., cost_usd: _Optional[float] = ...) -> None: ...

class ThumbnailVariant(_message.Message):
    __slots__ = ("variant_id", "concept_name", "url", "predicted_ctr", "thumbnail_score", "text_overlay", "dall_e_prompt")
    VARIANT_ID_FIELD_NUMBER: _ClassVar[int]
    CONCEPT_NAME_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    PREDICTED_CTR_FIELD_NUMBER: _ClassVar[int]
    THUMBNAIL_SCORE_FIELD_NUMBER: _ClassVar[int]
    TEXT_OVERLAY_FIELD_NUMBER: _ClassVar[int]
    DALL_E_PROMPT_FIELD_NUMBER: _ClassVar[int]
    variant_id: int
    concept_name: str
    url: str
    predicted_ctr: float
    thumbnail_score: float
    text_overlay: str
    dall_e_prompt: str
    def __init__(self, variant_id: _Optional[int] = ..., concept_name: _Optional[str] = ..., url: _Optional[str] = ..., predicted_ctr: _Optional[float] = ..., thumbnail_score: _Optional[float] = ..., text_overlay: _Optional[str] = ..., dall_e_prompt: _Optional[str] = ...) -> None: ...

class ThumbnailFeedbackRequest(_message.Message):
    __slots__ = ("content_id", "channel_id", "actual_ctr", "impressions")
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    ACTUAL_CTR_FIELD_NUMBER: _ClassVar[int]
    IMPRESSIONS_FIELD_NUMBER: _ClassVar[int]
    content_id: str
    channel_id: str
    actual_ctr: float
    impressions: int
    def __init__(self, content_id: _Optional[str] = ..., channel_id: _Optional[str] = ..., actual_ctr: _Optional[float] = ..., impressions: _Optional[int] = ...) -> None: ...

class ThumbnailTrainRequest(_message.Message):
    __slots__ = ("niche",)
    NICHE_FIELD_NUMBER: _ClassVar[int]
    niche: str
    def __init__(self, niche: _Optional[str] = ...) -> None: ...

class ThumbnailTrainResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: _Optional[bool] = ..., message: _Optional[str] = ...) -> None: ...
