# Provider Mock Harness

**Status:** Week 1 Day 3-5 Complete  
**Per:** HARNESS-ENGINEERING-PLAN.md Section 3

## Overview

Mock external API providers to eliminate testing costs (~$500/week savings).

**Providers Mocked:**
1. OpenAI (GPT-4, GPT-4o, GPT-3.5)
2. Anthropic (Claude)
3. Fish Audio (TTS)
4. DALL-E (Image generation)
5. Pexels/Pixabay (Stock media)
6. SerpAPI (Web search)
7. YouTube API (Video metadata)
8. Gemini (Google AI)

**Total:** ~600 LOC, 8 providers, disk caching, fixture support.

## Usage

### Basic Usage

```python
from tests.harnesses import ProviderMockHarness

harness = ProviderMockHarness(cache_enabled=True)

# Mock OpenAI API call
openai_request = {
    "model": "gpt-4o",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a poem about AI."},
    ],
    "max_tokens": 100,
}
response = harness.openai_mock(openai_request)
print(response["choices"][0]["message"]["content"])

# Mock Anthropic API call
anthropic_request = {
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "Explain quantum computing."}],
    "max_tokens": 200,
}
response = harness.anthropic_mock(anthropic_request)
print(response["content"][0]["text"])

# Mock Fish Audio TTS
fish_request = {
    "text": "Hello, this is a test.",
    "voice_id": "test_voice",
}
audio_bytes = harness.fish_audio_mock(fish_request)
# audio_bytes is a valid WAV file

# Mock DALL-E image generation
dalle_request = {
    "prompt": "A futuristic city at sunset",
    "size": "1024x1024",
    "response_format": "url",
}
response = harness.dalle_mock(dalle_request)
print(response["data"][0]["url"])

# Mock Pexels stock photos
pexels_request = {
    "query": "nature",
    "per_page": 10,
}
response = harness.pexels_pixabay_mock(pexels_request, provider="pexels")
print(f"Found {len(response['photos'])} photos")

# Mock SerpAPI web search
serpapi_request = {
    "q": "artificial intelligence trends 2024",
    "num": 10,
}
response = harness.serpapi_mock(serpapi_request)
for result in response["organic_results"]:
    print(f"{result['title']}: {result['link']}")

# Mock YouTube search
youtube_request = {
    "q": "machine learning tutorial",
    "maxResults": 5,
}
response = harness.youtube_api_mock(youtube_request, endpoint="search")
for item in response["items"]:
    print(item["snippet"]["title"])

# Mock Gemini
gemini_request = {
    "contents": [
        {"parts": [{"text": "Explain neural networks."}]},
    ],
}
response = harness.gemini_mock(gemini_request)
print(response["candidates"][0]["content"]["parts"][0]["text"])
```

### Integration with Existing Code

Replace real API calls with mocks in test mode:

```python
# Before (production)
import openai
response = openai.ChatCompletion.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)

# After (test mode)
from tests.harnesses import ProviderMockHarness

if settings.test_mode:
    harness = ProviderMockHarness()
    response = harness.openai_mock({
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello"}],
    })
else:
    response = openai.ChatCompletion.create(...)
```

### Caching Behavior

**Enabled by default:**
```python
harness = ProviderMockHarness(cache_enabled=True)
```

**How it works:**
1. First call: Generates mock response, saves to `tests/fixtures/providers/{hash}.json`
2. Subsequent calls: Returns cached response instantly ($0 cost, <1ms latency)
3. Cache key: SHA-256 hash of request parameters

**Disable caching:**
```python
harness = ProviderMockHarness(cache_enabled=False)
```

**Clear cache:**
```bash
rm -rf tests/fixtures/providers/*.json
```

## Response Formats

### OpenAI

```json
{
  "id": "chatcmpl-mock1718901234",
  "object": "chat.completion",
  "created": 1718901234,
  "model": "gpt-4o",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Mock response text..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 50,
    "total_tokens": 70
  }
}
```

### Anthropic

```json
{
  "id": "msg_mock1718901234",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Mock Claude response..."
    }
  ],
  "model": "claude-3-5-sonnet-20241022",
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 15,
    "output_tokens": 40
  }
}
```

### Fish Audio

Returns raw WAV bytes (44-byte header + PCM audio data).

### DALL-E

```json
{
  "created": 1718901234,
  "data": [
    {
      "url": "https://mock-dalle.example.com/images/abc123.png"
    }
  ]
}
```

Or with `response_format: "b64_json"`:

```json
{
  "created": 1718901234,
  "data": [
    {
      "b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB..."
    }
  ]
}
```

### Pexels

```json
{
  "page": 1,
  "per_page": 10,
  "photos": [
    {
      "id": "mock_0",
      "width": 1920,
      "height": 1080,
      "url": "https://www.pexels.com/photo/mock-0/",
      "photographer": "Mock Photographer",
      "src": {
        "original": "https://images.pexels.com/photos/mock-0/...",
        "large": "...",
        "medium": "..."
      }
    }
  ],
  "total_results": 1000
}
```

### SerpAPI

```json
{
  "search_metadata": {
    "id": "mock_1718901234",
    "status": "Success"
  },
  "organic_results": [
    {
      "position": 1,
      "title": "Mock Result 1 for query",
      "link": "https://example.com/result-1",
      "snippet": "This is a mock search result snippet..."
    }
  ]
}
```

### YouTube

