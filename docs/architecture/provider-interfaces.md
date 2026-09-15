# Provider Interfaces & Abstraction Layer

> Swap any external provider (TTS, LLM, search, image, storage) by changing one env var and implementing one class.

---

## Design Pattern

```
┌────────────────────────┐     ┌──────────────────────────────┐
│ Service (e.g., Voice)  │────▶│ ProviderRegistry.get("tts")  │
│ Calls provider.speak() │     └──────────┬───────────────────┘
└────────────────────────┘                │
                                          │ Reads config: TTS_PROVIDER=fish_audio
                                          │
                              ┌───────────▼──────────────┐
                              │   TTSProvider (ABC)      │
                              │   .synthesize()          │
                              │   .estimate_cost()       │
                              │   .health_check()        │
                              ├──────────────────────────┤
                              │ FishAudioTTS             │
                              │ ElevenLabsTTS            │
                              │ GoogleTTS                │
                              └──────────────────────────┘
```

**To swap Fish Audio → ElevenLabs:**

1. Set `TTS_PROVIDER=elevenlabs` in `.env`
2. Set `ELEVENLABS_API_KEY=sk_...` in `.env`
3. Restart voice service
4. Done. No code changes.

---

## Provider Registry

```python
# lib/providers/registry.py
from __future__ import annotations
import os
from typing import TypeVar, Type

T = TypeVar("T")

class ProviderRegistry:
    """Config-driven provider factory. Reads provider name from env vars."""

    _registries: dict[str, dict[str, Type]] = {}

    @classmethod
    def register(cls, category: str, name: str, provider_class: Type):
        if category not in cls._registries:
            cls._registries[category] = {}
        cls._registries[category][name] = provider_class

    @classmethod
    def get(cls, category: str, override: str | None = None) -> object:
        env_map = {
            "tts": "TTS_PROVIDER",
            "llm": "LLM_PROVIDER",
            "llm.research": "LLM_RESEARCH_PROVIDER",
            "llm.script": "LLM_SCRIPT_PROVIDER",
            "llm.factcheck": "LLM_FACTCHECK_PROVIDER",
            "llm.qc": "LLM_QC_PROVIDER",
            "search": "SEARCH_PROVIDER",
            "image": "IMAGE_PROVIDER",
            "storage": "STORAGE_PROVIDER",
        }

        name = override or os.getenv(env_map.get(category, ""), "")
        if not name:
            raise ValueError(f"No provider configured for category '{category}'")

        registry = cls._registries.get(category, {})
        provider_class = registry.get(name)
        if not provider_class:
            available = list(registry.keys())
            raise ValueError(f"Unknown {category} provider '{name}'. Available: {available}")

        return provider_class()

    @classmethod
    def list_providers(cls, category: str) -> list[str]:
        return list(cls._registries.get(category, {}).keys())
```

---

## Abstract Base Classes

### TTSProvider

```python
# lib/providers/tts/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TTSRequest:
    text: str
    voice_id: str
    emotion: str | None = None
    emphasis_words: list[str] | None = None
    target_wpm: int = 150
    format: str = "mp3"
    bitrate: int = 128


@dataclass
class TTSResult:
    audio_bytes: bytes
    duration_s: float
    word_count: int
    bytes_charged: int
    cost_usd: float
    provider: str
    cache_hit: bool = False


class TTSProvider(ABC):
    """Abstract base for all TTS providers."""

    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Generate speech audio from text."""
        ...

    @abstractmethod
    def estimate_cost(self, text: str) -> float:
        """Estimate cost in USD for synthesizing this text."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider API is reachable."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier string."""
        ...
```

### LLMProvider

```python
# lib/providers/llm/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMRequest:
    messages: list[dict]              # [{"role": "system", "content": "..."}, ...]
    model: str | None = None          # Override default model
    temperature: float = 0.7
    max_tokens: int = 4000
    response_format: str = "text"     # "text" | "json"
    json_schema: dict | None = None   # For structured output


@dataclass
class LLMResult:
    content: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    provider: str
    latency_ms: int = 0
    finish_reason: str = "stop"


class LLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResult:
        """Generate a completion."""
        ...

    @abstractmethod
    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str | None = None) -> float:
        """Estimate cost in USD for this request."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    def default_model(self) -> str:
        """Return the default model for this provider."""
        ...

    @abstractmethod
    def supported_models(self) -> list[str]:
        """List all models this provider supports."""
        ...
```

