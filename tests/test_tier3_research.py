"""
Tier 3 Research Service Tests

Tests for:
- HTTP retry logic on API failures
- Response validation for external APIs
- Embedding deduplication
- Result validation and filtering
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestHTTPRetry:
    """Test HTTP retry decorator and logic."""

    @pytest.mark.asyncio
    async def test_http_retry_succeeds_on_first_attempt(self):
        """Successful API call on first attempt should not retry."""
        from core.http_retry import with_http_retry

        call_count = {"n": 0}

        @with_http_retry(max_attempts=3)
        async def fetch_data():
            call_count["n"] += 1
            return {"status": "ok"}

        result = await fetch_data()
        assert result == {"status": "ok"}
        assert call_count["n"] == 1

    @pytest.mark.asyncio
    async def test_http_retry_retries_on_timeout(self):
        """Timeout errors should trigger retry with exponential backoff."""
        from core.http_retry import with_http_retry

        call_count = {"n": 0}

        @with_http_retry(max_attempts=3, base_delay=0.1)
        async def fetch_data():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise httpx.TimeoutException("Request timeout")
            return {"status": "ok"}

        result = await fetch_data()
        assert result == {"status": "ok"}
        assert call_count["n"] == 3

    @pytest.mark.asyncio
    async def test_http_retry_retries_on_5xx_status(self):
        """5xx status codes should trigger retry."""
        from core.http_retry import with_http_retry

        call_count = {"n": 0}

        @with_http_retry(max_attempts=3, base_delay=0.1)
        async def fetch_data():
            call_count["n"] += 1
            if call_count["n"] < 2:
                mock_request = MagicMock()
                mock_request.url = "http://example.com"
                mock_response = MagicMock()
                mock_response.status_code = 503
                raise httpx.HTTPStatusError("Service unavailable", request=mock_request, response=mock_response)
            return {"status": "ok"}

        result = await fetch_data()
        assert result == {"status": "ok"}
        assert call_count["n"] == 2

    @pytest.mark.asyncio
    async def test_http_retry_does_not_retry_on_4xx_status(self):
        """4xx status codes (except 429) should not retry."""
        from core.http_retry import with_http_retry

        call_count = {"n": 0}

        @with_http_retry(max_attempts=3, base_delay=0.1)
        async def fetch_data():
            call_count["n"] += 1
            mock_request = MagicMock()
            mock_request.url = "http://example.com"
            mock_response = MagicMock()
            mock_response.status_code = 404
            raise httpx.HTTPStatusError("Not found", request=mock_request, response=mock_response)

        with pytest.raises(httpx.HTTPStatusError):
            await fetch_data()

        assert call_count["n"] == 1  # Should not retry

    @pytest.mark.asyncio
    async def test_http_retry_exhausts_attempts(self):
        """After max attempts, should raise the last exception."""
        from core.http_retry import with_http_retry

        call_count = {"n": 0}

        @with_http_retry(max_attempts=3, base_delay=0.1)
        async def fetch_data():
            call_count["n"] += 1
            raise httpx.TimeoutException("Request timeout")

        with pytest.raises(httpx.TimeoutException):
            await fetch_data()

        assert call_count["n"] == 3


class TestAPIValidation:
    """Test API response validation logic."""

    @pytest.mark.asyncio
    async def test_youtube_search_validates_response_structure(self):
        """YouTube search should validate response has 'items' key."""
        from backend.api.core.research.main import _search_youtube

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"error": "Invalid API key"}
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            results = await _search_youtube("test topic", "test niche")
            assert results == []

    @pytest.mark.asyncio
    async def test_youtube_search_filters_invalid_items(self):
        """YouTube search should filter items without videoId or title."""
        from backend.api.core.research.main import _search_youtube, settings

        with (
            patch.object(settings, "youtube_api_key", "test-key"),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "items": [
                    {
                        "id": {"videoId": "abc123"},
                        "snippet": {"title": "Valid Video", "description": "Test"},
                    },
                    {
                        "id": {},  # Missing videoId
                        "snippet": {"title": "Invalid Video"},
                    },
                    {
                        "id": {"videoId": "def456"},
                        "snippet": {},  # Missing title
                    },
                ]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            results = await _search_youtube("test topic", "test niche")
            assert len(results) == 1
            assert results[0]["title"] == "Valid Video"

    @pytest.mark.asyncio
    async def test_reddit_search_validates_response_structure(self):
        """Reddit search should validate response has 'data.children' keys."""
        from backend.api.core.research.main import _search_reddit

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"error": "Invalid request"}
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            results = await _search_reddit("test topic", "test niche")
            assert results == []

    @pytest.mark.asyncio
    async def test_news_search_validates_response_structure(self):
        """News API search should validate response has 'articles' key."""
        from backend.api.core.research.main import _search_news

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "error", "message": "Invalid API key"}
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            results = await _search_news("test topic", "test niche")
            assert results == []


class TestEmbeddingDeduplication:
    """Test embedding deduplication logic."""

    @pytest.mark.asyncio
    async def test_store_topic_embedding_deduplicates_on_conflict(self):
        """Storing duplicate embedding should update existing row."""
        from backend.api.core.research.similarity import store_topic_embedding
        from tests.conftest import FakePool

        fake_pool = FakePool()
        executed_queries = []

        async def fake_execute(query, *args):
            executed_queries.append((query, args))

        fake_pool.execute = fake_execute

        with patch("backend.api.core.research.similarity.get_pool", return_value=fake_pool):
            with patch(
                "backend.api.core.research.similarity.compute_embedding",
                return_value=[0.1] * 384,
            ):
                result = await store_topic_embedding(
                    content_id="test_content_123",
                    channel_id="test_channel",
                    text_type="topic",
                    text="Test topic",
                )

                assert result["embedding_dim"] == 384
                assert "simhash" in result

                # Verify ON CONFLICT clause is present
                assert len(executed_queries) == 1
                query = executed_queries[0][0]
                assert "ON CONFLICT" in query
                assert "DO UPDATE SET" in query

    @pytest.mark.asyncio
    async def test_check_similarity_uses_vector_distance(self):
        """Similarity check should use pgvector distance operator."""
        from backend.api.core.research.similarity import check_similarity
        from tests.conftest import FakePool

        fake_pool = FakePool()
        fake_pool.rows = [
            {
                "content_id": "content_prev",
                "channel_id": "test_channel",
                "text_content": "Similar topic",
                "cosine_sim": 0.95,
                "simhash": 12345,
                "hamming": 2,
            }
        ]

        async def fake_fetch(query, *args):
            # Verify query uses vector distance operator
            assert "<=> $1::vector" in query or "embedding <=> $1" in query
            return fake_pool.rows

        fake_pool.fetch = fake_fetch

        with patch("backend.api.core.research.similarity.get_pool", return_value=fake_pool):
            with patch(
                "backend.api.core.research.similarity.compute_embedding",
                return_value=[0.1] * 384,
            ):
                result = await check_similarity(text="Test topic", channel_id="test_channel", top_k=5)

                assert "nearest_matches" in result
                assert len(result["nearest_matches"]) > 0


class TestResultValidation:
    """Test result validation and filtering."""

    @pytest.mark.asyncio
    async def test_serpapi_filters_results_without_title_or_link(self):
        """SerpAPI search should filter results missing required fields."""
        from backend.api.core.research.main import _search_serpapi

        mock_provider = AsyncMock()
        mock_result = MagicMock()
        mock_result.results = [
            {"title": "Valid Result", "link": "http://example.com", "snippet": "Test"},
            {"title": "No Link"},  # Missing link
            {"link": "http://example2.com"},  # Missing title
            {"title": "Valid Result 2", "link": "http://example3.com"},
        ]
        mock_provider.search.return_value = mock_result

        with patch("backend.api.core.research.main.ProviderRegistry.get", return_value=mock_provider):
            results = await _search_serpapi(["test query"])

            assert len(results) == 2
            assert results[0]["title"] == "Valid Result"
            assert results[1]["title"] == "Valid Result 2"

    @pytest.mark.asyncio
    async def test_wikipedia_search_strips_html_from_snippets(self):
        """Wikipedia search should remove HTML tags from snippets."""
        from backend.api.core.research.main import _search_wikipedia

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "query": {
                    "search": [
                        {
                            "title": "Test Article",
                            "snippet": "This is <b>bold</b> and <i>italic</i> text",
                        }
                    ]
                }
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            results = await _search_wikipedia("test topic")

            assert len(results) == 1
            assert "<b>" not in results[0]["snippet"]
            assert "<i>" not in results[0]["snippet"]
            assert "bold" in results[0]["snippet"]
            assert "italic" in results[0]["snippet"]
