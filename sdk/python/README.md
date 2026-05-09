# yt-engine — Python SDK

Typed async clients for the Remotion Vision rendering engine in the
`yt-automation` stack (P0.10 of the remotion-vision plan).

## Install (editable, from this repo)

```bash
pip install -e sdk/python
```

## Usage

### Render API

```python
from yt_engine import RemotionClient, RenderRequest

client = RemotionClient()  # reads REMOTION_API_URL or http://remotion-api:4000

req = RenderRequest(
    composition="MainVideo",
    input_props={"direction": direction_v3_dict},
    quality=80,
    export_stems=False,
)

result = await client.render_and_wait(req, timeout_s=900)
print(result.status, result.output_url, result.qc)
```

### MCP tools

```python
from yt_engine import McpClient

mcp = McpClient()  # reads REMOTION_MCP_URL or http://remotion-mcp:4100

drafted = await mcp.propose_scene(direction=direction_v3_dict, niche="documentary")
arms    = await mcp.run_bandit_sample(cluster="hook_style")
scenes  = await mcp.query_registry(kind="scene", limit=10)
```

## Contracts

This SDK is intentionally thin. The contracts it mirrors live at:

- `services/remotion/src/api/server.ts` — render API
- `services/remotion/src/mcp/tools.ts` — MCP tools
- `services/remotion/src/scene-graph/types.ts` — SceneGraph IR (passed through as `dict[str, Any]`)
- `services/remotion/src/schemas/directionV3.ts` — direction-v3 input shape

Changes to those should be reflected here in the same PR.
