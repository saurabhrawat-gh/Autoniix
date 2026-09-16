# Skill: Provider Pattern

**Use when:** Creating or modifying providers (LLM, TTS, Image, Search, Storage), or working with ProviderRegistry.

**When NOT to use:** General FastAPI endpoint work that doesn't involve external API providers.

---

## Architecture

```
ABC (base.py)  →  Concrete Provider  →  Registry (registry.py)  →  Config (.env)
     ↑                  ↑                      ↑
  Defines interface   Implements it        Factory + cache
```

## How to Add a New Provider

1. **Create the provider class** in `src/providers/<category>/`

   ```python
   from src.providers.<category>.base import <Category>Provider

   class MyProvider(<Category>Provider):
       async def complete(self, request): ...  # or synthesize(), generate(), etc.
       def estimate_cost(self, ...): ...
       async def health_check(self) -> bool: ...
       def provider_name(self) -> str: return "my_provider"
       def default_model(self) -> str: ...  # LLM only
   ```

2. **Register it** at the bottom of the file:

   ```python
   ProviderRegistry.register("llm", "my_provider", MyProvider)
   ```

3. **Add env var mapping** in `registry.py` `_ENV_MAP` (if new category) or just set the env var.

4. **Add test mode remap** in `registry.py` `_TEST_PROVIDER_MAP` if the provider is expensive.

5. **Add config** in `src/config.py` if new API keys needed.

6. **Update `.env.example`** with the new env vars.

## Provider Categories

| Category      | ABC             | Env Var                | Providers                        |
| ------------- | --------------- | ---------------------- | -------------------------------- |
| llm           | LLMProvider     | LLM_PROVIDER           | openai, claude, gemini, mock_llm |
| llm.script    | LLMProvider     | LLM_SCRIPT_PROVIDER    | claude (default)                 |
| llm.research  | LLMProvider     | LLM_RESEARCH_PROVIDER  | gemini (default)                 |
| llm.factcheck | LLMProvider     | LLM_FACTCHECK_PROVIDER | openai                           |
| llm.qc        | LLMProvider     | LLM_QC_PROVIDER        | gemini                           |
| llm.vision    | LLMProvider     | LLM_VISION_PROVIDER    | openai                           |
| tts           | TTSProvider     | TTS_PROVIDER           | fishaudio, elevenlabs, edge_tts  |
| image         | ImageProvider   | IMAGE_PROVIDER         | dalle, placeholder               |
| search        | SearchProvider  | SEARCH_PROVIDER        | serpapi, mock_search             |
| storage       | StorageProvider | STORAGE_PROVIDER       | minio                            |

## Usage in Services

```python
from src.providers.registry import ProviderRegistry

llm = ProviderRegistry.get("llm.script")
result = await llm.complete(LLMRequest(messages=[...], max_tokens=4096))
```

## Test Mode

When `ENVIRONMENT_MODE=test`, `ProviderRegistry.get()` automatically remaps to free providers via `_TEST_PROVIDER_MAP`. No code changes needed.
