"""HTTP retry utilities with exponential backoff for external API calls."""

from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Callable, TypeVar

import httpx
import structlog

logger = structlog.get_logger()

T = TypeVar("T")


def with_http_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retry_on_status: set[int] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator: retry an async HTTP call on transient errors.

    Args:
        max_attempts: Maximum number of attempts (default 3)
        base_delay: Initial delay in seconds (default 1.0)
        max_delay: Maximum delay cap in seconds (default 30.0)
        exponential_base: Backoff multiplier (default 2.0)
        retry_on_status: HTTP status codes to retry (default: 429, 500, 502, 503, 504)

    Retries on:
        - httpx.TimeoutException
        - httpx.ConnectError
        - httpx.HTTPStatusError (if status in retry_on_status)

    Example:
        @with_http_retry(max_attempts=5, base_delay=2.0)
        async def fetch_data(url: str) -> dict:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
    """
    if retry_on_status is None:
        retry_on_status = {429, 500, 502, 503, 504}

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code not in retry_on_status:
                        # Non-retryable status code, fail immediately
                        raise
                    last_exception = e
                    logger.warning(
                        "http.retry.status_error",
                        func=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        status_code=e.response.status_code,
                        url=str(e.request.url),
                    )
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last_exception = e
                    logger.warning(
                        "http.retry.transient_error",
                        func=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        error_type=type(e).__name__,
                    )
                except Exception as e:
                    # Non-retryable exception, fail immediately
                    logger.error(
                        "http.retry.non_retryable",
                        func=func.__name__,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    raise

                if attempt < max_attempts:
                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                    logger.info(
                        "http.retry.backoff",
                        func=func.__name__,
                        attempt=attempt,
                        delay_s=delay,
                    )
                    await asyncio.sleep(delay)

            # All attempts exhausted
            logger.error(
                "http.retry.exhausted",
                func=func.__name__,
                max_attempts=max_attempts,
                last_error=str(last_exception) if last_exception else "unknown",
            )
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__}: all {max_attempts} attempts failed")

        return wrapper

    return decorator


async def http_get_with_retry(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    max_attempts: int = 3,
) -> httpx.Response:
    """
    Convenience function: GET request with automatic retry.

    Args:
        url: Target URL
        params: Query parameters
        headers: HTTP headers
        timeout: Request timeout in seconds
        max_attempts: Maximum retry attempts

    Returns:
        httpx.Response object

    Raises:
        httpx.HTTPStatusError: On non-retryable status codes
        httpx.TimeoutException: After all retries exhausted
        httpx.ConnectError: After all retries exhausted
    """

    @with_http_retry(max_attempts=max_attempts)
    async def _fetch() -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp

    return await _fetch()
