# Providers: LLM

## Purpose

Unified abstraction over all LLM vendors. The router lets each task choose
the best model for the job (research, script, fact-check, QC, vision,
ideation, hook, direction, emotion) and swap providers without changing
calling code.

## Source

- `src/providers/llm/base.py` — ABC
- `src/providers/llm/openai_provider.py`
- `src/providers/llm/openai_vision_provider.py`
- `src/providers/llm/claude_provider.py`
- `src/providers/llm/gemini_provider.py`
- `src/providers/llm/glm_provider.py`
- `src/providers/llm/kimi_provider.py`
- `src/providers/llm/mock_provider.py`
- `src/llm/router.py` — task→provider routing

## ABC

```python
class LLMProvider(ABC):
    @abstractmethod
    async def complete(messages, *, json_mode=False, temperature=0.2,
                       max_tokens=None, model_override=None) -> dict: ...
    @abstractmethod
    def estimate_cost(prompt_tokens, completion_tokens) -> float: ...
    @abstractmethod
    async def health_check() -> bool: ...
    @abstractmethod
    def provider_name() -> str: ...
```

## Default routing (`src/config.py:55-68`)

| Task | Default | Why |
|---|---|---|
| `llm.research` | gemini | cost-optimised, structured JSON |
| `llm.script` | claude | best creative writing |
| `llm.factcheck` | openai (gpt-4o, t=0.1) | most reliable |
| `llm.qc` | gemini | 94% cheaper |
| `llm.vision` | openai (gpt-4o vision) | can “see” images |
| `llm.ideation` | openai | gpt-4o-mini, cheap |
| `llm.hook` | openai | gpt-4o-mini |
| `llm.direction` | openai (gpt-4o) | complex JSON |
| `llm.emotion` | openai | gpt-4o-mini |

## Models / cost

| Provider | Default model |
|---|---|
| openai | `gpt-4o-mini` (overridable) |
| claude | `claude-sonnet-4-20250514` |
| gemini | `gemini-2.5-flash` |
| glm | GLM-4 family |
| kimi | Moonshot K2 |

## Test-mode mock

`mock_provider.py` is a smart mock: first tries to hit a cached JSON file
for the prompt fingerprint; if miss, falls through to a cheap GPT-4o-mini
call and caches the result. This gives reproducible test runs while still
allowing new prompts to work.

## Related pages

- [[Architecture-Provider-Pattern]] · [[BFF-Providers-And-Experiments]]
- [[Test-vs-Production-Mode]]
