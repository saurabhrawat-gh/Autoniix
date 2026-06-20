"""
Python gRPC service harness — template for adding gRPC test infrastructure
to existing Python AI services (Brain, Analytics, Preventor, etc.).

Per HARNESS-ENGINEERING-PLAN.md Week 3 Day 3.

Usage:
    async with GRPCServiceHarness("brain") as h:
        stub = BrainServiceStub(h.channel)
        resp = await stub.Recall(RecallRequest(query="test"))
        assert resp.result
"""
from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

import grpc
import grpc.aio
import structlog

logger = structlog.get_logger()


class GRPCServiceHarness:
    """
    In-process gRPC test harness for Python AI services.

    Starts a gRPC server on a random local port, connects a client,
    and provides a channel for creating stubs in tests.

    Example:
        async with GRPCServiceHarness("brain") as h:
            stub = BrainServiceStub(h.channel)
            resp = await stub.Recall(RecallRequest(query="AI trends"))
            assert resp.summary
    """

    def __init__(self, service_name: str, port: int = 0):
        """
        Initialize the harness.

        Args:
            service_name: Name of the service being tested (for logging)
            port: Port to bind to (0 = random available port)
        """
        self.service_name = service_name
        self.port = port
        self._server: grpc.aio.Server | None = None
        self._channel: grpc.aio.Channel | None = None
        self._bound_port: int | None = None

    async def __aenter__(self) -> "GRPCServiceHarness":
        self._server = grpc.aio.server()
        self._bound_port = self._server.add_insecure_port(f"127.0.0.1:{self.port}")
        await self._server.start()

        self._channel = grpc.aio.insecure_channel(f"127.0.0.1:{self._bound_port}")

        logger.info(
            "grpc_harness.started",
            service=self.service_name,
            port=self._bound_port,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._channel:
            await self._channel.close()
        if self._server:
            await self._server.stop(grace=0)
        logger.info("grpc_harness.stopped", service=self.service_name)

    @property
    def channel(self) -> grpc.aio.Channel:
        """gRPC channel connected to the in-process server."""
        if self._channel is None:
            raise RuntimeError("GRPCServiceHarness not started. Use 'async with'.")
        return self._channel

    @property
    def bound_port(self) -> int:
        """Actual port the server is listening on."""
        if self._bound_port is None:
            raise RuntimeError("GRPCServiceHarness not started. Use 'async with'.")
        return self._bound_port

    def add_servicer(self, add_fn: Any, servicer: Any) -> None:
        """
        Register a gRPC servicer with the in-process server.

        Args:
            add_fn: The generated add_*Servicer_to_server function
            servicer: The servicer instance to register

        Must be called before __aenter__ (i.e., before the `async with` block).
        """
        if self._server is None:
            raise RuntimeError("add_servicer must be called after server creation.")
        add_fn(servicer, self._server)


class MockLLMServicer:
    """
    Mock LLM servicer for gRPC tests.
    Returns deterministic responses based on the request content.
    """

    def __init__(self) -> None:
        self.call_count = 0
        self._responses: dict[str, str] = {
            "research": '{"selected_topic": "Mock Topic", "key_facts": ["Fact 1"]}',
            "script": '{"title": "Mock Script", "segments": []}',
            "default": '{"result": "mock_response", "score": 8.5}',
        }

    def set_response(self, keyword: str, response: str) -> None:
        """Override the response for a given keyword."""
        self._responses[keyword] = response

    def reset(self) -> None:
        """Reset call count and custom responses."""
        self.call_count = 0
        self._responses = {
            "default": '{"result": "mock_response", "score": 8.5}',
        }

    def _get_response(self, prompt: str) -> str:
        """Return a response based on prompt content."""
        self.call_count += 1
        prompt_lower = prompt.lower()
        for keyword, response in self._responses.items():
            if keyword != "default" and keyword in prompt_lower:
                return response
        return self._responses["default"]


class HTTPServiceHarness:
    """
    HTTP test harness for Python FastAPI services.

    For services that expose HTTP (not gRPC) — e.g. the Python AI services
    that will gain gRPC wrappers over time.

    Usage:
        async with HTTPServiceHarness(app) as h:
            resp = await h.client.post("/api/v1/research", json={"topic": "AI"})
            assert resp.status_code == 200
    """

    def __init__(self, app: Any, base_url: str = "http://testserver"):
        """
        Initialize the HTTP harness.

        Args:
            app: FastAPI/Starlette application instance
            base_url: Base URL for test client
        """
        self.app = app
        self.base_url = base_url
        self._client: Any | None = None

    async def __aenter__(self) -> "HTTPServiceHarness":
        try:
            import httpx
            from asgi_lifespan import LifespanManager

            self._lifespan = LifespanManager(self.app)
            await self._lifespan.__aenter__()
            self._client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url=self.base_url,
            )
        except ImportError:
            raise ImportError(
                "Install httpx and asgi-lifespan: pip install httpx asgi-lifespan"
            )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
        if hasattr(self, "_lifespan"):
            await self._lifespan.__aexit__(None, None, None)

    @property
    def client(self) -> Any:
        """HTTP client connected to the in-process FastAPI app."""
        if self._client is None:
            raise RuntimeError("HTTPServiceHarness not started. Use 'async with'.")
        return self._client
