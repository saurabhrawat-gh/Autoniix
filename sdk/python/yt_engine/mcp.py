"""Typed client for the MCP tool server.

The tool surface is implemented in
``services/remotion/src/mcp/tools.ts``. This client mirrors each tool with a
typed Python method; tool names follow the ``snake_case`` convention used on
both sides.
"""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx


ToolName = Literal[
    "propose_scene",
    "render_preview",
    "query_registry",
    "get_qc_report",
    "list_channels",
    "get_retention_curve",
    "run_bandit_sample",
]


class McpError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class McpClient:
    """Async client over the MCP HTTP tool server.

    Attributes:
        base_url: Server base URL. Reads ``REMOTION_MCP_URL`` env, falls back
            to ``http://remotion-mcp:4100``.
    """

    def __init__(self, base_url: str | None = None, *, timeout_s: float = 30.0) -> None:
        self._base_url = (base_url or os.environ.get("REMOTION_MCP_URL") or "http://remotion-mcp:4100").rstrip("/")
        self._timeout = httpx.Timeout(timeout_s, connect=5.0)

    @property
    def base_url(self) -> str:
        return self._base_url

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/health")
        return self._unwrap(resp, expect="health")

    async def list_tools(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/tools")
        return self._unwrap(resp, expect="tools listing")

    async def call(self, tool: ToolName, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/tool/{tool}", json=payload or {})
        return self._unwrap(resp, expect=f"tool {tool}")

    # typed wrappers (one per tool)

    async def propose_scene(
        self,
        *,
        direction: dict[str, Any] | None = None,
        graph: dict[str, Any] | None = None,
        passes: list[Literal["director", "editor"]] | None = None,
        niche: str | None = None,
    ) -> dict[str, Any]:
        if (direction is None) == (graph is None):
            raise ValueError("propose_scene: pass exactly one of `direction` or `graph`")
        source: dict[str, Any] = (
            {"kind": "directionV3", "direction": direction}
            if direction is not None
            else {"kind": "sceneGraph", "graph": graph}
        )
        body: dict[str, Any] = {"source": source}
        if passes is not None:
            body["passes"] = passes
        if niche is not None:
            body["niche"] = niche
        return await self.call("propose_scene", body)

    async def render_preview(
        self, *, graph: dict[str, Any], range_ms: tuple[int, int] | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"graph": graph}
        if range_ms is not None:
            body["rangeMs"] = list(range_ms)
        return await self.call("render_preview", body)

    async def query_registry(
        self,
        *,
        kind: Literal["scene", "effect", "transition", "animation", "overlay", "lut", "sfx"] | None = None,
        tag: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if kind is not None:
            body["kind"] = kind
        if tag is not None:
            body["tag"] = tag
        if limit is not None:
            body["limit"] = limit
        return await self.call("query_registry", body)

    async def get_qc_report(self, *, job_id: str) -> dict[str, Any]:
        return await self.call("get_qc_report", {"jobId": job_id})

    async def list_channels(self) -> dict[str, Any]:
        return await self.call("list_channels", {})

    async def get_retention_curve(self, *, channel_id: str, last_n: int | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"channelId": channel_id}
        if last_n is not None:
            body["lastN"] = last_n
        return await self.call("get_retention_curve", body)

    async def run_bandit_sample(self, *, cluster: str, channel_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"cluster": cluster}
        if channel_id is not None:
            body["channelId"] = channel_id
        return await self.call("run_bandit_sample", body)

    # helpers

    @staticmethod
    def _unwrap(resp: httpx.Response, *, expect: str) -> dict[str, Any]:
        if resp.status_code >= 400:
            try:
                body: Any = resp.json()
            except Exception:  # noqa: BLE001
                body = resp.text
            raise McpError(f"{expect} failed (HTTP {resp.status_code})", status_code=resp.status_code, body=body)
        try:
            payload: Any = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise McpError(f"{expect} returned non-JSON response", status_code=resp.status_code, body=resp.text) from exc
        if not isinstance(payload, dict):
            raise McpError(f"{expect} returned non-object response", status_code=resp.status_code, body=payload)
        return payload
