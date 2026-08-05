"""Fallback handler used when no implementation is registered for a kind.

Marks the job as ``skipped`` with an explicit reason so the queue does not
fill up forever with un-processable jobs, and so operators can see which
handlers are missing.
"""

from __future__ import annotations

from typing import Any

KIND = "__skip__"


async def run(pool: Any, asset: dict, job: dict) -> dict:
    return {
        "status": "skipped",
        "reason": (
            f"no handler registered for kind={job.get('kind')!r}; "
            "ffmpeg-based handlers (transcode_hls/transcode_mp4/poster from video/"
            "waveform/transcribe) are a planned follow-up."
        ),
    }
