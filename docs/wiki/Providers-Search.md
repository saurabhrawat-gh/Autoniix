# Providers: Search

## Purpose

Web search for the research service — used to ground LLM topic synthesis
and fact-checking with current sources.

## Source

- `src/providers/search/base.py`
- `src/providers/search/serpapi_provider.py`
- `src/providers/search/mock_search_provider.py` (test mode)

## ABC

```python
class SearchProvider(ABC):
    async def search(query, *, n=10, date_range=None) -> list[SearchResult]: ...
    def estimate_cost(n) -> float: ...
    async def health_check() -> bool: ...
    def provider_name() -> str: ...
```

## SerpAPI (production)

Cost ~$0.005 per query. Returns organic results, news, and people-also-ask
for the topic’s long-tail.

## Mock (test mode)

First hits a local JSON cache keyed by query hash. On miss, falls through
to the Wikipedia API (free) and stores the result for reproducibility.

## Related pages

- [[Service-Research]] · [[Architecture-Provider-Pattern]]
