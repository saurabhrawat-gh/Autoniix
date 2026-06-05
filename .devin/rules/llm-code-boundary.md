# LLM/Code Boundary

## Use LLM For
- Classification of unstructured input (sentiment, intent, category)
- Drafting, summarization, extraction from natural language
- Judgment calls where context and nuance matter (script critique, quality scoring)
- Generating options or tradeoffs for human review
- Creative generation (script writing, hook ideation, thumbnail concepts)

## Use Plain Code For
- Routing — `if status == 429: retry` — the model doesn't decide this
- Fetching, filtering, sorting, paginating — deterministic answers
- Persisting, dispatching, scheduling — pure side effects
- Validation against known schemas — use Pydantic, not a prompt
- Retry logic — RetryPolicy with backoff, not LLM judgment
- Budget checks — arithmetic comparison, not AI deliberation

## Provider Pattern Rules
- All external AI APIs go through the provider abstraction (ABC + Registry).
- Never call OpenAI/Anthropic/Fish Audio directly — use `ProviderRegistry.get("llm")` etc.
- Config-driven: provider selection via env vars (`LLM_PROVIDER`, `TTS_PROVIDER`).
- Test mode auto-remaps to free providers via `_TEST_PROVIDER_MAP`.
- Each provider implements: `complete()`/`synthesize()`, `estimate_cost()`, `health_check()`, `provider_name()`.
- New providers: create class inheriting ABC, register via `ProviderRegistry.register()`, add to `_ENV_MAP`.

## Intelligence Layer Pattern
- Local-first computation: spaCy, textstat, NLTK, sklearn, numpy.
- LLM is fallback only, never the first choice for deterministic work.
- Every intelligence module has a cost of $0.00 — no API calls.
- Self-learning uses GBM + Thompson Sampling (sklearn), not LLM.
- Feedback endpoints: `/feedback`, `/train`, `/drift` on each service.

## Cost Discipline
- Test mode: ~$0.00/video (mock providers, Edge TTS, Pillow images).
- Production mode: ~$0.12-0.35/video (real LLM, Fish Audio, DALL-E).
- Budget guard on every LLM call. Never skip the budget check.
- Log all costs via structlog: `logger.info("provider.completed", cost_usd=...)`.
