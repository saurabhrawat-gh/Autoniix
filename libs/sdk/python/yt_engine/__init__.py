"""yt_engine — typed Python SDK for the Remotion Vision rendering engine (P0.10).

Two clients live here:

- ``RemotionClient``  — wraps the Remotion render API (`/api/render`, polling,
  health). Replaces ad-hoc ``httpx`` calls scattered across
  ``src/services/assembly/main.py`` and ``src/workers/activities/render.py``.
- ``McpClient``       — wraps the MCP tool surface (`/tool/<name>`). Lets
  Python services drive scene-graph drafts, registry queries, bandit pulls.

Both share retry + timeout policy and use ``httpx.AsyncClient``. They are
deliberately thin — the REST + tool contracts live in
``services/remotion/src/api/server.ts`` and ``services/remotion/src/mcp/tools.ts``
and remain the single source of truth.
"""

from .remotion import RemotionClient, RemotionError, RenderRequest, RenderStatus
from .mcp import McpClient, McpError, ToolName

__all__ = [
    "RemotionClient",
    "RemotionError",
    "RenderRequest",
    "RenderStatus",
    "McpClient",
    "McpError",
    "ToolName",
]

__version__ = "0.1.0"
