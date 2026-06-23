"""
Production Equivalence Sampler — per HARNESS-ENGINEERING-PLAN.md Section 12.

Runs continuously in production, sampling 0.1% of read-only requests and
comparing Python vs Rust responses. Logs divergences and alerts if the
divergence rate exceeds 0.5%.

Design:
  - Fires READ-ONLY (GET) requests at both services with the same payload
  - Never writes to the database in sampling mode
  - Skips endpoints that require write operations or side effects
  - Divergence threshold: 0.5% → log ERROR + (optionally) send Sentry alert

Configuration (env vars):
  PYTHON_DASHBOARD_URL   — default http://localhost:8000
  RUST_GATEWAY_URL       — default http://localhost:8080
  SAMPLER_RATE           — fraction of requests to sample (default 0.001 = 0.1%)
  SAMPLER_INTERVAL_S     — seconds between sampling rounds (default 60)
  SAMPLER_TOKEN          — JWT used for authenticated endpoint sampling
  SENTRY_DSN             — if set, alerts are sent to Sentry
  DIVERGENCE_LOG         — path to JSONL divergence log (default logs/prod_divergences.jsonl)

Run:
    PYTHON_DASHBOARD_URL=http://localhost:8000 \\
    RUST_GATEWAY_URL=http://localhost:8080 \\
    SAMPLER_TOKEN=<your-jwt> \\
    python -m tests.migration.prod_equivalence_sampler
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PYTHON_URL = os.getenv("PYTHON_DASHBOARD_URL", "http://localhost:8000")
RUST_URL = os.getenv("RUST_GATEWAY_URL", "http://localhost:8080")
SAMPLER_RATE = float(os.getenv("SAMPLER_RATE", "0.001"))
SAMPLER_INTERVAL_S = float(os.getenv("SAMPLER_INTERVAL_S", "60"))
SAMPLER_TOKEN = os.getenv("SAMPLER_TOKEN", "")
DIVERGENCE_LOG = os.getenv("DIVERGENCE_LOG", "logs/prod_divergences.jsonl")
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
ALERT_THRESHOLD = float(os.getenv("SAMPLER_ALERT_THRESHOLD", "0.005"))  # 0.5%

# Read-only endpoints eligible for sampling.
# These are safe to fire in production — they never mutate state.
SAMPLE_ENDPOINTS: list[dict[str, Any]] = [
    {
        "method": "GET",
        "python_path": "/api/v2/me",
        "rust_path": "/api/v2/me",
        "auth": True,
        "compare_fields": ["email", "display_name", "role", "global_role"],
    },
    {
        "method": "GET",
        "python_path": "/api/v2/auth/mode",
        "rust_path": "/api/v2/auth/mode",
        "auth": False,
        "compare_fields": ["v2_enabled", "legacy_enabled"],
    },
    {
        "method": "GET",
        "python_path": "/health",
        "rust_path": "/health/live",
        "auth": False,
        "compare_fields": [],  # status code only
    },
]


@dataclass
class SamplerRun:
    """One completed comparison round."""

    timestamp: str
    endpoint: str
    python_status: int
    rust_status: int
    status_match: bool
    field_diffs: dict[str, Any]
    latency_python_ms: float
    latency_rust_ms: float
    error: str = ""

    @property
    def diverged(self) -> bool:
        return not self.status_match or bool(self.field_diffs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "endpoint": self.endpoint,
            "python_status": self.python_status,
            "rust_status": self.rust_status,
            "status_match": self.status_match,
            "field_diffs": self.field_diffs,
            "latency_python_ms": round(self.latency_python_ms, 2),
            "latency_rust_ms": round(self.latency_rust_ms, 2),
            "error": self.error,
        }


@dataclass
class SamplerStats:
    total: int = 0
    divergences: int = 0
    errors: int = 0
    total_python_ms: float = 0.0
    total_rust_ms: float = 0.0
    by_endpoint: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def divergence_rate(self) -> float:
        return (self.divergences / self.total) if self.total else 0.0

    def record(self, endpoint: str, diverged: bool, python_ms: float, rust_ms: float) -> None:
        self.total += 1
        self.total_python_ms += python_ms
        self.total_rust_ms += rust_ms
        ep = self.by_endpoint.setdefault(endpoint, {"total": 0, "divergences": 0})
        ep["total"] += 1
        if diverged:
            self.divergences += 1
            ep["divergences"] += 1

    def summary(self) -> dict[str, Any]:
        return {
            "total_samples": self.total,
            "divergences": self.divergences,
            "divergence_rate_pct": round(self.divergence_rate * 100, 4),
            "errors": self.errors,
            "avg_python_ms": round(self.total_python_ms / max(self.total, 1), 2),
            "avg_rust_ms": round(self.total_rust_ms / max(self.total, 1), 2),
            "speedup_factor": round(
                self.total_python_ms / max(self.total_rust_ms, 0.001), 2
            ),
            "by_endpoint": self.by_endpoint,
        }


class ProductionEquivalenceSampler:
    """
    Continuously samples read-only endpoints in production, comparing Python
    and Rust responses. Alerts when divergence rate exceeds the threshold.
    """

    def __init__(
        self,
        python_url: str = PYTHON_URL,
        rust_url: str = RUST_URL,
        sample_rate: float = SAMPLER_RATE,
        token: str = SAMPLER_TOKEN,
        divergence_log: str = DIVERGENCE_LOG,
        alert_threshold: float = ALERT_THRESHOLD,
        timeout_s: float = 8.0,
    ) -> None:
        self.python_url = python_url.rstrip("/")
        self.rust_url = rust_url.rstrip("/")
        self.sample_rate = sample_rate
        self.token = token
        self.divergence_log = divergence_log
        self.alert_threshold = alert_threshold
        self.timeout_s = timeout_s
        self.stats = SamplerStats()
        self._client = httpx.AsyncClient(timeout=timeout_s)
        self._running = False

    async def __aenter__(self) -> "ProductionEquivalenceSampler":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()

    # ── Main loop ────────────────────────────────────────────────────────────

    async def run_forever(self) -> None:
        """Run sampling loop indefinitely. Cancel the task to stop."""
        self._running = True
        logger.info(
            "sampler: started — rate=%.3f%% interval=%.0fs python=%s rust=%s",
            self.sample_rate * 100,
            SAMPLER_INTERVAL_S,
            self.python_url,
            self.rust_url,
        )
        while self._running:
            try:
                await self._sample_round()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("sampler: round error: %s", exc)
            await asyncio.sleep(SAMPLER_INTERVAL_S)

    async def run_once(self) -> dict[str, Any]:
        """Run exactly one sampling round and return the summary."""
        await self._sample_round()
        return self.stats.summary()

    def stop(self) -> None:
        self._running = False

    # ── Sampling round ───────────────────────────────────────────────────────

    async def _sample_round(self) -> None:
        tasks = []
        for endpoint in SAMPLE_ENDPOINTS:
            if random.random() > self.sample_rate:
                continue
            tasks.append(asyncio.create_task(self._sample_endpoint(endpoint)))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, SamplerRun):
                    if result.diverged:
                        self._log_divergence(result)
                        self._maybe_alert()

    async def _sample_endpoint(self, endpoint: dict[str, Any]) -> SamplerRun:
        method = endpoint["method"]
        python_path = endpoint["python_path"]
        rust_path = endpoint["rust_path"]
        compare_fields: list[str] = endpoint.get("compare_fields", [])
        auth = endpoint.get("auth", False)

        headers: dict[str, str] = {}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif auth and not self.token:
            return SamplerRun(
                timestamp=_now(),
                endpoint=python_path,
                python_status=0,
                rust_status=0,
                status_match=True,
                field_diffs={},
                latency_python_ms=0.0,
                latency_rust_ms=0.0,
                error="SKIP: no SAMPLER_TOKEN for authenticated endpoint",
            )

        py_result, py_ms = await self._timed_get(self.python_url, python_path, headers)
        rust_result, rust_ms = await self._timed_get(self.rust_url, rust_path, headers)

        self.stats.total_python_ms += py_ms
        self.stats.total_rust_ms += rust_ms

        error = ""
        python_status = 0
        rust_status = 0
        status_match = False
        field_diffs: dict[str, Any] = {}

        if isinstance(py_result, Exception) or isinstance(rust_result, Exception):
            self.stats.errors += 1
            error = f"py={py_result!r} rust={rust_result!r}"
            run = SamplerRun(
                timestamp=_now(),
                endpoint=python_path,
                python_status=0,
                rust_status=0,
                status_match=False,
                field_diffs={},
                latency_python_ms=py_ms,
                latency_rust_ms=rust_ms,
                error=error,
            )
            self.stats.record(python_path, diverged=True, python_ms=py_ms, rust_ms=rust_ms)
            return run

        python_status = py_result.status_code
        rust_status = rust_result.status_code
        status_match = python_status == rust_status

        if status_match and compare_fields:
            try:
                py_body = py_result.json()
                rust_body = rust_result.json()
                for f in compare_fields:
                    pv = _nested_get(py_body, f)
                    rv = _nested_get(rust_body, f)
                    if pv != rv:
                        field_diffs[f] = {"python": pv, "rust": rv}
            except Exception as exc:
                error = f"body parse error: {exc}"

        run = SamplerRun(
            timestamp=_now(),
            endpoint=python_path,
            python_status=python_status,
            rust_status=rust_status,
            status_match=status_match,
            field_diffs=field_diffs,
            latency_python_ms=py_ms,
            latency_rust_ms=rust_ms,
            error=error,
        )
        self.stats.record(python_path, diverged=run.diverged, python_ms=py_ms, rust_ms=rust_ms)
        return run

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    async def _timed_get(
        self,
        base_url: str,
        path: str,
        headers: dict[str, str],
    ) -> tuple[httpx.Response | Exception, float]:
        t0 = time.monotonic()
        try:
            resp = await self._client.get(base_url + path, headers=headers)
            return resp, (time.monotonic() - t0) * 1000
        except Exception as exc:
            return exc, (time.monotonic() - t0) * 1000

    # ── Alerting + logging ───────────────────────────────────────────────────

    def _log_divergence(self, run: SamplerRun) -> None:
        record = json.dumps(run.to_dict())
        logger.warning(
            "sampler divergence: %s status_match=%s fields=%s",
            run.endpoint,
            run.status_match,
            list(run.field_diffs.keys()),
        )
        if self.divergence_log:
            try:
                os.makedirs(os.path.dirname(self.divergence_log) or ".", exist_ok=True)
                with open(self.divergence_log, "a") as fh:
                    fh.write(record + "\n")
            except Exception as exc:
                logger.debug("sampler: could not write log: %s", exc)

    def _maybe_alert(self) -> None:
        rate = self.stats.divergence_rate
        if rate > self.alert_threshold:
            msg = (
                f"PROD SAMPLER ALERT: divergence rate {rate*100:.2f}% "
                f"exceeds threshold {self.alert_threshold*100:.1f}% "
                f"({self.stats.divergences}/{self.stats.total} samples)"
            )
            logger.error(msg)
            if SENTRY_DSN:
                self._send_sentry_alert(msg)

    def _send_sentry_alert(self, message: str) -> None:
        try:
            import sentry_sdk  # type: ignore[import]

            sentry_sdk.capture_message(message, level="error")
        except ImportError:
            logger.debug("sampler: sentry_sdk not installed — skipping alert")
        except Exception as exc:
            logger.debug("sampler: sentry alert failed: %s", exc)


# ── Utilities ────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _nested_get(obj: Any, key: str) -> Any:
    """Navigate nested keys with dot notation. Returns None if missing."""
    for part in key.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


# ── Standalone entrypoint ────────────────────────────────────────────────────

async def _main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )
    async with ProductionEquivalenceSampler(sample_rate=1.0) as sampler:
        summary = await sampler.run_once()
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
