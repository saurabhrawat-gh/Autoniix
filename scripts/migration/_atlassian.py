"""Shared Atlassian REST client for the migration scripts.

Reads credentials from ~/.autoniix-atlassian.env (NEVER committed).
All Jira and Confluence calls go through this module so retries,
rate-limiting, and auth are centralised.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

ENV_FILE = Path.home() / ".autoniix-atlassian.env"


def _load_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        sys.stderr.write(
            f"ERROR: credentials file {ENV_FILE} not found.\n"
            "See scripts/migration/README.md for setup.\n"
        )
        sys.exit(2)
    out: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    for required in ("ATLASSIAN_EMAIL", "ATLASSIAN_API_TOKEN", "ATLASSIAN_BASE_URL"):
        if not out.get(required):
            sys.stderr.write(f"ERROR: {required} missing from {ENV_FILE}\n")
            sys.exit(2)
    out["ATLASSIAN_BASE_URL"] = out["ATLASSIAN_BASE_URL"].rstrip("/")
    return out


@dataclass(frozen=True)
class AtlassianConfig:
    email: str
    token: str
    base_url: str

    @property
    def jira_api(self) -> str:
        return f"{self.base_url}/rest/api/3"

    @property
    def confluence_api(self) -> str:
        return f"{self.base_url}/wiki/api/v2"

    @property
    def confluence_v1(self) -> str:
        # v1 still required for some operations (search, attachments)
        return f"{self.base_url}/wiki/rest/api"


def load_config() -> AtlassianConfig:
    env = _load_env()
    return AtlassianConfig(
        email=env["ATLASSIAN_EMAIL"],
        token=env["ATLASSIAN_API_TOKEN"],
        base_url=env["ATLASSIAN_BASE_URL"],
    )


class AtlassianClient:
    """Minimal REST wrapper with retries + rate limiting."""

    def __init__(self, cfg: AtlassianConfig, requests_per_second: float = 5.0):
        self.cfg = cfg
        self.auth = HTTPBasicAuth(cfg.email, cfg.token)
        self._min_interval = 1.0 / requests_per_second
        self._last_call = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def request(
        self,
        method: str,
        url: str,
        *,
        json_body: Any = None,
        params: dict | None = None,
        max_retries: int = 4,
    ) -> requests.Response:
        self._wait()
        headers = {"Accept": "application/json"}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        attempt = 0
        while True:
            attempt += 1
            resp = requests.request(
                method,
                url,
                auth=self.auth,
                headers=headers,
                json=json_body,
                params=params,
                timeout=30,
            )
            if resp.status_code == 429 and attempt <= max_retries:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                time.sleep(retry_after)
                continue
            if 500 <= resp.status_code < 600 and attempt <= max_retries:
                time.sleep(2 ** attempt)
                continue
            return resp

    # ---- High-level helpers ----------------------------------------------

    def jira_get(self, path: str, **kw) -> dict:
        r = self.request("GET", f"{self.cfg.jira_api}{path}", **kw)
        r.raise_for_status()
        return r.json()

    def jira_post(self, path: str, body: Any) -> dict:
        r = self.request("POST", f"{self.cfg.jira_api}{path}", json_body=body)
        if r.status_code >= 400:
            raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text[:500]}")
        return r.json() if r.text else {}

    def confluence_get(self, path: str, **kw) -> dict:
        r = self.request("GET", f"{self.cfg.confluence_api}{path}", **kw)
        r.raise_for_status()
        return r.json()

    def confluence_post(self, path: str, body: Any) -> dict:
        r = self.request("POST", f"{self.cfg.confluence_api}{path}", json_body=body)
        if r.status_code >= 400:
            raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text[:500]}")
        return r.json() if r.text else {}


def pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str)


def get_state_dir() -> Path:
    p = Path(__file__).resolve().parent / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p
