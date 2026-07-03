"""Unit tests for individual media_jobs handlers — AE-355."""
from __future__ import annotations

import io
import json
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from src.workers.media_jobs.handlers import autotag, embed, probe




@pytest.mark.asyncio
async def test_probe_handler_writes_image_metadata(mock_pool):
    img = Image.new("RGB", (321, 123), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    asset = {
        "id": 1, "kind": "image",
        "storage_key": "dam/x/y/image/abc.png",
        "mime_type": "image/png",
    }
    with patch(
        "src.workers.media_jobs.handlers.probe.download_bytes",
        AsyncMock(return_value=buf.getvalue()),
    ):
        out = await probe.run(mock_pool, asset, {"kind": "probe"})

    assert out["status"] == "done"
    assert out["result"]["width"] == 321
    assert out["result"]["height"] == 123
    assert out["result"]["format"] == "png"
    sql = mock_pool.execute.await_args.args[0]
    assert "UPDATE dam_assets" in sql


@pytest.mark.asyncio
async def test_probe_skips_unknown_kind(mock_pool):
    out = await probe.run(mock_pool, {"id": 1, "kind": "template", "storage_key": "k"},
                          {"kind": "probe"})
    assert out["status"] == "skipped"


@pytest.mark.asyncio
async def test_probe_skips_video_until_ffmpeg(mock_pool):
    out = await probe.run(mock_pool, {"id": 1, "kind": "video", "storage_key": "k"},
                          {"kind": "probe"})
    assert out["status"] == "skipped"
    assert "ffprobe" in out["reason"]




@pytest.mark.asyncio
async def test_embed_handler_skips_when_no_text(mock_pool):
    out = await embed.run(mock_pool, {"id": 1, "display_name": "", "tags": []},
                          {"kind": "embed"})
    assert out["status"] == "skipped"


@pytest.mark.asyncio
async def test_embed_handler_upserts_vector_on_success(mock_pool):
    with patch(
        "src.workers.media_jobs.handlers.embed.embed_text",
        AsyncMock(return_value=[0.1] * 1536),
    ):
        out = await embed.run(
            mock_pool,
            {"id": 7, "display_name": "Cool render",
             "tags": ["scifi", "neon"], "ai_tags": {}, "metadata": {}},
            {"kind": "embed"},
        )
    assert out["status"] == "done"
    assert out["result"]["dim"] == 1536
    sql = mock_pool.execute.await_args.args[0]
    assert "INSERT INTO dam_text_embeddings" in sql
    assert "ON CONFLICT (asset_id) DO UPDATE" in sql


@pytest.mark.asyncio
async def test_embed_handler_marks_failed_on_embedding_error(mock_pool):
    from src.llm.embeddings import EmbeddingError

    with patch(
        "src.workers.media_jobs.handlers.embed.embed_text",
        AsyncMock(side_effect=EmbeddingError("down")),
    ):
        out = await embed.run(
            mock_pool,
            {"id": 7, "display_name": "Cool render", "tags": [], "ai_tags": {}, "metadata": {}},
            {"kind": "embed"},
        )
    assert out["status"] == "failed"




@pytest.mark.asyncio
async def test_autotag_handler_skips_non_image(mock_pool):
    with patch("src.workers.media_jobs.handlers.autotag.settings.openai_api_key", "sk-x"):
        out = await autotag.run(mock_pool, {"id": 1, "kind": "video", "storage_key": "k"},
                                {"kind": "autotag"})
    assert out["status"] == "skipped"


@pytest.mark.asyncio
async def test_autotag_handler_skips_without_api_key(mock_pool):
    with patch("src.workers.media_jobs.handlers.autotag.settings.openai_api_key", ""):
        out = await autotag.run(mock_pool, {"id": 1, "kind": "image", "storage_key": "k"},
                                {"kind": "autotag"})
    assert out["status"] == "skipped"


@pytest.mark.asyncio
async def test_autotag_handler_writes_tags_and_caption(mock_pool):
    payload = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "caption": "A red car in a snowy street.",
                    "tags": ["car", "red", "snow", "winter"],
                })
            }
        }]
    }

    class _R:
        status_code = 200
        text = ""
        def json(self_inner):
            return payload

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): return _R()

    with patch("src.workers.media_jobs.handlers.autotag.settings.openai_api_key", "sk-x"), \
         patch("src.workers.media_jobs.handlers.autotag.httpx.AsyncClient", _Client), \
         patch(
             "src.workers.media_jobs.handlers.autotag.download_bytes",
             AsyncMock(return_value=b"\x89PNG\r\n"),
         ):
        out = await autotag.run(
            mock_pool,
            {"id": 7, "kind": "image", "storage_key": "k", "mime_type": "image/png"},
            {"kind": "autotag"},
        )
    assert out["status"] == "done"
    assert "car" in out["result"]["tags"]
    sql = mock_pool.execute.await_args.args[0]
    assert "UPDATE dam_assets" in sql
    assert "ai_tags" in sql
