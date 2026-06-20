"""
Performance comparison harness — benchmarks Python vs Rust endpoints
and generates a Markdown report.

Per HARNESS-ENGINEERING-PLAN.md Week 4 Day 3.

Usage:
    harness = PerformanceComparison()
    result = await harness.benchmark_both("/api/v2/auth/signin", payload={...})
    print(result.speedup_factor, "× faster")

    report = harness.generate_report()
    Path("perf_report.md").write_text(report)
"""
from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

RUST_GATEWAY_URL = "http://localhost:8080"
PYTHON_DASHBOARD_URL = "http://localhost:8000"


@dataclass
class EndpointResult:
    service: str
    endpoint: str
    method: str
    samples: list[float] = field(default_factory=list)  # latencies in ms

    @property
    def p50(self) -> float:
        return statistics.median(self.samples) if self.samples else 0.0

    @property
    def p95(self) -> float:
        if not self.samples:
            return 0.0
        sorted_s = sorted(self.samples)
        idx = int(len(sorted_s) * 0.95)
        return sorted_s[min(idx, len(sorted_s) - 1)]

    @property
    def p99(self) -> float:
        if not self.samples:
            return 0.0
        sorted_s = sorted(self.samples)
        idx = int(len(sorted_s) * 0.99)
        return sorted_s[min(idx, len(sorted_s) - 1)]

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0


@dataclass
class ComparisonResult:
    python: EndpointResult
    rust: EndpointResult

    @property
    def speedup_factor(self) -> float:
        """How many times faster Rust is vs Python (p95)."""
        if self.rust.p95 == 0:
            return 0.0
        return self.python.p95 / self.rust.p95

    @property
    def rust_wins(self) -> bool:
        return self.rust.p95 < self.python.p95


class PerformanceComparison:
    """
    Benchmarks two services on the same logical operation
    and produces a comparison report.
    """

    def __init__(
        self,
        python_url: str = PYTHON_DASHBOARD_URL,
        rust_url: str = RUST_GATEWAY_URL,
        warmup_requests: int = 5,
        sample_count: int = 50,
        concurrency: int = 5,
    ):
        self.python_url = python_url
        self.rust_url = rust_url
        self.warmup_requests = warmup_requests
        self.sample_count = sample_count
        self.concurrency = concurrency
        self._results: list[ComparisonResult] = []

    async def benchmark_both(
        self,
        python_path: str,
        rust_path: str,
        method: str = "POST",
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ComparisonResult:
        """Benchmark the same logical operation on both services."""
        logger.info(
            "perf.benchmark_start",
            python_path=python_path,
            rust_path=rust_path,
            samples=self.sample_count,
        )

        python_result = await self._benchmark_endpoint(
            self.python_url, python_path, method, payload, headers, "python"
        )
        rust_result = await self._benchmark_endpoint(
            self.rust_url, rust_path, method, payload, headers, "rust"
        )

        comparison = ComparisonResult(python=python_result, rust=rust_result)
        self._results.append(comparison)

        logger.info(
            "perf.benchmark_complete",
            python_p95_ms=f"{python_result.p95:.1f}",
            rust_p95_ms=f"{rust_result.p95:.1f}",
            speedup=f"{comparison.speedup_factor:.2f}x",
        )
        return comparison

    async def _benchmark_endpoint(
        self,
        base_url: str,
        path: str,
        method: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str] | None,
        service_name: str,
    ) -> EndpointResult:
        result = EndpointResult(service=service_name, endpoint=path, method=method)

        async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
            # Warmup
            for _ in range(self.warmup_requests):
                try:
                    await self._make_request(client, method, path, payload, headers)
                except Exception:
                    pass

            # Timed samples with controlled concurrency
            sem = asyncio.Semaphore(self.concurrency)

            async def timed_request() -> float | None:
                async with sem:
                    try:
                        start = time.perf_counter()
                        await self._make_request(client, method, path, payload, headers)
                        return (time.perf_counter() - start) * 1000.0
                    except Exception as e:
                        logger.warning("perf.request_failed", error=str(e))
                        return None

            tasks = [timed_request() for _ in range(self.sample_count)]
            times = await asyncio.gather(*tasks)
            result.samples = [t for t in times if t is not None]

        return result

    async def _make_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str] | None,
    ) -> httpx.Response:
        kwargs: dict[str, Any] = {}
        if payload:
            kwargs["json"] = payload
        if headers:
            kwargs["headers"] = headers
        return await client.request(method, path, **kwargs)

    def generate_report(self) -> str:
        """Generate a Markdown performance comparison report."""
        lines = [
            "# Performance Comparison: Python vs Rust",
            "",
            "Per HARNESS-ENGINEERING-PLAN.md Week 4 Day 3.",
            "",
            "| Endpoint | Python p50 | Python p95 | Rust p50 | Rust p95 | Speedup |",
            "|----------|-----------|-----------|---------|---------|---------|",
        ]

        for r in self._results:
            speedup = r.speedup_factor
            emoji = "🟢" if r.rust_wins else "🔴"
            lines.append(
                f"| `{r.rust.endpoint}` "
                f"| {r.python.p50:.1f}ms "
                f"| {r.python.p95:.1f}ms "
                f"| {r.rust.p50:.1f}ms "
                f"| {r.rust.p95:.1f}ms "
                f"| {emoji} {speedup:.2f}× |"
            )

        lines += [
            "",
            "## Summary",
            "",
            f"- **Total endpoints benchmarked:** {len(self._results)}",
            f"- **Rust faster in:** {sum(1 for r in self._results if r.rust_wins)}/{len(self._results)}",
            "",
            "## Targets",
            "",
            "| Endpoint | Target p95 |",
            "|----------|-----------|",
            "| signup   | < 30ms    |",
            "| signin   | < 25ms    |",
            "| refresh  | < 10ms    |",
            "| /me      | < 5ms     |",
            "",
            "_Generated by `tests/harnesses/perf_comparison.py`_",
        ]

        return "\n".join(lines)
