"""Load test: /api/fleet-health under concurrent fire.

Goal: prove the aggregator endpoint stays responsive under fan-in
pressure. The endpoint itself fans out to ~13 services + Remotion + DB,
so it's the most realistic single-endpoint load probe we have.

SLOs (production-mode):
* p50 latency < 1.0s
* p99 latency < 4.0s   (3s probe timeout + headroom)
* error rate <  1%

Skipped automatically unless ``DASHBOARD_BASE_URL`` + ``DASHBOARD_TOKEN``
are exported. See ``tests/load/README.md``.
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time

import pytest

_BASE = os.environ.get("DASHBOARD_BASE_URL")
_TOKEN = os.environ.get("DASHBOARD_TOKEN")

pytestmark = pytest.mark.skipif(
    not _BASE or not _TOKEN,
    reason="Set DASHBOARD_BASE_URL + DASHBOARD_TOKEN to run load tests.",
)


CONCURRENCY = 50  # simultaneous in-flight requests
TOTAL_REQUESTS = 200  # total over the test
PER_REQ_TIMEOUT_S = 8.0  # generous — endpoint's own probes cap at ~3.5s


@pytest.mark.asyncio
async def test_fleet_health_p99_under_4s():
    import httpx

    headers = {"Authorization": f"Bearer {_TOKEN}"}
    sem = asyncio.Semaphore(CONCURRENCY)
    latencies_ms: list[float] = []
    errors = 0

    async with httpx.AsyncClient(base_url=_BASE, timeout=PER_REQ_TIMEOUT_S, headers=headers) as cli:

        async def one():
            nonlocal errors
            async with sem:
                start = time.monotonic()
                try:
                    r = await cli.get("/api/fleet-health")
                    if r.status_code != 200:
                        errors += 1
                        return
                except Exception:
                    errors += 1
                    return
                latencies_ms.append((time.monotonic() - start) * 1000)

        await asyncio.gather(*[one() for _ in range(TOTAL_REQUESTS)])

    assert latencies_ms, "every request errored — service likely down"

    latencies_ms.sort()
    p50 = statistics.median(latencies_ms)
    p99 = latencies_ms[int(len(latencies_ms) * 0.99) - 1]
    error_rate = errors / TOTAL_REQUESTS

    print(
        f"\nfleet-health load: n={len(latencies_ms)} p50={p50:.0f}ms p99={p99:.0f}ms errors={errors} ({error_rate:.1%})"
    )

    assert p50 < 1_000, f"p50 latency {p50:.0f}ms breaches 1s SLO"
    assert p99 < 4_000, f"p99 latency {p99:.0f}ms breaches 4s SLO"
    assert error_rate < 0.01, f"error rate {error_rate:.1%} breaches 1% SLO"
