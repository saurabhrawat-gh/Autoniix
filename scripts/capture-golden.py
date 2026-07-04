#!/usr/bin/env python3
"""
Capture golden fixtures from the Python v2 dashboard.

For each endpoint in ENDPOINTS, makes a request to the Python dashboard and
saves the response as a golden fixture in tests/golden/<tag>/<slug>.json.

Usage:
    python scripts/capture-golden.py [--output tests/golden] [--python-url http://localhost:8000]

Env vars (override CLI):
    PYTHON_DASHBOARD_URL   base URL of the Python dashboard (default: http://localhost:8000)
    GOLDEN_OUTPUT_DIR      output directory (default: tests/golden)
    TEST_EMAIL             email for seeded test user (default: golden@capture.test)
    TEST_PASSWORD          password for seeded test user (default: GoldenPass123!)

Per HARNESS-ENGINEERING-PLAN.md §A4.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PYTHON_URL = os.environ.get("PYTHON_DASHBOARD_URL", "http://localhost:8000")
OUTPUT_DIR = Path(os.environ.get("GOLDEN_OUTPUT_DIR", "tests/golden"))
TEST_EMAIL = os.environ.get("TEST_EMAIL", "golden@capture.test")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "GoldenPass123!")

# Fields that differ between runs and should be ignored during comparison.
DYNAMIC_FIELDS = [
    "id", "user_id", "workspace_id", "created_at", "updated_at",
    "access_token", "refresh_token", "expires_in", "session_id",
    "delete_scheduled_at", "deleted_at",
]

# ---------------------------------------------------------------------------
# Endpoint definitions
# Each tuple: (tag, slug, method, path, request_body, auth_required)
# ---------------------------------------------------------------------------

ENDPOINTS: list[tuple[str, str, str, str, Any, bool]] = [
    # auth
    ("auth", "auth_mode",          "GET",  "/api/v2/auth/mode",    None,  False),
    # users
    ("users", "me",                "GET",  "/api/v2/me",           None,  True),
    # flags
    ("flags", "flags_list",        "GET",  "/api/v2/flags",        None,  True),
    # notifications
    ("notifications", "deliveries","GET",  "/api/v2/notifications/deliveries", None, True),
    # system
    ("system", "fleet_health",     "GET",  "/api/v2/system/fleet-health", None, True),
    ("system", "config",           "GET",  "/api/v2/system/config", None, True),
    # workspace
    ("workspace", "workspace_get", "GET",  "/api/v2/workspace",    None,  True),
    ("workspace", "members_list",  "GET",  "/api/v2/workspace/members", None, True),
    ("workspace", "invites_list",  "GET",  "/api/v2/workspace/invites", None, True),
    # channels
    ("channels", "channels_list",  "GET",  "/api/v2/channels",     None,  True),
    # voice
    ("voice", "voices_list",       "GET",  "/api/v2/voice/voices", None,  True),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_user(session: requests.Session) -> str | None:
    """Register + login; return access token or None if dashboard not reachable."""
    try:
        ts = int(time.time() * 1000)
        email = f"golden-{ts}@capture.test"
        reg = session.post(
            f"{PYTHON_URL}/api/v2/auth/register",
            json={
                "email": email,
                "password": TEST_PASSWORD,
                "display_name": "Golden Capture",
                "workspace_name": "Golden Workspace",
            },
            timeout=10,
        )
        if reg.status_code not in (200, 201, 409):
            print(f"  [WARN] register returned {reg.status_code}", file=sys.stderr)

        login = session.post(
            f"{PYTHON_URL}/api/v2/auth/signin",
            json={"email": email, "password": TEST_PASSWORD},
            timeout=10,
        )
        if login.status_code == 200:
            return login.json().get("access_token")
        # Fallback: try pre-seeded user
        login2 = session.post(
            f"{PYTHON_URL}/api/v2/auth/signin",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=10,
        )
        if login2.status_code == 200:
            return login2.json().get("access_token")
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"  [WARN] could not authenticate: {exc}", file=sys.stderr)
        return None


def strip_dynamic(body: Any) -> Any:
    """Recursively remove dynamic field values (replace with placeholder)."""
    if isinstance(body, dict):
        return {
            k: "<dynamic>" if k in DYNAMIC_FIELDS else strip_dynamic(v)
            for k, v in body.items()
        }
    if isinstance(body, list):
        return [strip_dynamic(i) for i in body[:3]]  # cap list at 3 items
    return body


def capture_endpoint(
    session: requests.Session,
    token: str | None,
    method: str,
    path: str,
    request_body: Any,
    auth_required: bool,
) -> dict | None:
    url = f"{PYTHON_URL}{path}"
    headers: dict[str, str] = {}
    if auth_required and token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        if method == "GET":
            resp = session.get(url, headers=headers, timeout=15)
        elif method == "POST":
            resp = session.post(url, json=request_body, headers=headers, timeout=15)
        elif method == "PUT":
            resp = session.put(url, json=request_body, headers=headers, timeout=15)
        elif method == "DELETE":
            resp = session.delete(url, headers=headers, timeout=15)
        else:
            return None

        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            body = {}

        return {
            "method": method,
            "path": path,
            "request_body": request_body,
            "status": resp.status_code,
            "body": strip_dynamic(body),
            "ignore_fields": DYNAMIC_FIELDS,
        }
    except requests.exceptions.ConnectionError:
        print(f"  [SKIP] {method} {path} — connection refused", file=sys.stderr)
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"  [ERR] {method} {path} — {exc}", file=sys.stderr)
        return None


def save_fixture(tag: str, slug: str, fixture: dict) -> None:
    out = OUTPUT_DIR / tag
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"{slug}.json"
    dest.write_text(json.dumps(fixture, indent=2) + "\n")
    print(f"  [SAVED] {dest}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Capture golden fixtures from Python v2 dashboard")
    parser.add_argument("--output", default=str(OUTPUT_DIR), help="Output directory")
    parser.add_argument("--python-url", default=PYTHON_URL, help="Python dashboard base URL")
    args = parser.parse_args()

    global OUTPUT_DIR, PYTHON_URL  # noqa: PLW0603
    OUTPUT_DIR = Path(args.output)
    PYTHON_URL = args.python_url.rstrip("/")

    print(f"Capturing golden fixtures from {PYTHON_URL} → {OUTPUT_DIR}")
    print()

    session = requests.Session()
    token = ensure_user(session)
    if token:
        print(f"  Authenticated (token length={len(token)})")
    else:
        print("  Not authenticated — auth-required endpoints will be skipped")

    captured = 0
    skipped = 0

    for tag, slug, method, path, request_body, auth_required in ENDPOINTS:
        if auth_required and not token:
            print(f"  [SKIP] {method} {path} — no auth token")
            skipped += 1
            continue

        print(f"  {method} {path}")
        fixture = capture_endpoint(session, token, method, path, request_body, auth_required)
        if fixture:
            save_fixture(tag, slug, fixture)
            captured += 1
        else:
            skipped += 1

    print()
    print(f"Done. {captured} captured, {skipped} skipped.")
    if captured == 0:
        print("WARNING: No fixtures captured. Is the Python dashboard running?")
        sys.exit(1)


if __name__ == "__main__":
    main()
