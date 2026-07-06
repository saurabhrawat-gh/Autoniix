"""Typed client for the Remotion render API.

Mirrors the Express endpoints declared in
``services/remotion/src/api/server.ts``:

    POST /api/render         enqueue a render
    POST /api/thumbnail      enqueue a still
    GET  /api/render/:id     poll status
    GET  /api/health         queue depth + memory

Use ``submit_render`` + ``wait_for_render`` for the common case. Set
``base_url`` from ``REMOTION_API_URL`` env (default
``http://remotion-api:4000``) to match the docker-compose stack.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx


Composition = Literal["MainVideo", "ShortFormVideo", "ThumbnailComp"]
Codec = Literal["h264", "h265", "vp8", "vp9"]
OutputFormat = Literal["mp4", "webm", "png", "jpeg"]


class RemotionError(RuntimeError):
    """Raised when the Remotion API returns a non-2xx response or times out."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


@dataclass(slots=True)
class RenderRequest:
    composition: Composition
    input_props: dict[str, Any]
    codec: Codec = "h264"
    output_format: OutputFormat = "mp4"
    quality: int = 80
    width: int | None = None
    height: int | None = None
    callback_url: str | None = None
    export_stems: bool = False

    def to_payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "composition": self.composition,
            "inputProps": self.input_props,
            "codec": self.codec,
            "outputFormat": self.output_format,
            "quality": self.quality,
        }
        if self.width is not None:
            body["width"] = self.width
        if self.height is not None:
            body["height"] = self.height
        if self.callback_url is not None:
            body["callbackUrl"] = self.callback_url
        if self.export_stems:
            body["exportStems"] = True
        return body


@dataclass(slots=True)
class RenderStatus:
    render_id: str
    status: Literal["rendering", "done", "failed"]
    progress: float = 0.0
    output_url: str | None = None
    file_size: int | None = None
    duration: int | None = None
    qc: dict[str, Any] | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def done(self) -> bool:
        return self.status in ("done", "failed")

    @classmethod
    def from_response(cls, body: dict[str, Any]) -> "RenderStatus":
        return cls(
            render_id=str(body.get("renderId") or ""),
            status=body.get("status", "rendering"),
            progress=float(body.get("progress") or 0.0),
            output_url=body.get("outputUrl"),
            file_size=body.get("fileSize"),
            duration=body.get("duration"),
            qc=body.get("qc"),
            error=body.get("error"),
            raw=body,
        )


class RemotionClient:
    """Async client over the Remotion render API."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_s: float = 30.0,
        poll_interval_s: float = 3.0,
        poll_timeout_s: float = 600.0,
    ) -> None:
        self._base_url = (base_url or os.environ.get("REMOTION_API_URL") or "http://remotion-api:4000").rstrip("/")
        self._timeout = httpx.Timeout(timeout_s, connect=10.0)
        self._poll_interval_s = poll_interval_s
        self._poll_timeout_s = poll_timeout_s

    @property
    def base_url(self) -> str:
        return self._base_url

    async def submit_render(self, req: RenderRequest) -> RenderStatus:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/api/render", json=req.to_payload())
        return self._handle(resp, expect="render submission")

    async def submit_thumbnail(
        self,
        input_props: dict[str, Any],
        *,
        output_format: Literal["png", "jpeg"] = "png",
        width: int | None = None,
        height: int | None = None,
    ) -> RenderStatus:
        body: dict[str, Any] = {"inputProps": input_props, "outputFormat": output_format}
        if width is not None:
            body["width"] = width
        if height is not None:
            body["height"] = height
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/api/thumbnail", json=body)
        return self._handle(resp, expect="thumbnail submission")

    async def get_status(self, render_id: str) -> RenderStatus:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(f"{self._base_url}/api/render/{render_id}")
        return self._handle(resp, expect=f"render {render_id} status")

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{self._base_url}/api/health")
        if resp.status_code >= 400:
            raise RemotionError(
                f"health check failed (HTTP {resp.status_code})",
                status_code=resp.status_code,
                body=resp.text,
            )
        return resp.json()

    async def wait_for_render(
        self,
        render_id: str,
        *,
        poll_interval_s: float | None = None,
        timeout_s: float | None = None,
    ) -> RenderStatus:
        """Poll until the render is ``done``/``failed`` or the timeout elapses."""

        interval = poll_interval_s if poll_interval_s is not None else self._poll_interval_s
        deadline = (timeout_s if timeout_s is not None else self._poll_timeout_s)
        elapsed = 0.0
        last: RenderStatus | None = None
        while elapsed < deadline:
            last = await self.get_status(render_id)
            if last.done:
                return last
            await asyncio.sleep(interval)
            elapsed += interval
        raise RemotionError(
            f"render {render_id} did not complete within {deadline:.0f}s (last status={last.status if last else 'n/a'})",
            body=last.raw if last else None,
        )

    async def render_and_wait(self, req: RenderRequest, **wait_kwargs: Any) -> RenderStatus:
        submitted = await self.submit_render(req)
        if not submitted.render_id:
            raise RemotionError("render submission returned no renderId", body=submitted.raw)
        return await self.wait_for_render(submitted.render_id, **wait_kwargs)

    # helpers

    @staticmethod
    def _handle(resp: httpx.Response, *, expect: str) -> RenderStatus:
        if resp.status_code >= 400:
            raise RemotionError(
                f"{expect} failed (HTTP {resp.status_code})",
                status_code=resp.status_code,
                body=_safe_json(resp),
            )
        body = _safe_json(resp)
        if not isinstance(body, dict):
            raise RemotionError(f"{expect} returned non-object body", body=body)
        return RenderStatus.from_response(body)


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return resp.text