### SearchProvider

```python
# lib/providers/search/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchRequest:
    query: str
    num_results: int = 10
    search_type: str = "web"    # "web" | "video" | "news"
    domain_filter: str | None = None


@dataclass
class SearchResult:
    results: list[dict]         # [{title, url, snippet, ...}]
    total_results: int
    cost_usd: float
    provider: str
    cache_hit: bool = False


class SearchProvider(ABC):

    @abstractmethod
    async def search(self, request: SearchRequest) -> SearchResult:
        ...

    @abstractmethod
    def estimate_cost(self, num_queries: int) -> float:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...
```

### ImageProvider

```python
# lib/providers/image/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ImageRequest:
    prompt: str
    size: str = "1024x1024"     # "1024x1024" | "1792x1024" | "1024x1792"
    quality: str = "standard"   # "standard" | "hd"
    style: str = "vivid"        # "vivid" | "natural"
    n: int = 1


@dataclass
class ImageResult:
    images: list[dict]          # [{url, revised_prompt}]
    cost_usd: float
    provider: str


class ImageProvider(ABC):

    @abstractmethod
    async def generate(self, request: ImageRequest) -> ImageResult:
        ...

    @abstractmethod
    def estimate_cost(self, n: int, quality: str, size: str) -> float:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...
```

### StorageProvider

```python
# lib/providers/storage/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StorageUpload:
    key: str                    # e.g., "audio/BS001/VID_.../scene_s1.mp3"
    data: bytes
    content_type: str = "application/octet-stream"
    metadata: dict | None = None


@dataclass
class StorageResult:
    url: str                    # Public or signed URL
    key: str
    size_bytes: int
    provider: str


class StorageProvider(ABC):

    @abstractmethod
    async def upload(self, upload: StorageUpload) -> StorageResult:
        ...

    @abstractmethod
    async def download(self, key: str) -> bytes:
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...

    @abstractmethod
    async def get_signed_url(self, key: str, expires_in: int = 3600) -> str:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...
```

---

## Concrete Implementations

### FishAudioTTS

```python
# lib/providers/tts/fish_audio.py
import os
import httpx
from lib.providers.tts.base import TTSProvider, TTSRequest, TTSResult
from lib.providers.registry import ProviderRegistry


class FishAudioTTS(TTSProvider):
    BASE_URL = "https://api.fish.audio/v1/tts"
    COST_PER_BYTE = 15.0 / 1_000_000  # $15 per 1M UTF-8 bytes

    def __init__(self):
        self.api_key = os.getenv("FISH_AUDIO_API_KEY")
        if not self.api_key:
            raise ValueError("FISH_AUDIO_API_KEY not set")

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "text": request.text,
                    "reference_id": request.voice_id,
                    "format": request.format,
                    "bitrate": request.bitrate,
                },
            )
            response.raise_for_status()
            audio_bytes = response.content

        text_bytes = len(request.text.encode("utf-8"))
        cost = text_bytes * self.COST_PER_BYTE
        duration_s = len(audio_bytes) / (request.bitrate * 1000 / 8)

        return TTSResult(
            audio_bytes=audio_bytes,
            duration_s=duration_s,
            word_count=len(request.text.split()),
            bytes_charged=text_bytes,
            cost_usd=cost,
            provider="fish_audio",
        )

    def estimate_cost(self, text: str) -> float:
        return len(text.encode("utf-8")) * self.COST_PER_BYTE

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get("https://api.fish.audio/", headers={"Authorization": f"Bearer {self.api_key}"})
                return resp.status_code < 500
        except Exception:
            return False

    def provider_name(self) -> str:
        return "fish_audio"


# Auto-register
ProviderRegistry.register("tts", "fish_audio", FishAudioTTS)
```

### ElevenLabsTTS (Swap-in Example)

