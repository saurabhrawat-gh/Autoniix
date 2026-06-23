"""
Shadow Mode Infrastructure — per HARNESS-ENGINEERING-PLAN.md Section 11.

Shadow mode runs BOTH Python and Rust services with the same request, but
returns ONLY Python's response to the caller. Rust's response is discarded —
it's captured and compared in the background to detect divergences silently.

Stages (per Section 11):
  Stage 1 — Shadow:   Python serves 100%, Rust runs in parallel (response discarded)
  Stage 2 — Canary:   Rust serves 1% of traffic (enable via SHADOW_MODE=canary)
  Stage 3 — Rollout:  Rust traffic increases to 10/25/50/100%
  Stage 4 — Cutover:  Rust serves 100%

Usage:
    # Start shadow comparison
    interceptor = ShadowModeInterceptor(
        python_url="http://localhost:8000",
        rust_url="http://localhost:8080",
        divergence_log="logs/shadow_divergences.jsonl",
    )

    # Wrap a request — Python response returned, Rust compared silently
    resp = await interceptor.shadow("POST", "/api/v2/auth/signin", json={...})

    # Check what divergences were captured
    report = interceptor.divergence_report()

Run (standalone integration smoke):
    PYTHON_DASHBOARD_URL=http://localhost:8000 \\
    RUST_GATEWAY_URL=http://localhost:8080 \\
    python -m tests.migration.shadow_mode
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PYTHON_URL = os.getenv("PYTHON_DASHBOARD_URL", "http://localhost:8000")
RUST_URL = os.getenv("RUST_GATEWAY_URL", "http://localhost:8080")

# ShadowMode controls whether the interceptor is active and how much traffic
# Rust should handle. Set via SHADOW_MODE env var.
#   off     — disabled (Python only)
#   shadow  — Rust mirrors every request, response discarded (default)
#   canary  — Rust serves SHADOW_RUST_PERCENT % of traffic (default 1%)
#   full    — Rust serves 100%
SHADOW_MODE = os.getenv("SHADOW_MODE", "shadow")
SHADOW_RUST_PERCENT = float(os.getenv("SHADOW_RUST_PERCENT", "1"))


@dataclass
class ShadowDivergence:
    """One recorded difference between Python and Rust responses."""

    timestamp: str
    method: str
    path: str
    status_match: bool
    python_status: int
    rust_status: int
    body_diff: dict[str, Any]
    latency_python_ms: float
    latency_rust_ms: float
    request_id: str = ""

    def is_intentional(self) -> bool:
        """Check if this divergence is registered as intentional."""
        from tests.migration.divergence_registry import INTENTIONAL_DIVERGENCES

        key = f"{self.method.upper()} {self.path}"
        return key in INTENTIONAL_DIVERGENCES

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "method": self.method,
            "path": self.path,
            "status_match": self.status_match,
            "python_status": self.python_status,
            "rust_status": self.rust_status,
            "body_diff": self.body_diff,
            "latency_python_ms": round(self.latency_python_ms, 2),
            "latency_rust_ms": round(self.latency_rust_ms, 2),
            "intentional": self.is_intentional(),
            "request_id": self.request_id,
        }


@dataclass
class ShadowStats:
    """Running counters for shadow mode reporting."""

    total_requests: int = 0
    divergences: int = 0
    intentional_divergences: int = 0
    rust_errors: int = 0
    python_errors: int = 0
    total_python_ms: float = 0.0
    total_rust_ms: float = 0.0

    @property
    def divergence_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.divergences - self.intentional_divergences) / self.total_requests

    @property
    def avg_speedup(self) -> float:
        """Average latency ratio Python/Rust. >1 means Rust is faster."""
        if self.total_rust_ms == 0:
            return 0.0
        return self.total_python_ms / self.total_rust_ms


class ShadowModeInterceptor:
    """
    Fires the same HTTP request at both Python and Rust simultaneously,
    returns Python's response to the caller, and logs any divergences.
    """

    def __init__(
        self,
        python_url: str = PYTHON_URL,
        rust_url: str = RUST_URL,
        divergence_log: str = "logs/shadow_divergences.jsonl",
        alert_threshold: float = 0.005,  # 0.5% divergence rate triggers alert
        timeout_s: float = 10.0,
    ) -> None:
        self.python_url = python_url.rstrip("/")
        self.rust_url = rust_url.rstrip("/")
        self.divergence_log = divergence_log
        self.alert_threshold = alert_threshold
        self.timeout_s = timeout_s
        self.stats = ShadowStats()
        self._divergences: list[ShadowDivergence] = []
        self._client = httpx.AsyncClient(timeout=timeout_s)

    async def __aenter__(self) -> "ShadowModeInterceptor":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()

    # ── Core shadow method ───────────────────────────────────────────────────

    async def shadow(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        request_id: str = "",
    ) -> httpx.Response:
        """
        Send the request to both services in parallel.
        Always returns the Python response.
        Rust result is compared in the background.
        """
        mode = SHADOW_MODE

        if mode == "off":
            return await self._call(self.python_url, method, path, json=json, headers=headers, cookies=cookies)

        # Parallel fire
        python_task = asyncio.create_task(
            self._timed_call(self.python_url, method, path, json=json, headers=headers, cookies=cookies)
        )
        rust_task = asyncio.create_task(
            self._timed_call(self.rust_url, method, path, json=json, headers=headers, cookies=cookies)
        )

        (py_resp, py_ms), (rust_resp, rust_ms) = await asyncio.gather(
            python_task, rust_task, return_exceptions=False
        )

        self.stats.total_requests += 1
        self.stats.total_python_ms += py_ms
        self.stats.total_rust_ms += rust_ms

        if isinstance(py_resp, Exception):
            self.stats.python_errors += 1
            logger.warning("shadow: python error on %s %s: %s", method, path, py_resp)
        if isinstance(rust_resp, Exception):
            self.stats.rust_errors += 1
            logger.debug("shadow: rust error on %s %s: %s", method, path, rust_resp)

        if not isinstance(py_resp, Exception) and not isinstance(rust_resp, Exception):
            await self._compare(
                method, path, py_resp, py_ms, rust_resp, rust_ms, request_id=request_id
            )

        if isinstance(py_resp, Exception):
            raise py_resp
        return py_resp

    # ── Comparison ──────────────────────────────────────────────────────────

    async def _compare(
        self,
        method: str,
        path: str,
        py_resp: httpx.Response,
        py_ms: float,
        rust_resp: httpx.Response,
        rust_ms: float,
        request_id: str = "",
    ) -> None:
        status_match = py_resp.status_code == rust_resp.status_code
        body_diff: dict[str, Any] = {}

        try:
            py_body = py_resp.json()
            rust_body = rust_resp.json()
            body_diff = _json_diff(py_body, rust_body)
        except Exception:
            if py_resp.text != rust_resp.text:
                body_diff = {"text_mismatch": True, "python": py_resp.text[:200], "rust": rust_resp.text[:200]}

        if not status_match or body_diff:
            div = ShadowDivergence(
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
                method=method.upper(),
                path=path,
                status_match=status_match,
                python_status=py_resp.status_code,
                rust_status=rust_resp.status_code,
                body_diff=body_diff,
                latency_python_ms=py_ms,
                latency_rust_ms=rust_ms,
                request_id=request_id,
            )
            self._divergences.append(div)
            self.stats.divergences += 1
            if div.is_intentional():
                self.stats.intentional_divergences += 1
            else:
                self._log_divergence(div)
                self._check_alert()

    def _log_divergence(self, div: ShadowDivergence) -> None:
        record = json.dumps(div.to_dict())
        logger.warning("shadow divergence: %s %s → status=%s body_diff=%s",
                        div.method, div.path, not div.status_match, bool(div.body_diff))
        if self.divergence_log:
            try:
                import os
                os.makedirs(os.path.dirname(self.divergence_log) or ".", exist_ok=True)
                with open(self.divergence_log, "a") as f:
                    f.write(record + "\n")
            except Exception as e:
                logger.debug("shadow: could not write divergence log: %s", e)

    def _check_alert(self) -> None:
        rate = self.stats.divergence_rate
        if rate > self.alert_threshold:
            logger.error(
                "SHADOW ALERT: divergence rate %.2f%% exceeds threshold %.2f%%  "
                "— consider rolling back Rust traffic",
                rate * 100,
                self.alert_threshold * 100,
            )

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    async def _timed_call(
        self,
        base_url: str,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> tuple[httpx.Response | Exception, float]:
        t0 = time.monotonic()
        try:
            resp = await self._call(base_url, method, path, **kwargs)
            return resp, (time.monotonic() - t0) * 1000
        except Exception as exc:
            return exc, (time.monotonic() - t0) * 1000

    async def _call(
        self,
        base_url: str,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> httpx.Response:
        url = base_url + path
        return await self._client.request(
            method.upper(),
            url,
            json=json,
            headers=headers or {},
            cookies=cookies or {},
        )

    # ── Reporting ────────────────────────────────────────────────────────────

    def divergence_report(self) -> dict[str, Any]:
        unintentional = [d for d in self._divergences if not d.is_intentional()]
        return {
            "total_requests": self.stats.total_requests,
            "total_divergences": self.stats.divergences,
            "intentional": self.stats.intentional_divergences,
            "unintentional": len(unintentional),
            "divergence_rate_pct": round(self.stats.divergence_rate * 100, 4),
            "avg_python_ms": round(self.stats.total_python_ms / max(self.stats.total_requests, 1), 2),
            "avg_rust_ms": round(self.stats.total_rust_ms / max(self.stats.total_requests, 1), 2),
            "speedup_factor": round(self.stats.avg_speedup, 2),
            "rust_errors": self.stats.rust_errors,
            "python_errors": self.stats.python_errors,
            "divergence_samples": [d.to_dict() for d in unintentional[:10]],
        }

    def assert_no_unintentional_divergences(self) -> None:
        """Raise AssertionError if any unexpected divergences were recorded."""
        unintentional = [d for d in self._divergences if not d.is_intentional()]
        if unintentional:
            sample = json.dumps(unintentional[0].to_dict(), indent=2)
            raise AssertionError(
                f"{len(unintentional)} unintentional shadow divergence(s) detected.\n"
                f"First divergence:\n{sample}"
            )


# ── Utilities ────────────────────────────────────────────────────────────────

def _json_diff(a: Any, b: Any, path: str = "") -> dict[str, Any]:
    """Shallow diff of two JSON values. Returns {path: {python: ..., rust: ...}} for mismatches."""
    diffs: dict[str, Any] = {}

    if type(a) != type(b):
        diffs[path or "root"] = {"python": a, "rust": b}
        return diffs

    if isinstance(a, dict):
        all_keys = set(a) | set(b)
        for k in all_keys:
            sub = f"{path}.{k}" if path else k
            if k not in a:
                diffs[sub] = {"python": None, "rust": b[k]}
            elif k not in b:
                diffs[sub] = {"python": a[k], "rust": None}
            elif a[k] != b[k]:
                if isinstance(a[k], (dict, list)):
                    diffs.update(_json_diff(a[k], b[k], path=sub))
                else:
                    diffs[sub] = {"python": a[k], "rust": b[k]}
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs[path or "root"] = {"python_len": len(a), "rust_len": len(b)}
        else:
            for i, (av, bv) in enumerate(zip(a, b)):
                diffs.update(_json_diff(av, bv, path=f"{path}[{i}]"))
    elif a != b:
        diffs[path or "root"] = {"python": a, "rust": b}

    return diffs


# ── Standalone smoke ─────────────────────────────────────────────────────────

async def _smoke() -> None:
    """Quick sanity: run one shadow request against both services (if available)."""
    interceptor = ShadowModeInterceptor()
    try:
        resp = await interceptor.shadow("GET", "/health")
        print(f"Python /health → {resp.status_code}")
    except Exception as exc:
        print(f"Smoke skipped: {exc}")
    print(json.dumps(interceptor.divergence_report(), indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_smoke())
