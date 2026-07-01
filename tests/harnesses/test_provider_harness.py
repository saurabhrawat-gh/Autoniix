"""
Tests for provider mock harness.
Per HARNESS-ENGINEERING-PLAN.md Week 1 Day 3-5.
"""
import json
import pytest

from .provider_harness import ProviderMockHarness


@pytest.fixture
def harness():
    """Provider mock harness instance."""
    return ProviderMockHarness(cache_enabled=True)


class TestOpenAIMock:
    """Tests for OpenAI API mock."""
    
    def test_openai_chat_completion(self, harness):
        """Test OpenAI chat completion mock."""
        request = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Write a short poem about AI."},
            ],
            "max_tokens": 100,
        }
        
        response = harness.openai_mock(request)
        
        assert response["object"] == "chat.completion"
        assert response["model"] == "gpt-4o"
        assert len(response["choices"]) == 1
        assert response["choices"][0]["message"]["role"] == "assistant"
        assert "usage" in response
        assert response["usage"]["total_tokens"] > 0
    
    def test_openai_json_response(self, harness):
        """Test OpenAI JSON format response."""
        request = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Generate research data."},
                {"role": "user", "content": "Research topic: AI in healthcare"},
            ],
            "response_format": {"type": "json_object"},
        }
        
        response = harness.openai_mock(request)
        content = response["choices"][0]["message"]["content"]
        
        data = json.loads(content)
        assert isinstance(data, dict)
    
    def test_openai_caching(self, harness):
        """Test that identical requests are cached."""
        request = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Test caching"}],
        }
        
        response1 = harness.openai_mock(request)
        response2 = harness.openai_mock(request)
        
        assert response1 == response2


class TestAnthropicMock:
    """Tests for Anthropic Claude API mock."""
    
    def test_anthropic_message(self, harness):
        """Test Anthropic message mock."""
        request = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "user", "content": "Explain quantum computing."},
            ],
            "max_tokens": 200,
        }
        
        response = harness.anthropic_mock(request)
        
        assert response["type"] == "message"
        assert response["role"] == "assistant"
        assert len(response["content"]) > 0
        assert response["content"][0]["type"] == "text"
        assert "usage" in response


class TestFishAudioMock:
    """Tests for Fish Audio TTS mock."""
    
    def test_fish_audio_generates_wav(self, harness):
        """Test Fish Audio generates valid WAV bytes."""
        request = {
            "text": "Hello, this is a test.",
            "voice_id": "test_voice",
        }
        
        audio_bytes = harness.fish_audio_mock(request)
        
        assert audio_bytes[:4] == b'RIFF'
        assert audio_bytes[8:12] == b'WAVE'
        assert len(audio_bytes) > 44


class TestDALLEMock:
    """Tests for DALL-E image generation mock."""
    
    def test_dalle_url_response(self, harness):
        """Test DALL-E URL response format."""
        request = {
            "prompt": "A futuristic city at sunset",
            "size": "1024x1024",
            "response_format": "url",
        }
        
        response = harness.dalle_mock(request)
        
        assert "data" in response
        assert len(response["data"]) > 0
        assert "url" in response["data"][0]
    
    def test_dalle_b64_response(self, harness):
        """Test DALL-E base64 response format."""
        request = {
            "prompt": "Abstract art",
            "response_format": "b64_json",
        }
        
        response = harness.dalle_mock(request)
        
        assert "data" in response
        assert "b64_json" in response["data"][0]
        
        import base64
        b64_data = response["data"][0]["b64_json"]
        decoded = base64.b64decode(b64_data)
        assert len(decoded) > 0


class TestPexelsPixabayMock:
    """Tests for Pexels and Pixabay stock media mocks."""
    
    def test_pexels_search(self, harness):
        """Test Pexels search mock."""
        request = {
            "query": "nature",
            "per_page": 10,
        }
        
        response = harness.pexels_pixabay_mock(request, provider="pexels")
        
        assert "photos" in response
        assert len(response["photos"]) > 0
        assert response["photos"][0]["photographer"] is not None
        assert "src" in response["photos"][0]
    
    def test_pixabay_search(self, harness):
        """Test Pixabay search mock."""
        request = {
            "query": "technology",
            "per_page": 15,
        }
        
        response = harness.pexels_pixabay_mock(request, provider="pixabay")
        
        assert "hits" in response
        assert len(response["hits"]) > 0
        assert response["hits"][0]["type"] == "photo"


class TestSerpAPIMock:
    """Tests for SerpAPI web search mock."""
    
    def test_serpapi_search(self, harness):
        """Test SerpAPI search mock."""
        request = {
            "q": "artificial intelligence trends 2024",
            "num": 10,
        }
        
        response = harness.serpapi_mock(request)
        
        assert "organic_results" in response
        assert len(response["organic_results"]) > 0
        assert "title" in response["organic_results"][0]
        assert "link" in response["organic_results"][0]
        assert "snippet" in response["organic_results"][0]


class TestYouTubeAPIMock:
    """Tests for YouTube Data API mock."""
    
    def test_youtube_search(self, harness):
        """Test YouTube search mock."""
        request = {
            "q": "machine learning tutorial",
            "maxResults": 5,
        }
        
        response = harness.youtube_api_mock(request, endpoint="search")
        
        assert response["kind"] == "youtube#searchListResponse"
        assert "items" in response
        assert len(response["items"]) > 0
        assert response["items"][0]["id"]["kind"] == "youtube#video"
    
    def test_youtube_video_details(self, harness):
        """Test YouTube video details mock."""
        request = {
            "id": "test_video_123",
        }
        
        response = harness.youtube_api_mock(request, endpoint="videos")
        
        assert response["kind"] == "youtube#videoListResponse"
        assert len(response["items"]) > 0
        assert "statistics" in response["items"][0]


class TestGeminiMock:
    """Tests for Google Gemini API mock."""
    
    def test_gemini_generate(self, harness):
        """Test Gemini generate content mock."""
        request = {
            "contents": [
                {
                    "parts": [
                        {"text": "Explain the concept of neural networks."},
                    ],
                },
            ],
        }
        
        response = harness.gemini_mock(request)
        
        assert "candidates" in response
        assert len(response["candidates"]) > 0
        assert response["candidates"][0]["finishReason"] == "STOP"
        assert "usageMetadata" in response


class TestCaching:
    """Tests for caching behavior."""
    
    def test_cache_persistence(self, harness, tmp_path):
        """Test that cache persists across harness instances."""
        harness.fixtures_dir = tmp_path
        
        request = {"model": "gpt-4o", "messages": [{"role": "user", "content": "test"}]}
        
        response1 = harness.openai_mock(request)
        
        harness2 = ProviderMockHarness(cache_enabled=True)
        harness2.fixtures_dir = tmp_path
        
        response2 = harness2.openai_mock(request)
        
        assert response1 == response2
    
    def test_cache_disabled(self, tmp_path):
        """Test that caching can be disabled."""
        harness = ProviderMockHarness(cache_enabled=False)
        harness.fixtures_dir = tmp_path
        
        request = {"model": "gpt-4o", "messages": [{"role": "user", "content": "test"}]}
        
        harness.openai_mock(request)
        
        cache_files = list(tmp_path.glob("*.json"))
        assert len(cache_files) == 0
