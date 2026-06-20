"""
E2E orchestration harness — spins up the full test environment via docker-compose
and provides a client interface for running end-to-end tests.

Per HARNESS-ENGINEERING-PLAN.md Week 4 Day 2.

Usage:
    async with E2EHarness() as h:
        resp = await h.rust.post("/api/v2/auth/signup", json={...})
        assert resp.status_code == 201

    # Or with docker-compose management:
    async with E2EHarness(manage_docker=True) as h:
        # docker-compose up was called automatically
        ...
        # docker-compose down called on exit
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

COMPOSE_FILE = Path(__file__).parent.parent.parent / "docker-compose.test.yml"
RUST_GATEWAY_URL = "http://localhost:8080"
PYTHON_DASHBOARD_URL = "http://localhost:8000"


class ServiceClient:
    """Thin HTTP client wrapper for a single service."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._client.get(path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._client.post(path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._client.put(path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._client.delete(path, **kwargs)

    async def close(self) -> None:
        await self._client.aclose()

    async def wait_healthy(self, health_path: str = "/health", retries: int = 30) -> bool:
        """Poll health endpoint until service is up."""
        for i in range(retries):
            try:
                resp = await self._client.get(health_path)
                if resp.status_code < 500:
                    logger.info("service.healthy", url=self.base_url)
                    return True
            except httpx.ConnectError:
                pass
            await asyncio.sleep(2.0)
            logger.debug("service.waiting", url=self.base_url, attempt=i + 1)
        logger.error("service.unhealthy", url=self.base_url)
        return False


class E2EHarness:
    """
    End-to-end test harness.

    Provides clients for both Python and Rust services.
    Optionally manages docker-compose lifecycle.

    Attributes:
        rust: HTTP client for the Rust gateway
        python: HTTP client for the Python dashboard
    """

    def __init__(
        self,
        manage_docker: bool = False,
        rust_url: str = RUST_GATEWAY_URL,
        python_url: str = PYTHON_DASHBOARD_URL,
    ):
        self.manage_docker = manage_docker
        self.rust = ServiceClient(rust_url)
        self.python = ServiceClient(python_url)

    async def __aenter__(self) -> "E2EHarness":
        if self.manage_docker:
            logger.info("e2e_harness.docker_compose_up")
            subprocess.run(
                ["docker-compose", "-f", str(COMPOSE_FILE), "up", "-d"],
                check=True,
            )
            # Wait for both services
            rust_ready = await self.rust.wait_healthy()
            python_ready = await self.python.wait_healthy()
            if not (rust_ready and python_ready):
                raise RuntimeError("E2E services failed to become healthy")
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.rust.close()
        await self.python.close()
        if self.manage_docker:
            logger.info("e2e_harness.docker_compose_down")
            subprocess.run(
                ["docker-compose", "-f", str(COMPOSE_FILE), "down", "-v"],
                check=False,
            )

    # ── Auth helpers ────────────────────────────────────────────────────────

    async def rust_signup(
        self,
        email: str,
        password: str = "Password123!",
        workspace_name: str = "E2E Workspace",
    ) -> httpx.Response:
        return await self.rust.post(
            "/api/v2/auth/signup",
            json={"email": email, "password": password, "workspace_name": workspace_name},
        )

    async def python_register(
        self,
        email: str,
        password: str = "Password123!",
        workspace_name: str = "E2E Workspace",
    ) -> httpx.Response:
        return await self.python.post(
            "/auth/register",
            json={"email": email, "password": password, "workspace_name": workspace_name},
        )

    async def rust_signin(self, email: str, password: str = "Password123!") -> str:
        """Sign in via Rust and return the access token."""
        resp = await self.rust.post(
            "/api/v2/auth/signin",
            json={"email": email, "password": password},
        )
        return resp.json().get("access_token", "")

    async def python_login(self, email: str, password: str = "Password123!") -> str:
        """Log in via Python and return the access token."""
        resp = await self.python.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        return resp.json().get("access_token", "")
