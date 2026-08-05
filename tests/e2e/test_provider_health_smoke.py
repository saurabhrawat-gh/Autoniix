"""AE-34 e2e: Provider health smoke gate against the running dashboard.

Requires ``YT_E2E_DASHBOARD_URL`` (e.g. ``http://localhost:8020``) and
``YT_E2E_API_TOKEN`` (owner JWT) to be set.

Typical invocation::

    YT_E2E_DASHBOARD_URL=http://localhost:8020 \
    YT_E2E_API_TOKEN=<jwt> \
    pytest tests/e2e/test_provider_health_smoke.py -v

The test:
  1. Fetches all enabled credentials via GET /api/v2/providers/credentials
  2. POSTs to /credentials/{id}/test for each enabled credential
  3. Asserts that the render-critical categories (llm, tts, storage) each
     have at least one credential that passes health_check
  4. Fails the smoke gate with a detailed report if any required category
     has zero healthy credentials.
"""

from __future__ import annotations

import os

import httpx
import pytest

DASHBOARD_URL = os.getenv("YT_E2E_DASHBOARD_URL")
API_TOKEN = os.getenv("YT_E2E_API_TOKEN")

pytestmark = pytest.mark.skipif(
    not DASHBOARD_URL or not API_TOKEN,
    reason="set YT_E2E_DASHBOARD_URL and YT_E2E_API_TOKEN to run provider health smoke",
)

REQUIRED_HEALTHY_CATEGORIES = {"llm", "tts", "storage"}


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


def test_provider_health_smoke():
    """Gate: each pipeline-critical category has ≥1 healthy provider."""
    with httpx.Client(base_url=DASHBOARD_URL, timeout=30, headers=_headers()) as client:
        resp = client.get("/api/v2/providers/credentials")
        resp.raise_for_status()
        credentials = resp.json().get("data", [])

    if not credentials:
        pytest.skip("No credentials configured — skipping provider health smoke")

    enabled = [c for c in credentials if c.get("enabled", True)]
    healthy_categories: set[str] = set()
    results: list[dict] = []

    with httpx.Client(base_url=DASHBOARD_URL, timeout=30, headers=_headers()) as client:
        for cred in enabled:
            cid = cred["id"]
            cat = cred["category"]
            try:
                resp = client.post(f"/api/v2/providers/credentials/{cid}/test")
                ok = resp.json().get("ok", False) if resp.status_code == 200 else False
            except Exception as exc:
                ok = False
                results.append(
                    {"id": cid, "category": cat, "provider": cred.get("provider_name"), "ok": False, "error": str(exc)}
                )
                continue

            results.append(
                {
                    "id": cid,
                    "category": cat,
                    "provider": cred.get("provider_name"),
                    "ok": ok,
                    "latency_ms": resp.json().get("latency_ms") if resp.status_code == 200 else None,
                }
            )
            if ok:
                healthy_categories.add(cat)

    unhealthy_required = REQUIRED_HEALTHY_CATEGORIES - healthy_categories
    if unhealthy_required:
        report = "\n".join(
            f"  [{r['category']}/{r['provider']}] ok={r['ok']}"
            + (f" error={r.get('error')!r}" if not r["ok"] else f" latency={r.get('latency_ms')}ms")
            for r in results
        )
        pytest.fail(
            f"Provider health smoke FAILED.\n"
            f"Required categories with NO healthy credential: {unhealthy_required}\n\n"
            f"Results:\n{report}"
        )
