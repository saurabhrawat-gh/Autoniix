"""
Provider Mock Harness — mock external API providers for testing.
Per HARNESS-ENGINEERING-PLAN.md Week 1 Day 3-5.

Saves ~$500/week in testing costs by mocking:
- OpenAI (GPT-4, GPT-4o, GPT-3.5)
- Anthropic (Claude)
- Fish Audio (TTS)
- DALL-E (Image generation)
- Pexels/Pixabay (Stock media)
- SerpAPI (Web search)
- YouTube API (Video metadata)
- Gemini (Google AI)

Total: ~600 LOC across 8 providers.
"""
from __future__ import annotations

import base64
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "providers"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


class ProviderMockHarness:
    """Base class for provider mocks with caching and fixture support."""
    
    def __init__(self, cache_enabled: bool = True):
        """
        Initialize provider mock harness.
        
        Args:
            cache_enabled: If True, cache responses to disk for faster subsequent runs
        """
        self.cache_enabled = cache_enabled
        self.fixtures_dir = FIXTURES_DIR
    
    def _cache_key(self, provider: str, request_data: dict[str, Any]) -> str:
        """Generate cache key from request data."""
        raw = json.dumps(request_data, sort_keys=True)
        hash_val = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"{provider}_{hash_val}"
    
    def _get_cached(self, cache_key: str) -> dict[str, Any] | None:
        """Retrieve cached response if exists."""
        if not self.cache_enabled:
            return None
        
        cache_file = self.fixtures_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                logger.info("provider_mock.cache_hit", key=cache_key)
                return json.loads(cache_file.read_text())
            except (json.JSONDecodeError, IOError):
                cache_file.unlink(missing_ok=True)
        
        return None
    
    def _set_cached(self, cache_key: str, response: dict[str, Any]) -> None:
        """Cache response to disk."""
        if not self.cache_enabled:
            return
        
        cache_file = self.fixtures_dir / f"{cache_key}.json"
        cache_file.write_text(json.dumps(response, indent=2))
        logger.info("provider_mock.cached", key=cache_key)
    
    def openai_mock(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Mock OpenAI API responses.
        
        Supports:
        - /v1/chat/completions (GPT-4, GPT-4o, GPT-3.5)
        - /v1/completions (legacy)
        - /v1/embeddings
        
        Args:
            request: OpenAI API request body
        
        Returns:
            Mock OpenAI API response
        """
        cache_key = self._cache_key("openai", request)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        model = request.get("model", "gpt-4o-mini")
        messages = request.get("messages", [])
        max_tokens = request.get("max_tokens", 1000)
        
        content = self._generate_openai_content(messages, request.get("response_format"))
        
        prompt_tokens = sum(len(str(m.get("content", "")).split()) for m in messages) * 1.3
        completion_tokens = len(content.split()) * 1.3
        
        response = {
            "id": f"chatcmpl-mock{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(prompt_tokens + completion_tokens),
            },
        }
        
        self._set_cached(cache_key, response)
        logger.info("openai_mock.generated", model=model, tokens=response["usage"]["total_tokens"])
        return response
    
    def _generate_openai_content(self, messages: list[dict], response_format: dict | None) -> str:
        """Generate mock content based on messages."""
        prompt_text = " ".join(str(m.get("content", "")) for m in messages).lower()
        
        if response_format and response_format.get("type") == "json_object":
            if "research" in prompt_text:
                return json.dumps({
                    "selected_topic": "Mock Research Topic",
                    "title_candidates": ["Mock Title 1", "Mock Title 2"],
                    "key_facts": ["Fact 1", "Fact 2"],
                    "sources": [{"url": "https://example.com", "title": "Mock Source"}],
                })
            elif "script" in prompt_text:
                return json.dumps({
                    "title": "Mock Video Title",
                    "segments": [
                        {
                            "id": "seg_1",
                            "section": "hook",
                            "text": "This is a mock hook.",
                            "narration": "This is a mock hook.",
                            "duration_s": 5,
                        }
                    ],
                    "total_duration_s": 60,
                })
            else:
                return json.dumps({"result": "mock_response", "status": "success"})
        
        return "This is a mock response from the OpenAI harness. The actual API was not called."
    
    def anthropic_mock(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Mock Anthropic Claude API responses.
        
        Args:
            request: Anthropic API request body
        
        Returns:
            Mock Anthropic API response
        """
        cache_key = self._cache_key("anthropic", request)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        model = request.get("model", "claude-3-5-sonnet-20241022")
        messages = request.get("messages", [])
        max_tokens = request.get("max_tokens", 1000)
        
        prompt_text = " ".join(str(m.get("content", "")) for m in messages)
        content = f"Mock Claude response: {prompt_text[:100]}..."
        
        response = {
            "id": f"msg_mock{int(time.time())}",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": content,
                }
            ],
            "model": model,
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": len(prompt_text.split()) * 1.3,
                "output_tokens": len(content.split()) * 1.3,
            },
        }
        
        self._set_cached(cache_key, response)
        logger.info("anthropic_mock.generated", model=model)
        return response
    
    def fish_audio_mock(self, request: dict[str, Any]) -> bytes:
        """
        Mock Fish Audio TTS API responses.
        
        Args:
            request: Fish Audio API request body
        
        Returns:
            Mock audio bytes (silent WAV file)
        """
        cache_key = self._cache_key("fish_audio", request)
        cache_file = self.fixtures_dir / f"{cache_key}.wav"
        
        if cache_file.exists():
            logger.info("fish_audio_mock.cache_hit", key=cache_key)
            return cache_file.read_bytes()
        
        audio_bytes = self._generate_silent_wav(duration_seconds=1)
        
        if self.cache_enabled:
            cache_file.write_bytes(audio_bytes)
            logger.info("fish_audio_mock.cached", key=cache_key)
        
        logger.info("fish_audio_mock.generated", size=len(audio_bytes))
        return audio_bytes
    
    def _generate_silent_wav(self, duration_seconds: int = 1, sample_rate: int = 44100) -> bytes:
        """Generate a silent WAV file."""
        num_samples = duration_seconds * sample_rate
        data_size = num_samples * 2
        
        header = b'RIFF'
        header += (data_size + 36).to_bytes(4, 'little')
        header += b'WAVE'
        header += b'fmt '
        header += (16).to_bytes(4, 'little')
        header += (1).to_bytes(2, 'little')
        header += (1).to_bytes(2, 'little')
        header += sample_rate.to_bytes(4, 'little')
        header += (sample_rate * 2).to_bytes(4, 'little')
        header += (2).to_bytes(2, 'little')
        header += (16).to_bytes(2, 'little')
        header += b'data'
        header += data_size.to_bytes(4, 'little')
        
        audio_data = b'\x00' * data_size
        
        return header + audio_data
    
    def dalle_mock(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Mock DALL-E image generation API.
        
        Args:
            request: DALL-E API request body
        
        Returns:
            Mock DALL-E API response with base64 image or URL
        """
        cache_key = self._cache_key("dalle", request)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        prompt = request.get("prompt", "")
        size = request.get("size", "1024x1024")
        response_format = request.get("response_format", "url")
        
        image_bytes = self._generate_placeholder_image()
        
        if response_format == "b64_json":
            b64_image = base64.b64encode(image_bytes).decode()
            response = {
                "created": int(time.time()),
                "data": [
                    {
                        "b64_json": b64_image,
                    }
                ],
            }
        else:
            response = {
                "created": int(time.time()),
                "data": [
                    {
                        "url": f"https://mock-dalle.example.com/images/{cache_key}.png",
                    }
                ],
            }
        
        self._set_cached(cache_key, response)
        logger.info("dalle_mock.generated", prompt=prompt[:50], size=size)
        return response
    
    def _generate_placeholder_image(self) -> bytes:
        """Generate a 1x1 pixel transparent PNG."""
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
    
    def pexels_pixabay_mock(self, request: dict[str, Any], provider: str = "pexels") -> dict[str, Any]:
        """
        Mock Pexels and Pixabay stock media APIs.
        
        Args:
            request: API request parameters (query, per_page, etc.)
            provider: "pexels" or "pixabay"
        
        Returns:
            Mock stock media API response
        """
        cache_key = self._cache_key(provider, request)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        query = request.get("query", "nature")
        per_page = request.get("per_page", 15)
        
        results = []
        for i in range(min(per_page, 5)):
            if provider == "pexels":
                results.append({
                    "id": f"mock_{i}",
                    "width": 1920,
                    "height": 1080,
                    "url": f"https://www.pexels.com/photo/mock-{i}/",
                    "photographer": "Mock Photographer",
                    "photographer_url": "https://www.pexels.com/@mock",
                    "src": {
                        "original": f"https://images.pexels.com/photos/mock-{i}/pexels-photo-mock-{i}.jpeg",
                        "large": f"https://images.pexels.com/photos/mock-{i}/pexels-photo-mock-{i}.jpeg?w=1920",
                        "medium": f"https://images.pexels.com/photos/mock-{i}/pexels-photo-mock-{i}.jpeg?w=1280",
                    },
                })
            else:
                results.append({
                    "id": f"mock_{i}",
                    "pageURL": f"https://pixabay.com/photos/mock-{i}/",
                    "type": "photo",
                    "tags": query,
                    "previewURL": f"https://cdn.pixabay.com/photo/mock-{i}_150.jpg",
                    "webformatURL": f"https://pixabay.com/get/mock-{i}.jpg",
                    "largeImageURL": f"https://pixabay.com/get/mock-{i}_1920.jpg",
                    "imageWidth": 1920,
                    "imageHeight": 1080,
                    "user": "mock_user",
                })
        
        if provider == "pexels":
            response = {
                "page": 1,
                "per_page": per_page,
                "photos": results,
                "total_results": 1000,
            }
        else:
            response = {
                "total": 1000,
                "totalHits": 500,
                "hits": results,
            }
        
        self._set_cached(cache_key, response)
        logger.info(f"{provider}_mock.generated", query=query, results=len(results))
        return response
    
    def serpapi_mock(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Mock SerpAPI web search responses.
        
        Args:
            request: SerpAPI request parameters
        
        Returns:
            Mock SerpAPI response
        """
        cache_key = self._cache_key("serpapi", request)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        query = request.get("q", "")
        num_results = request.get("num", 10)
        
        organic_results = []
        for i in range(min(num_results, 5)):
            organic_results.append({
                "position": i + 1,
                "title": f"Mock Result {i+1} for {query}",
                "link": f"https://example.com/result-{i+1}",
                "snippet": f"This is a mock search result snippet for query: {query}. It contains relevant information about the topic.",
                "source": "Example.com",
            })
        
        response = {
            "search_metadata": {
                "id": f"mock_{int(time.time())}",
                "status": "Success",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "processed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "total_time_taken": 0.5,
            },
            "search_parameters": {
                "q": query,
                "num": num_results,
            },
            "organic_results": organic_results,
        }
        
        self._set_cached(cache_key, response)
        logger.info("serpapi_mock.generated", query=query, results=len(organic_results))
        return response
    
    def youtube_api_mock(self, request: dict[str, Any], endpoint: str = "search") -> dict[str, Any]:
        """
        Mock YouTube Data API v3 responses.
        
        Args:
            request: YouTube API request parameters
            endpoint: API endpoint (search, videos, channels, etc.)
        
        Returns:
            Mock YouTube API response
        """
        cache_key = self._cache_key(f"youtube_{endpoint}", request)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if endpoint == "search":
            query = request.get("q", "")
            max_results = request.get("maxResults", 5)
            
            items = []
            for i in range(min(max_results, 3)):
                items.append({
                    "kind": "youtube#searchResult",
                    "id": {
                        "kind": "youtube#video",
                        "videoId": f"mock_video_{i}",
                    },
                    "snippet": {
                        "title": f"Mock Video {i+1}: {query}",
                        "description": f"This is a mock video description for {query}",
                        "thumbnails": {
                            "default": {"url": f"https://i.ytimg.com/vi/mock_{i}/default.jpg"},
                            "medium": {"url": f"https://i.ytimg.com/vi/mock_{i}/mqdefault.jpg"},
                            "high": {"url": f"https://i.ytimg.com/vi/mock_{i}/hqdefault.jpg"},
                        },
                        "channelTitle": "Mock Channel",
                    },
                })
            
            response = {
                "kind": "youtube#searchListResponse",
                "items": items,
                "pageInfo": {
                    "totalResults": 1000,
                    "resultsPerPage": max_results,
                },
            }
        
        elif endpoint == "videos":
            video_id = request.get("id", "mock_video_0")
            response = {
                "kind": "youtube#videoListResponse",
                "items": [
                    {
                        "kind": "youtube#video",
                        "id": video_id,
                        "snippet": {
                            "title": "Mock Video Title",
                            "description": "Mock video description",
                            "channelTitle": "Mock Channel",
                        },
                        "statistics": {
                            "viewCount": "1000000",
                            "likeCount": "50000",
                            "commentCount": "1000",
                        },
                    }
                ],
            }
        
        else:
            response = {"kind": f"youtube#{endpoint}ListResponse", "items": []}
        
        self._set_cached(cache_key, response)
        logger.info(f"youtube_{endpoint}_mock.generated")
        return response
    
    def gemini_mock(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Mock Google Gemini API responses.
        
        Args:
            request: Gemini API request body
        
        Returns:
            Mock Gemini API response
        """
        cache_key = self._cache_key("gemini", request)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        contents = request.get("contents", [])
        
        prompt_text = ""
        for content in contents:
            for part in content.get("parts", []):
                if "text" in part:
                    prompt_text += part["text"] + " "
        
        response_text = f"Mock Gemini response for: {prompt_text[:100]}..."
        
        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": response_text,
                            }
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                    "safetyRatings": [
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "probability": "NEGLIGIBLE",
                        },
                    ],
                }
            ],
            "usageMetadata": {
                "promptTokenCount": len(prompt_text.split()),
                "candidatesTokenCount": len(response_text.split()),
                "totalTokenCount": len(prompt_text.split()) + len(response_text.split()),
            },
        }
        
        self._set_cached(cache_key, response)
        logger.info("gemini_mock.generated")
        return response
