"""``autotag`` handler — caption + tag an image with OpenAI vision.

Posts the image bytes (base64) to ``gpt-4o-mini`` with a structured prompt
requesting a short caption + 5–12 tags. Writes:

* ``dam_assets.ai_tags`` — ``{tag: confidence}`` JSONB
* ``dam_assets.metadata.caption`` — one-sentence caption (consumed by the
  embed handler so the semantic vector picks it up)

Skips video / audio / non-image assets (a future ticket adds frame-sample
captioning for video).
"""
from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx
import structlog

from core.config import settings
from temporal_workers.media_jobs.storage import download_bytes

logger = structlog.get_logger()

KIND = "autotag"

_PROMPT = (
    "You are a media-library cataloguer. Look at the image and respond with "
    'JSON of the shape {"caption": "<one short factual sentence>", "tags": '
    '["tag1", "tag2", ...] }. Use lowercase, hyphen-separated tags. Return 5 '
    "to 12 tags. No commentary outside the JSON."
)

_VISION_URL = "https://api.openai.com/v1/chat/completions"
_VISION_MODEL = "gpt-4o-mini"
_TIMEOUT_S = 30.0


async def run(pool: Any, asset: dict, job: dict) -> dict:
    if asset.get("kind") != "image":
        return {"status": "skipped", "reason": f"autotag is image-only for now (kind={asset.get('kind')!r})"}
    if not settings.openai_api_key:
        return {"status": "skipped", "reason": "OPENAI_API_KEY not set"}

    storage_key = asset.get("storage_key")
    if not storage_key:
        return {"status": "skipped", "reason": "asset has no storage_key"}

    data = await download_bytes(storage_key)
    if data is None:
        return {"status": "failed", "reason": "could not fetch object"}

    payload = await _call_vision(data, asset.get("mime_type") or "image/png")
    if payload is None:
        return {"status": "failed", "reason": "vision call failed"}

    caption, tags = _parse_response(payload)
    if not tags:
        return {"status": "failed", "reason": "no tags parsed from vision response"}

    ai_tags = {t: 0.9 for t in tags}
    await pool.execute(
        """
        UPDATE dam_assets
           SET ai_tags = $2::jsonb,
               metadata = COALESCE(metadata, '{}'::jsonb) ||
                          CASE WHEN $3::text <> '' THEN jsonb_build_object('caption', $3::text)
                               ELSE '{}'::jsonb END,
               updated_at = now()
         WHERE id = $1
        """,
        asset["id"],
        json.dumps(ai_tags),
        caption or "",
    )
    return {"status": "done", "result": {"tags": tags, "caption": caption}}


async def _call_vision(data: bytes, mime: str) -> dict | None:
    b64 = base64.b64encode(data).decode("ascii")
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": _VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 300,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            r = await client.post(_VISION_URL, headers=headers, json=body)
        if r.status_code != 200:
            logger.warning("autotag.vision_http_error", status=r.status_code, body=r.text[:200])
            return None
        return r.json()
    except Exception as exc:
        logger.warning("autotag.vision_exception", error=str(exc))
        return None


def _parse_response(payload: dict) -> tuple[str, list[str]]:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return "", []
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if not m:
            return "", []
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError:
            return "", []
    caption = str(parsed.get("caption") or "").strip()
    raw_tags = parsed.get("tags") or []
    tags: list[str] = []
    if isinstance(raw_tags, list):
        for t in raw_tags:
            s = re.sub(r"[^a-z0-9\-]+", "-", str(t).strip().lower()).strip("-")
            if s and s not in tags:
                tags.append(s)
            if len(tags) >= 12:
                break
    return caption, tags
