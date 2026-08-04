from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SynthesizeVoiceRequest(_message.Message):
    __slots__ = ("script_id", "text", "voice_model_id", "channel_id", "settings")
    SCRIPT_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    VOICE_MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    script_id: str
    text: str
    voice_model_id: str
    channel_id: str
    settings: VoiceSettings
    def __init__(self, script_id: _Optional[str] = ..., text: _Optional[str] = ..., voice_model_id: _Optional[str] = ..., channel_id: _Optional[str] = ..., settings: _Optional[_Union[VoiceSettings, _Mapping]] = ...) -> None: ...

class SynthesizeVoiceResponse(_message.Message):
    __slots__ = ("audio_id", "audio_url", "duration_ms", "generation_cost")
    AUDIO_ID_FIELD_NUMBER: _ClassVar[int]
    AUDIO_URL_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    GENERATION_COST_FIELD_NUMBER: _ClassVar[int]
    audio_id: str
    audio_url: str
    duration_ms: int
    generation_cost: float
    def __init__(self, audio_id: _Optional[str] = ..., audio_url: _Optional[str] = ..., duration_ms: _Optional[int] = ..., generation_cost: _Optional[float] = ...) -> None: ...

class ListVoiceModelsRequest(_message.Message):
    __slots__ = ("provider", "language")
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    provider: str
    language: str
    def __init__(self, provider: _Optional[str] = ..., language: _Optional[str] = ...) -> None: ...

class ListVoiceModelsResponse(_message.Message):
    __slots__ = ("models",)
    MODELS_FIELD_NUMBER: _ClassVar[int]
    models: _containers.RepeatedCompositeFieldContainer[VoiceModel]
    def __init__(self, models: _Optional[_Iterable[_Union[VoiceModel, _Mapping]]] = ...) -> None: ...

class GetVoiceAudioRequest(_message.Message):
    __slots__ = ("audio_id",)
    AUDIO_ID_FIELD_NUMBER: _ClassVar[int]
    audio_id: str
    def __init__(self, audio_id: _Optional[str] = ...) -> None: ...

class GetVoiceAudioResponse(_message.Message):
    __slots__ = ("audio_data", "format", "sample_rate")
    AUDIO_DATA_FIELD_NUMBER: _ClassVar[int]
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_RATE_FIELD_NUMBER: _ClassVar[int]
    audio_data: bytes
    format: str
    sample_rate: int
    def __init__(self, audio_data: _Optional[bytes] = ..., format: _Optional[str] = ..., sample_rate: _Optional[int] = ...) -> None: ...

class VoiceModel(_message.Message):
    __slots__ = ("id", "name", "provider", "language", "gender", "styles", "cost_per_character")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    GENDER_FIELD_NUMBER: _ClassVar[int]
    STYLES_FIELD_NUMBER: _ClassVar[int]
    COST_PER_CHARACTER_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    provider: str
    language: str
    gender: str
    styles: _containers.RepeatedScalarFieldContainer[str]
    cost_per_character: float
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., provider: _Optional[str] = ..., language: _Optional[str] = ..., gender: _Optional[str] = ..., styles: _Optional[_Iterable[str]] = ..., cost_per_character: _Optional[float] = ...) -> None: ...

class VoiceSettings(_message.Message):
    __slots__ = ("speed", "pitch", "stability", "similarity_boost", "style")
    SPEED_FIELD_NUMBER: _ClassVar[int]
    PITCH_FIELD_NUMBER: _ClassVar[int]
    STABILITY_FIELD_NUMBER: _ClassVar[int]
    SIMILARITY_BOOST_FIELD_NUMBER: _ClassVar[int]
    STYLE_FIELD_NUMBER: _ClassVar[int]
    speed: float
    pitch: float
    stability: float
    similarity_boost: float
    style: str
    def __init__(self, speed: _Optional[float] = ..., pitch: _Optional[float] = ..., stability: _Optional[float] = ..., similarity_boost: _Optional[float] = ..., style: _Optional[str] = ...) -> None: ...