```python
# lib/providers/tts/elevenlabs.py
import os
import httpx
from lib.providers.tts.base import TTSProvider, TTSRequest, TTSResult
from lib.providers.registry import ProviderRegistry


class ElevenLabsTTS(TTSProvider):
    BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"
    COST_PER_CHAR = 0.30 / 1000  # Pro plan: ~$0.30/1K chars

    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY not set")

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/{request.voice_id}",
                headers={"xi-api-key": self.api_key},
                json={
                    "text": request.text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
            )
            response.raise_for_status()
            audio_bytes = response.content

        chars = len(request.text)
        cost = chars * self.COST_PER_CHAR

        return TTSResult(
            audio_bytes=audio_bytes,
            duration_s=len(audio_bytes) / (128 * 1000 / 8),
            word_count=len(request.text.split()),
            bytes_charged=chars,
            cost_usd=cost,
            provider="elevenlabs",
        )

    def estimate_cost(self, text: str) -> float:
        return len(text) * self.COST_PER_CHAR

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": self.api_key})
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "elevenlabs"


ProviderRegistry.register("tts", "elevenlabs", ElevenLabsTTS)
```

### OpenAI LLM

```python
# lib/providers/llm/openai_provider.py
import os
import time
import httpx
from lib.providers.llm.base import LLMProvider, LLMRequest, LLMResult
from lib.providers.registry import ProviderRegistry


OPENAI_PRICING = {
    "gpt-4o":       {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-mini":  {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
}


class OpenAILLM(LLMProvider):
    BASE_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

    async def complete(self, request: LLMRequest) -> LLMResult:
        model = request.model or self.default_model()
        start = time.monotonic()

        body = {
            "model": model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format == "json":
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        usage = data["usage"]
        pricing = OPENAI_PRICING.get(model, OPENAI_PRICING["gpt-4o"])
        cost = usage["prompt_tokens"] * pricing["input"] + usage["completion_tokens"] * pricing["output"]

        return LLMResult(
            content=data["choices"][0]["message"]["content"],
            model=model,
            tokens_in=usage["prompt_tokens"],
            tokens_out=usage["completion_tokens"],
            cost_usd=cost,
            provider="openai",
            latency_ms=int((time.monotonic() - start) * 1000),
            finish_reason=data["choices"][0]["finish_reason"],
        )

    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str | None = None) -> float:
        model = model or self.default_model()
        pricing = OPENAI_PRICING.get(model, OPENAI_PRICING["gpt-4o"])
        return tokens_in * pricing["input"] + tokens_out * pricing["output"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def provider_name(self) -> str:
        return "openai"

    def default_model(self) -> str:
        return "gpt-4o"

    def supported_models(self) -> list[str]:
        return list(OPENAI_PRICING.keys())


ProviderRegistry.register("llm", "openai", OpenAILLM)
ProviderRegistry.register("llm.factcheck", "openai", OpenAILLM)
ProviderRegistry.register("llm.qc", "openai", OpenAILLM)
```

### MinIO Storage

```python
# lib/providers/storage/minio_provider.py
import os
from minio import Minio
from lib.providers.storage.base import StorageProvider, StorageUpload, StorageResult
from lib.providers.registry import ProviderRegistry
from io import BytesIO


class MinIOStorage(StorageProvider):

    def __init__(self):
        self.client = Minio(
            os.getenv("S3_ENDPOINT", "minio:9000").replace("http://", ""),
            access_key=os.getenv("S3_ACCESS_KEY"),
            secret_key=os.getenv("S3_SECRET_KEY"),
            secure=os.getenv("S3_ENDPOINT", "").startswith("https"),
        )
        self.bucket = os.getenv("S3_BUCKET", "yt-automation")
        self.public_base = os.getenv("S3_PUBLIC_BASE_URL", "")

    async def upload(self, upload: StorageUpload) -> StorageResult:
        data = BytesIO(upload.data)
        self.client.put_object(
            self.bucket, upload.key, data, len(upload.data),
            content_type=upload.content_type,
            metadata=upload.metadata,
        )
        url = f"{self.public_base}/{upload.key}" if self.public_base else f"s3://{self.bucket}/{upload.key}"
        return StorageResult(url=url, key=upload.key, size_bytes=len(upload.data), provider="minio")

    async def download(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        return response.read()

    async def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> None:
        self.client.remove_object(self.bucket, key)

    async def get_signed_url(self, key: str, expires_in: int = 3600) -> str:
        from datetime import timedelta
        return self.client.presigned_get_object(self.bucket, key, expires=timedelta(seconds=expires_in))

    async def health_check(self) -> bool:
        try:
            self.client.bucket_exists(self.bucket)
            return True
        except Exception:
            return False

    def provider_name(self) -> str:
        return "minio"


ProviderRegistry.register("storage", "minio", MinIOStorage)
```

---

## Configuration

