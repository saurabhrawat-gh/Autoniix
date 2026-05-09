"""Shared Prometheus instrumentation for every FastAPI service.

Usage in any ``main.py``::

    from fastapi import FastAPI
    from src.observability.metrics import instrument_app

    app = FastAPI(...)
    instrument_app(app, service_name="research")

Exposes ``GET /metrics`` (Prometheus text format) plus a small set of
pipeline-wide custom counters / histograms that all services share so
Grafana can render a single funnel dashboard without per-service queries.

Scrape target: ``http://<service>:<port>/metrics`` — wired via the
``prometheus`` container in ``docker-compose.yml`` (see Phase 2).
"""
from __future__ import annotations

from typing import Any

try:
    from prometheus_client import Counter, Histogram
    from prometheus_fastapi_instrumentator import Instrumentator, metrics
    _HAS_INSTRUMENTATOR = True
except Exception:  # pragma: no cover - optional dep, must not crash app
    _HAS_INSTRUMENTATOR = False
    Counter = Histogram = None  # type: ignore


# ── Pipeline-wide custom metrics ────────────────────────────────────
# These live in a single registry so every service can ``inc()`` them.
# The label set is intentionally small (service, channel, phase, status)
# to keep cardinality bounded.

if _HAS_INSTRUMENTATOR:
    PIPELINE_PHASE_TOTAL = Counter(
        "pipeline_phase_total",
        "Pipeline phase transitions (started/completed/failed).",
        labelnames=("service", "phase", "status"),
    )
    PIPELINE_PHASE_DURATION = Histogram(
        "pipeline_phase_duration_seconds",
        "Wall-clock duration of a pipeline phase.",
        labelnames=("service", "phase"),
        buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1800),
    )
    QUALITY_GATE_BLOCKS = Counter(
        "quality_gate_blocks_total",
        "Quality gates that blocked a video from advancing.",
        labelnames=("service", "gate"),
    )
    LLM_REQUESTS = Counter(
        "llm_requests_total",
        "LLM provider calls.",
        labelnames=("provider", "model", "status"),
    )
    LLM_COST_USD = Counter(
        "llm_cost_usd_total",
        "Cumulative USD cost of LLM calls.",
        labelnames=("provider", "model"),
    )
    RENDER_OUTCOMES = Counter(
        "render_outcomes_total",
        "Remotion render outcomes (qc_pass / qc_fail / timeout / other).",
        labelnames=("composition", "outcome"),
    )
else:  # pragma: no cover
    class _Noop:
        def labels(self, *_a: Any, **_kw: Any) -> "_Noop": return self
        def inc(self, *_a: Any, **_kw: Any) -> None: return None
        def observe(self, *_a: Any, **_kw: Any) -> None: return None
    PIPELINE_PHASE_TOTAL = _Noop()  # type: ignore
    PIPELINE_PHASE_DURATION = _Noop()  # type: ignore
    QUALITY_GATE_BLOCKS = _Noop()  # type: ignore
    LLM_REQUESTS = _Noop()  # type: ignore
    LLM_COST_USD = _Noop()  # type: ignore
    RENDER_OUTCOMES = _Noop()  # type: ignore


def instrument_app(app: Any, *, service_name: str) -> None:
    """Attach Prometheus middleware + ``/metrics`` route to a FastAPI app.

    Safe to call multiple times (idempotent on the same app instance).
    No-ops cleanly when the instrumentator dependency is missing so a
    partial install (e.g. CI image without obs deps) still boots.
    """
    if not _HAS_INSTRUMENTATOR:
        return

    instr = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        should_instrument_requests_inprogress=False,
        excluded_handlers=["/metrics", "/health"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="http_requests_inprogress",
        inprogress_labels=False,
    )
    # Default HTTP metrics (request count, latency histogram, in-progress).
    instr.add(metrics.default(metric_namespace=service_name.replace("-", "_")))
    instr.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
