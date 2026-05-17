# Architecture: Provider Pattern

## Purpose

Every external dependency — LLM, TTS, image, search, storage, secrets — is
fronted by an **abstract base class** with concrete implementations and a
single **registry** that resolves the active provider at call-time. This
lets us swap providers via env var, channel-level override, or **test mode**
without touching service code.

## Source files

- `src/providers/registry.py:1-171`
- `src/providers/chain.py` — fallback chain + DB-driven priority
- `src/providers/boot.py` — import-time registration of all providers
- `src/providers/invalidation.py` — cache invalidation on config change
- `src/providers/secrets.py` — env / Infisical backend

## Categories

```python
# src/providers/registry.py:11-26
_ENV_MAP = {
  "tts":            "TTS_PROVIDER",
  "llm":            "LLM_PROVIDER",
  "llm.research":   "LLM_RESEARCH_PROVIDER",
  "llm.script":     "LLM_SCRIPT_PROVIDER",
  "llm.factcheck":  "LLM_FACTCHECK_PROVIDER",
  "llm.qc":         "LLM_QC_PROVIDER",
  "llm.vision":     "LLM_VISION_PROVIDER",
  "llm.ideation":   "LLM_IDEATION_PROVIDER",
  "llm.hook":       "LLM_HOOK_PROVIDER",
  "llm.direction":  "LLM_DIRECTION_PROVIDER",
  "llm.emotion":    "LLM_EMOTION_PROVIDER",
  "search":         "SEARCH_PROVIDER",
  "image":          "IMAGE_PROVIDER",
  "storage":        "STORAGE_PROVIDER",
}
```

## Test-mode remap

In test mode the registry overrides expensive providers automatically:

```python
# src/providers/registry.py:30-45
_TEST_PROVIDER_MAP = {
  "tts":           "edge_tts",       # free Microsoft Edge TTS
  "llm":           "mock_llm",       # cached JSON + GPT-4o-mini fallback
  "llm.*":         "mock_llm",       # every llm.<task> too
  "search":        "mock_search",    # cache + Wikipedia
  "image":         "placeholder",    # Pillow-rendered
  # storage: NOT remapped — MinIO is free
}
```

The registry calls `is_test()` from `src/environment.py` on every `get()`
so a toggle in the dashboard flips the resolution **without restarting**
services (cache TTL = 5s).

## Resolution order

`ProviderRegistry.get(category, *, override=None, channel_id=None, content_mode=None)`:

1. **Explicit `override=`** (e.g. force a specific provider for one call).
2. **Test mode** → `_TEST_PROVIDER_MAP[category]`.
3. **DB-driven priority chain** (`resolve_chain` in `chain.py`) using
   `provider_credentials` table, scoped by `channel_id` and `content_mode`.
4. **Env var** (`_ENV_MAP[category]`).
5. Else raise `NoProviderConfigured` — surfaced in UI as a clear error.

Result is **cached per `(category, name, channel_id, content_mode)`** so
different channels with different overrides don’t poison each other.

## ABCs

Each category has a base class under `src/providers/<category>/base.py`,
e.g. `TTSProvider`:

```python
# src/providers/tts/base.py
class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(text, voice_id) -> bytes: ...
    @abstractmethod
    async def synthesize_with_params(
        text, voice_id, *, stability, similarity_boost, style, speed
    ) -> bytes: ...
    @abstractmethod
    def estimate_cost(text) -> float: ...
    @abstractmethod
    async def health_check() -> bool: ...
    @abstractmethod
    def provider_name() -> str: ...
    async def get_word_timestamps(...) -> list[dict] | None:  # optional
```

All provider implementations are registered at import time by
`src/providers/boot.py` so the registry is populated before any service
starts handling requests.

## Fallback chain (`chain.py`)

The `FallbackProvider` wraps an ordered list of providers and tries each in
turn on failure. The priority list comes from the `provider_credentials`
table so ops can re-order without redeploying. Special sentinel
`EMPTY_CHAIN` distinguishes “DB reachable but no enabled creds” from “DB
unreachable, fall back to env”.

## Cache invalidation

`src/providers/invalidation.py` exposes `invalidate_category(category)` and
is called by the dashboard `/providers` endpoints whenever credentials are
added, edited or disabled. It clears `ProviderRegistry._instances` so the
next `get()` re-reads the DB chain.

## Related pages

- [[Providers-LLM]] · [[Providers-TTS]] · [[Providers-Image]]
- [[Providers-Search]] · [[Providers-Storage]] · [[Providers-Secrets]]
- [[BFF-Providers-And-Experiments]]
- [[Test-vs-Production-Mode]]