### Environment Variables

```bash
# Default providers (change to swap)
TTS_PROVIDER=fish_audio           # Options: fish_audio, elevenlabs, google_tts
LLM_PROVIDER=openai               # Default LLM; overridden by task-specific vars
LLM_RESEARCH_PROVIDER=google      # Gemini Flash for research
LLM_SCRIPT_PROVIDER=anthropic     # Claude Sonnet for script writing
LLM_FACTCHECK_PROVIDER=openai     # GPT-4o for fact-checking
LLM_QC_PROVIDER=google            # Gemini Flash for QC scoring
SEARCH_PROVIDER=serpapi            # Options: serpapi, google_custom
IMAGE_PROVIDER=dalle               # Options: dalle, stock_only
STORAGE_PROVIDER=minio             # Options: minio, s3, gcs
```

### Using a Provider in a Service

```python
# services/voice/main.py
from lib.providers.registry import ProviderRegistry

# Import implementations to trigger auto-registration
import lib.providers.tts.fish_audio
import lib.providers.tts.elevenlabs

async def generate_voice(text: str, voice_id: str) -> TTSResult:
    tts = ProviderRegistry.get("tts")  # Reads TTS_PROVIDER env var

    # Pre-flight cost check
    estimated = tts.estimate_cost(text)
    if estimated > budget_remaining:
        raise BudgetExceededError(...)

    result = await tts.synthesize(TTSRequest(text=text, voice_id=voice_id))

    # Log cost
    await log_api_usage(provider=result.provider, cost_usd=result.cost_usd, ...)

    return result
```

---

## How to Add a New Provider

### Example: Adding Google Cloud TTS

1. **Create implementation file:**

```python
# lib/providers/tts/google_tts.py
import os
from google.cloud import texttospeech
from lib.providers.tts.base import TTSProvider, TTSRequest, TTSResult
from lib.providers.registry import ProviderRegistry


class GoogleTTS(TTSProvider):
    COST_PER_CHAR = 0.000016  # $16 per 1M chars (Standard)

    def __init__(self):
        # Uses GOOGLE_APPLICATION_CREDENTIALS env var
        self.client = texttospeech.TextToSpeechAsyncClient()

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        input_text = texttospeech.SynthesisInput(text=request.text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name=request.voice_id,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
        )
        response = await self.client.synthesize_speech(
            input=input_text, voice=voice, audio_config=audio_config,
        )
        chars = len(request.text)
        return TTSResult(
            audio_bytes=response.audio_content,
            duration_s=len(response.audio_content) / (128 * 1000 / 8),
            word_count=len(request.text.split()),
            bytes_charged=chars,
            cost_usd=chars * self.COST_PER_CHAR,
            provider="google_tts",
        )

    def estimate_cost(self, text: str) -> float:
        return len(text) * self.COST_PER_CHAR

    async def health_check(self) -> bool:
        try:
            await self.client.list_voices(language_code="en-US")
            return True
        except Exception:
            return False

    def provider_name(self) -> str:
        return "google_tts"


ProviderRegistry.register("tts", "google_tts", GoogleTTS)
```

2. **Import in the service entrypoint:**

```python
# services/voice/main.py
import lib.providers.tts.google_tts  # Add this line
```

3. **Set env var:**

```bash
TTS_PROVIDER=google_tts
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

4. **Restart voice service.** Done.

---

## Fallback Chains

Configure fallback providers for resilience:

```python
# lib/providers/fallback.py
from lib.providers.registry import ProviderRegistry

FALLBACK_CHAINS = {
    "tts": ["fish_audio", "google_tts"],
    "llm": ["openai", "anthropic", "google"],
    "search": ["serpapi", "google_custom"],
    "image": ["dalle", "stock_only"],
    "storage": ["minio"],  # No fallback for storage
}


async def call_with_fallback(category: str, method: str, *args, **kwargs):
    """Try primary provider, then fallbacks on failure."""
    chain = FALLBACK_CHAINS.get(category, [])
    last_error = None

    for provider_name in chain:
        try:
            provider = ProviderRegistry.get(category, override=provider_name)
            if not await provider.health_check():
                continue
            result = await getattr(provider, method)(*args, **kwargs)
            return result
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"All {category} providers failed. Last error: {last_error}")
```

Usage:

```python
result = await call_with_fallback("tts", "synthesize", tts_request)
```
