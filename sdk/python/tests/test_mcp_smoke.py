"""End-to-end smoke for the Python SDK against a live MCP tool server.

Boots ``services/remotion/src/mcp/server.ts`` on a free port via ``tsx``,
fires three tool calls through ``McpClient``, then tears the server down.

Skipped automatically when ``tsx`` / ``node_modules`` aren't available so
this module is safe to import from CI workers that don't have the JS stack.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
REMOTION_DIR = REPO_ROOT / "services" / "remotion"
FIXTURE = REMOTION_DIR / "src" / "scene-graph" / "__fixtures__" / "minimal-direction.json"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _has_node_modules() -> bool:
    return (REMOTION_DIR / "node_modules" / "tsx").exists()


@pytest.mark.skipif(not _has_node_modules(), reason="services/remotion node_modules not installed")
@pytest.mark.asyncio
async def test_mcp_smoke_end_to_end() -> None:
    from yt_engine import McpClient

    port = _free_port()
    env = {**os.environ, "MCP_PORT": str(port)}
    proc = subprocess.Popen(
        ["npx", "tsx", "src/mcp/server.ts"],
        cwd=REMOTION_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Wait for /health
        deadline = time.monotonic() + 30.0
        ready = False
        while time.monotonic() < deadline:
            try:
                async with httpx.AsyncClient(timeout=1.5) as c:
                    resp = await c.get(f"http://127.0.0.1:{port}/health")
                    if resp.status_code == 200:
                        ready = True
                        break
            except Exception:  # noqa: BLE001
                await asyncio.sleep(0.4)
        assert ready, f"MCP server failed to start on :{port}"

        client = McpClient(base_url=f"http://127.0.0.1:{port}")

        health = await client.health()
        assert health["status"] == "ok"
        assert "tools" in health

        bandit = await client.run_bandit_sample(cluster="hook_style")
        assert bandit["arm"] == "question"

        direction = json.loads(FIXTURE.read_text())
        proposed = await client.propose_scene(direction=direction, niche="documentary")
        assert "graph" in proposed and proposed["graph"]["hash"]
        assert isinstance(proposed["appliedAgents"], list) and len(proposed["appliedAgents"]) >= 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
