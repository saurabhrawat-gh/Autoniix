"""Shared Prometheus instrumentation for every FastAPI service.

Usage in any ``main.py``::

    from fastapi import FastAPI
    from observability.metrics import instrument_app

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

    # --- Compatibility shim for prometheus_fastapi_instrumentator 8.x ---
    # v8 crashes with AttributeError on _IncludedRouter objects (routers added
    # via app.include_router()) because it calls route.path on them directly.
    # Patch the private helper to skip non-Route objects gracefully.
    try:
        import prometheus_fastapi_instrumentator.routing as _pfi_routing

        _orig_get_route_name = _pfi_routing.get_route_name

        def _safe_get_route_name(request: Any) -> str:  # type: ignore[override]
            try:
                return _orig_get_route_name(request)
            except AttributeError:
                return "unknown"

        _pfi_routing.get_route_name = _safe_get_route_name  # type: ignore[assignment]
    except Exception:
        pass
    # --- End shim ---

except Exception:  # pragma: no cover - optional dep, must not crash app
    _HAS_INSTRUMENTATOR = False
    Counter = Histogram = None  # type: ignore


# Pipeline-wide custom metrics
# These live in a single registry so every service can ``inc()`` them.
# The label set is intentionally small (service, channel, phase, status)
# to keep cardinality bounded.

if _HAS_INSTRUMENTATOR:
    from prometheus_client import Gauge

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
    RENDER_OUTCOMES = Counter(
        "render_outcomes_total",
        "Remotion render outcomes (qc_pass / qc_fail / timeout / other).",
        labelnames=("composition", "outcome"),
    )

    # Budget gauges (updated every 60 s by BFF background task)
    YT_DAILY_API_SPEND = Gauge(
        "yt_daily_api_spend_usd",
        "Today's total API spend in USD for a channel.",
        labelnames=("channel_id",),
    )
    YT_DAILY_BUDGET_LIMIT = Gauge(
        "yt_daily_budget_limit_usd",
        "Configured daily API budget cap in USD for a channel.",
        labelnames=("channel_id",),
    )

    # Video pipeline counters (incremented by the Temporal worker)
    YT_VIDEOS_STARTED = Counter(
        "yt_videos_started_total",
        "Video production jobs started.",
        labelnames=("channel_id", "content_mode"),
    )
    YT_VIDEOS_COMPLETED = Counter(
        "yt_videos_completed_total",
        "Video production jobs delivered successfully.",
        labelnames=("channel_id", "content_mode"),
    )

    # QC counters (incremented at each quality gate)
    YT_QC_CHECKED = Counter(
        "yt_qc_checked_total",
        "Quality gate evaluations run.",
        labelnames=("service", "gate"),
    )
    YT_QC_FAILED = Counter(
        "yt_qc_failed_total",
        "Quality gate evaluations that did not meet threshold.",
        labelnames=("service", "gate"),
    )

    # AE-75 — provider health beat metrics
    PROVIDER_HEALTH_UNHEALTHY = Counter(
        "provider_credentials_unhealthy_total",
        "Number of provider credentials that failed their health check.",
        labelnames=("category",),
    )
    PROVIDER_HEALTH_CHECK_DURATION = Histogram(
        "provider_health_check_duration_ms",
        "Duration of a single provider credential health check in milliseconds.",
        labelnames=("provider_name",),
        buckets=(10, 50, 100, 250, 500, 1000, 2000, 5000, 10000),
    )

    # AE-520 — Token compression metrics
    LLM_COMPRESSION_SAVINGS = Counter(
        "llm_compression_tokens_saved_total",
        "Total tokens saved by the compression layer.",
        labelnames=("tier", "engine"),
    )
    LLM_COMPRESSION_PASSES = Counter(
        "llm_compression_passes_total",
        "Total compression passes applied.",
        labelnames=("tier", "engine"),
    )
else:  # pragma: no cover

    class _Noop:
        def labels(self, *_a: Any, **_kw: Any) -> "_Noop":
            return self

        def inc(self, *_a: Any, **_kw: Any) -> None:
            return None

        def observe(self, *_a: Any, **_kw: Any) -> None:
            return None

        def set(self, *_a: Any, **_kw: Any) -> None:
            return None

    PIPELINE_PHASE_TOTAL = _Noop()  # type: ignore
    PIPELINE_PHASE_DURATION = _Noop()  # type: ignore
    QUALITY_GATE_BLOCKS = _Noop()  # type: ignore
    RENDER_OUTCOMES = _Noop()  # type: ignore
    YT_DAILY_API_SPEND = _Noop()  # type: ignore
    YT_DAILY_BUDGET_LIMIT = _Noop()  # type: ignore
    YT_VIDEOS_STARTED = _Noop()  # type: ignore
    YT_VIDEOS_COMPLETED = _Noop()  # type: ignore
    YT_QC_CHECKED = _Noop()  # type: ignore
    YT_QC_FAILED = _Noop()  # type: ignore
    PROVIDER_HEALTH_UNHEALTHY = _Noop()  # type: ignore
    PROVIDER_HEALTH_CHECK_DURATION = _Noop()  # type: ignore
    LLM_COMPRESSION_SAVINGS = _Noop()  # type: ignore
    LLM_COMPRESSION_PASSES = _Noop()  # type: ignore


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
