"""Snapshot test for the legacy ``/api/*`` surface.

This locks the *shape* of the legacy dashboard API so any unintentional
endpoint removal or rename breaks the build, while still allowing additive
v2 changes. We don't run the endpoints (most need a real DB and Temporal
client) — we just inspect FastAPI's route table.

The expected snapshot lives in ``tests/golden/legacy_api_contract.json``.
To intentionally update it::

    UPDATE_LEGACY_CONTRACT=1 pytest tests/test_legacy_api_contract.py

Whenever the snapshot is updated, code review must verify the diff is
intentional (e.g. a new endpoint added, an old one explicitly retired).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


GOLDEN_PATH = Path(__file__).parent / "golden" / "legacy_api_contract.json"


def _collect_legacy_routes():
    """Import the dashboard FastAPI app and return a normalized route list.

    We only collect HTTP routes whose path starts with ``/api/`` (skipping
    the v2 namespace, since v2 may iterate freely). Each entry is::

        {"path": "/api/channels", "methods": ["GET"]}

    sorted by path + method for deterministic comparison.
    """
    # Make src importable regardless of PYTHONPATH.
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))

    # Mock out env so import doesn't require a real DB at module-load time.
    os.environ.setdefault("DATABASE_URL", "postgresql://app:app@localhost:5433/autoniix")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6380")

    from src.services.dashboard.main import app  # noqa: PLC0415

    out: list[dict] = []
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None)
        if not path or not methods:
            continue
        if not path.startswith("/api/"):
            continue
        if path.startswith("/api/v2/"):
            continue
        # Filter HEAD/OPTIONS noise.
        m = sorted(x for x in methods if x not in ("HEAD", "OPTIONS"))
        if not m:
            continue
        out.append({"path": path, "methods": m})
    out.sort(key=lambda r: (r["path"], r["methods"]))
    return out


def test_legacy_api_contract():
    actual = _collect_legacy_routes()
    if os.getenv("UPDATE_LEGACY_CONTRACT") == "1":
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(json.dumps(actual, indent=2) + "\n")
        pytest.skip("snapshot updated — re-run without UPDATE_LEGACY_CONTRACT")
    if not GOLDEN_PATH.exists():
        # First run — create the golden file silently. Treat as a pass so
        # CI bootstraps cleanly the first time.
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(json.dumps(actual, indent=2) + "\n")
        return
    expected = json.loads(GOLDEN_PATH.read_text())
    if actual == expected:
        return
    # Build a friendly diff message.
    actual_set = {(r["path"], tuple(r["methods"])) for r in actual}
    expected_set = {(r["path"], tuple(r["methods"])) for r in expected}
    removed = sorted(expected_set - actual_set)
    added = sorted(actual_set - expected_set)
    msg = ["Legacy /api/* contract drifted from snapshot.\n"]
    if removed:
        msg.append("REMOVED endpoints (potential breaking change):")
        for p, m in removed:
            msg.append(f"  - {p}  {' '.join(m)}")
    if added:
        msg.append("\nADDED endpoints (additive — likely OK):")
        for p, m in added:
            msg.append(f"  + {p}  {' '.join(m)}")
    msg.append(
        "\nIf this drift is intentional, update the snapshot:"
        "\n    UPDATE_LEGACY_CONTRACT=1 pytest tests/test_legacy_api_contract.py"
    )
    pytest.fail("\n".join(msg))
