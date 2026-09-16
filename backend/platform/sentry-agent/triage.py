"""Triage helpers: parse Sentry Slack messages, detect layer, map priority."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

_LAYER_PATTERNS: List[Tuple[str, str]] = [
    (r"src/services/dashboard|dashboard/src|web/src", "UI"),
    (r"src/workers/", "Worker"),
    (r"scripts/.*\.sql|migrations/|src/db\.py", "DB"),
    (r"src/providers/auth|auth/|auth\.py", "Auth"),
    (r"traefik/|Dockerfile|docker-compose|\.github/workflows", "Infra"),
    (r"src/services/", "Service"),
    (r"src/", "Service"),
    (r"services/remotion", "Worker"),
]

_SENTRY_URL_RE = re.compile(
    r"https://(?:[a-z0-9.-]+\.sentry\.io|sentry\.io)/(?:organizations/[^/]+/)?issues/(\d+)[^\s|>]*"
)


def parse_sentry_slack_message(event: dict) -> Optional[dict]:
    """Extract Sentry alert metadata from a raw Slack message event.

    Returns a dict with keys: issue_id, url, title, fingerprint
    or None if the message is not a recognisable Sentry alert.
    """
    parts: list[str] = [event.get("text", "")]
    for block in event.get("blocks", []):
        if block.get("type") == "section":
            parts.append(block.get("text", {}).get("text", ""))
        for elem in block.get("elements", []):
            parts.append(elem.get("text", ""))
    for att in event.get("attachments", []):
        parts.extend([att.get("text", ""), att.get("title", ""), att.get("fallback", "")])

    full_text = " ".join(p for p in parts if p)

    url_match = _SENTRY_URL_RE.search(full_text)
    if not url_match:
        return None

    issue_id = url_match.group(1)
    url = url_match.group(0).rstrip("/")

    title = f"Sentry Issue #{issue_id}"
    link_label = re.search(r"<https?://[^|>]+\|([^>]+)>", full_text)
    if link_label:
        title = re.sub(r"[*_`]", "", link_label.group(1)).strip()
    elif event.get("text"):
        first_line = event["text"].split("\n")[0]
        clean = re.sub(r"<[^>]+>|[*_`]", "", first_line).strip()
        if clean:
            title = clean

    return {
        "issue_id": issue_id,
        "url": url,
        "title": title[:120],
        "fingerprint": f"sentry-issue-{issue_id}",
    }


def detect_layer(issue: dict) -> str:
    """Infer the Autoniix layer from the issue's stack trace filenames."""
    for entry in issue.get("entries", []):
        if entry.get("type") != "exception":
            continue
        for exc_val in entry.get("data", {}).get("values", []):
            frames = exc_val.get("stacktrace", {}).get("frames", [])
            for frame in reversed(frames):
                filename = (frame.get("filename") or frame.get("module") or "").replace("\\", "/")
                if not filename or _is_stdlib_frame(filename):
                    continue
                for pattern, layer in _LAYER_PATTERNS:
                    if re.search(pattern, filename):
                        return layer
    return "Service"


def map_priority(is_critical_channel: bool, sentry_level: str) -> tuple[str, str]:
    """Return (jira_label, jira_priority_name).

    #alerts-critical → bug:production / Highest
    #alerts-warnings → bug:normal / High
    """
    if is_critical_channel or sentry_level in ("fatal", "error"):
        label = "bug:production"
        priority = "Highest"
    else:
        label = "bug:normal"
        priority = "High"
    return label, priority


def extract_stack_summary(issue: dict, max_frames: int = 10) -> str:
    """Return a compact plaintext stack trace for Jira / Slack messages."""
    lines: list[str] = []
    for entry in issue.get("entries", []):
        if entry.get("type") != "exception":
            continue
        for exc_val in entry.get("data", {}).get("values", []):
            exc_type = exc_val.get("type", "")
            exc_msg = exc_val.get("value", "")
            lines.append(f"{exc_type}: {exc_msg}")
            frames = exc_val.get("stacktrace", {}).get("frames", [])
            for frame in frames[-max_frames:]:
                fn = frame.get("filename") or frame.get("module") or "?"
                ln = frame.get("lineno", "?")
                func = frame.get("function", "?")
                ctx = (frame.get("context_line") or "").strip()
                lines.append(f"  {fn}:{ln} in {func}()")
                if ctx:
                    lines.append(f"    → {ctx}")
    return "\n".join(lines) if lines else "No stack trace available"


def find_culprit_file(issue: dict) -> Optional[str]:
    """Return the innermost application-owned file from the stack trace."""
    for entry in issue.get("entries", []):
        if entry.get("type") != "exception":
            continue
        for exc_val in entry.get("data", {}).get("values", []):
            frames = exc_val.get("stacktrace", {}).get("frames", [])
            for frame in reversed(frames):
                filename = (frame.get("filename") or "").replace("\\", "/").lstrip("/")
                if not filename or _is_stdlib_frame(filename):
                    continue
                if not (
                    filename.endswith(".py")
                    or filename.endswith(".ts")
                    or filename.endswith(".tsx")
                    or filename.endswith(".js")
                ):
                    continue
                return filename
    return None


def _is_stdlib_frame(filename: str) -> bool:
    skip = (
        "/usr/",
        "/opt/",
        "site-packages",
        "node_modules",
        "venv/",
        ".venv/",
        "<frozen",
        "/home/runner",
        "/root/.local",
    )
    return any(s in filename for s in skip)
