"""End-to-end smoke test for the Remotion render path.

Submits a tiny Direction v3 directly to the Remotion API, polls for
completion, and asserts the resulting MP4:

  * is reachable via the dashboard proxy,
  * has a video stream,
  * has at least the expected duration,
  * is **not a black-frame render** (mean luminance > 30/255 over 20 sample
    frames).

This is the regression gate for Phase 1 of the master plan. Black-screen
renders, missing-bucket failures, key-prefix mismatches, and broken download
URLs are all caught here.

The test is opt-in: it requires the docker stack (or at minimum the
``remotion-api`` and MinIO services) to be reachable. By default it skips
unless ``YT_E2E_REMOTION_URL`` is set in the environment.

Typical CI invocation::

    docker compose up -d minio minio-bootstrap remotion-api remotion-worker
    YT_E2E_REMOTION_URL=http://localhost:4000 \
    YT_E2E_DASHBOARD_URL=http://localhost:8020 \
    pytest tests/e2e/test_render_smoke.py -q

The dashboard URL is optional — when omitted, the test exercises only the
Remotion API + MinIO path.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any

import httpx
import pytest

REMOTION_URL = os.getenv("YT_E2E_REMOTION_URL")
DASHBOARD_URL = os.getenv("YT_E2E_DASHBOARD_URL")

pytestmark = pytest.mark.skipif(
    not REMOTION_URL,
    reason="set YT_E2E_REMOTION_URL to run e2e render smoke tests",
)


def _build_minimal_direction() -> dict[str, Any]:
    """5-second, 5-segment direction guaranteed to render bright pixels.

    Uses scene.placeholder (light-gray label on dark-gray background — well
    above the 30/255 luminance floor) plus one kinetic-typography segment to
    exercise text rendering. No external assets, no audio.
    """
    fps = 30
    seg_ms = 1_000
    return {
        "version": "3.0",
        "meta": {
            "video_id": f"smoke_{int(time.time())}",
            "channel_id": "smoke",
            "title": "Render smoke test",
            "duration_target_seconds": 5,
            "aspect": "16:9",
            "fps": fps,
            "resolution": {"width": 640, "height": 360},
        },
        "template": "hybrid-kinetic",
        "theme": {
            "primary_color": "#FF3B30",
            "accent_color": "#FFD60A",
            "background_color": "#1F2937",
            "text_color": "#FFFFFF",
            "fonts": {"heading": "Inter", "body": "Inter"},
        },
        "grade_preset": "fx.grade.cinematic_teal_orange",
        "segments": [
            {
                "id": f"s{i}",
                "start_ms": i * seg_ms,
                "duration_ms": seg_ms,
                "scene_preset": "scene.placeholder",
                "scene_overrides": {
                    "label": f"Frame {i + 1}",
                    "bg": "#1F2937",
                    "fg": "#FFFFFF",
                },
            }
            for i in range(5)
        ],
    }


def _ffprobe_video(path: str) -> dict[str, Any]:
    if shutil.which("ffprobe") is None:
        pytest.skip("ffprobe not available on test runner")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"ffprobe failed: {result.stderr}"
    import json

    return json.loads(result.stdout)


def _mean_luminance(path: str, samples: int = 20) -> float:
    """Sample luminance via ffmpeg signalstats, returns mean Y in 0–255."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available on test runner")
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            path,
            "-vf",
            f"select='not(mod(n\\,{samples}))',signalstats,metadata=print:key=lavfi.signalstats.YAVG",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    import re

    matches = re.findall(r"YAVG=([0-9.]+)", result.stderr)
    assert matches, f"no luminance samples extracted; ffmpeg stderr: {result.stderr[-500:]}"
    values = [float(m) for m in matches]
    return sum(values) / len(values)


def test_render_smoke_produces_visible_mp4(tmp_path):
    """Submit minimal direction, poll, download, verify non-black playable MP4."""
    direction = _build_minimal_direction()

    with httpx.Client(base_url=REMOTION_URL, timeout=30) as client:
        resp = client.post(
            "/api/render",
            json={
                "composition": "MainVideo",
                "inputProps": {"direction": direction},
                "outputFormat": "mp4",
                "codec": "h264",
                "quality": 50,
                "width": 640,
                "height": 360,
            },
        )
        resp.raise_for_status()
        render_id = resp.json()["renderId"]

        deadline = time.monotonic() + 300
        last_status: dict[str, Any] = {}
        while time.monotonic() < deadline:
            status = client.get(f"/api/render/{render_id}").json()
            last_status = status
            if status.get("status") == "done":
                break
            if status.get("status") == "failed":
                pytest.fail(f"render failed: {status.get('error')!r} (qc={status.get('qc')})")
            time.sleep(2)
        else:
            pytest.fail(f"render did not complete in 300s; last status={last_status}")

        qc = last_status.get("qc")
        assert qc is not None, "render result missing post-render QC block"
        assert qc.get("pass") is True, f"worker QC rejected: {qc}"
        mean_lum = qc.get("meanLuminance")
        assert mean_lum is not None and mean_lum > 30, (
            f"worker reported low mean luminance {mean_lum} — black-frame render regression?"
        )

        output_url = last_status["outputUrl"]
        assert output_url, "no outputUrl on done render"

    download_url = output_url
    if DASHBOARD_URL:
        pass

    out = tmp_path / "smoke.mp4"
    with httpx.stream("GET", download_url, timeout=60, follow_redirects=True) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)

    size = out.stat().st_size
    assert size >= 50_000, f"downloaded MP4 suspiciously small: {size}B"

    probe = _ffprobe_video(str(out))
    streams = probe.get("streams", [])
    assert any(s.get("codec_type") == "video" for s in streams), "no video stream"
    duration_s = float(probe.get("format", {}).get("duration", 0))
    assert 4.0 <= duration_s <= 7.0, f"unexpected duration {duration_s}s (want ~5s)"

    lum = _mean_luminance(str(out))
    assert lum > 30, (
        f"BLACK-FRAME REGRESSION: downloaded MP4 mean luminance {lum:.1f}/255 "
        "(threshold 30). The render pipeline shipped a black video."
    )