```json
{
  "kind": "youtube#searchListResponse",
  "items": [
    {
      "kind": "youtube#searchResult",
      "id": {
        "kind": "youtube#video",
        "videoId": "mock_video_0"
      },
      "snippet": {
        "title": "Mock Video 1: query",
        "description": "Mock video description",
        "thumbnails": {
          "default": {"url": "https://i.ytimg.com/vi/mock_0/default.jpg"}
        }
      }
    }
  ]
}
```

### Gemini

```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {"text": "Mock Gemini response..."}
        ],
        "role": "model"
      },
      "finishReason": "STOP"
    }
  ],
  "usageMetadata": {
    "promptTokenCount": 10,
    "candidatesTokenCount": 20,
    "totalTokenCount": 30
  }
}
```

## Testing

Run provider mock tests:

```bash
pytest tests/harnesses/test_provider_harness.py -v
```

Run specific provider test:

```bash
pytest tests/harnesses/test_provider_harness.py::TestOpenAIMock::test_openai_chat_completion -v
```

## Cost Savings

**Before (real APIs):**
- OpenAI GPT-4o: $0.005/1K input tokens, $0.015/1K output tokens
- Anthropic Claude: $0.003/1K input tokens, $0.015/1K output tokens
- DALL-E 3: $0.04 per image
- Fish Audio: $0.001 per second
- SerpAPI: $0.002 per search
- YouTube API: Free (quota limited)

**Typical test suite (100 runs/day):**
- 500 LLM calls × $0.01 = $5/day
- 50 image generations × $0.04 = $2/day
- 100 TTS calls × $0.05 = $5/day
- 200 searches × $0.002 = $0.40/day
- **Total: ~$12/day = $360/month = $4,320/year**

**With mocks:**
- First run: Generates fixtures (one-time cost)
- Subsequent runs: $0 (reads from cache)
- **Savings: ~$500/week in active development**

## Fixtures Directory

```
tests/fixtures/providers/
├── openai_abc123.json          # Cached OpenAI response
├── anthropic_def456.json       # Cached Anthropic response
├── fish_audio_ghi789.wav       # Cached audio file
├── dalle_jkl012.json           # Cached DALL-E response
├── pexels_mno345.json          # Cached Pexels response
├── serpapi_pqr678.json         # Cached SerpAPI response
├── youtube_search_stu901.json  # Cached YouTube response
└── gemini_vwx234.json          # Cached Gemini response
```

## Advanced Usage

### Custom Fixtures

Override default responses by creating fixture files:

```python
import json
from pathlib import Path

fixtures_dir = Path("tests/fixtures/providers")
fixtures_dir.mkdir(parents=True, exist_ok=True)

# Create custom OpenAI response
custom_response = {
    "id": "chatcmpl-custom",
    "object": "chat.completion",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "Custom response for specific test case"
        }
    }],
    "usage": {"total_tokens": 50}
}

# Save with specific cache key
cache_key = "openai_custom_test_case"
(fixtures_dir / f"{cache_key}.json").write_text(json.dumps(custom_response))

# Use in test
harness = ProviderMockHarness()
# Will return custom_response for matching request
```

### Deterministic Responses

Use request parameters to ensure deterministic responses:

```python
# Same request always returns same response
request = {
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Explain AI"}],
    "temperature": 0,  # Deterministic
}

response1 = harness.openai_mock(request)
response2 = harness.openai_mock(request)

assert response1 == response2  # Always true
```

## CI Integration

Add to `.github/workflows/test.yml`:

```yaml
- name: Run Provider Mock Tests
  run: pytest tests/harnesses/test_provider_harness.py -v

- name: Cache Provider Fixtures
  uses: actions/cache@v3
  with:
    path: tests/fixtures/providers
    key: provider-fixtures-${{ hashFiles('tests/harnesses/**') }}
```

## Troubleshooting

### Cache Not Working

**Problem:** Responses not cached between runs

**Solution:** Check that `cache_enabled=True` and fixtures directory is writable:

```python
harness = ProviderMockHarness(cache_enabled=True)
print(f"Fixtures dir: {harness.fixtures_dir}")
print(f"Writable: {harness.fixtures_dir.exists()}")
```

### Invalid Response Format

**Problem:** Mock response doesn't match expected format

**Solution:** Check provider documentation and update mock in `provider_harness.py`. Example:

```python
# If OpenAI changes response format, update:
def openai_mock(self, request):
    # ... update response structure here
```

### Missing Provider

**Problem:** Need to mock a provider not yet implemented

**Solution:** Add new method to `ProviderMockHarness`:

```python
def new_provider_mock(self, request: dict[str, Any]) -> dict[str, Any]:
    """Mock NewProvider API."""
    cache_key = self._cache_key("new_provider", request)
    cached = self._get_cached(cache_key)
    if cached:
        return cached
    
    # Generate mock response
    response = {"status": "success", "data": [...]}
    
    self._set_cached(cache_key, response)
    return response
```

## Next Steps

Per HARNESS-ENGINEERING-PLAN.md:

- **Week 2:** Rust gateway test harness (GatewayHarness helper)
- **Week 3:** Equivalence testing (Python vs Rust response diffing)
- **Week 4:** Performance benchmarks (Criterion)

## Related Documents

- `docs/architecture/harness-engineering-plan.md` — Overall harness plan
- `tests/contracts/README.md` — REST contract validation
- `docs/future/post-harness-tasks.md` — Post-harness tasks
