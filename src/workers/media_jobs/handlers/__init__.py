"""Pluggable handler registry for media_jobs kinds.

To add support for a new ``kind`` (e.g. ``transcode_hls`` once ffmpeg is
available inside the worker image), add a module that defines:

    KIND = "transcode_hls"

    async def run(pool, asset: dict, job: dict) -> dict:
        '''Do the work, return a dict that goes into media_jobs.result.'''

…and import it from this package's ``HANDLERS`` table.

The runner looks up ``HANDLERS[job["kind"]]`` and falls back to
``skip_handler`` when no entry exists.
"""
from __future__ import annotations

from src.workers.media_jobs.handlers import autotag, embed, probe, skip_handler

HANDLERS = {
    probe.KIND: probe.run,
    embed.KIND: embed.run,
    autotag.KIND: autotag.run,
}


def resolve(kind: str):
    """Return the handler for ``kind`` or the skip handler if unknown."""
    return HANDLERS.get(kind, skip_handler.run)


__all__ = ["HANDLERS", "resolve", "skip_handler"]
