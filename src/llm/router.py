"""LLM router — multi-provider fallback ladder with budget + circuit breaker.

Wraps :class:`src.providers.registry.ProviderRegistry` so the existing
provider implementations (``openai``, ``claude``, ``gemini``, ``mock_llm``)
are reused unchanged. Services that previously did::

    llm = ProviderRegistry.get("llm.script")
    result = await llm.complete(LLMRequest(...))

migrate to::

    from src.llm import route
    result = await route(
        category="llm.script",
        request=LLMRequest(...),
        channel_id=req.channel_id,
        content_id=req.content_id,
    )

What the router adds on top of a raw ``provider.complete`` call:

1. **Per-channel daily cost cap.** Before each call, sums today's
   ``api_usage.cost_usd`` for the channel. If ≥ ``channels.daily_cost_cap_usd``
   the call raises :class:`BudgetExceeded` (no fallback attempted — paying
   $0.001 to a different vendor still busts the budget).

2. **Provider ladder.** Each category has a ``primary -> fallbacks`` list
   driven by env vars, e.g. ``LLM_SCRIPT_LADDER=claude,openai,gemini``.
   On transient errors (timeout, 5xx, 429) we drop to the next provider in
   the ladder and retry. Permanent errors (4xx other than 429) raise
   immediately so the caller sees a real schema/auth bug.

3. **Circuit breaker.** Per (provider) rolling 5-min error rate; opens
   for 60 s when > 50 % errors over ≥ 6 samples. Open providers are
   skipped for the duration of the open window.

4. **Per-call telemetry.** Writes to ``api_usage`` (so cost rollup works)
   and emits Prometheus counters/histograms (``llm_requests_total``,
   ``llm_cost_usd_total``, ``llm_request_duration_seconds``).

The router is safe to use from concurrent tasks (per-process state is
guarded by an asyncio lock when needed; the Postgres rollup is the
authoritative cost source).
"""
from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Any, Iterable

import httpx
import structlog

from src.providers.llm.base import LLMRequest, LLMResult
from src.providers.registry import ProviderRegistry

logger = structlog.get_logger()


# ── Public exceptions ───────────────────────────────────────────────


class BudgetExceeded(RuntimeError):
    """Raised when a channel has hit its ``daily_cost_cap_usd``."""

    def __init__(self, channel_id: str, spent: float, cap: float):
        super().__init__(
            f"channel {channel_id} daily LLM budget exhausted: "
            f"${spent:.2f} of ${cap:.2f}"
        )
        self.channel_id = channel_id
        self.spent = spent
        self.cap = cap


class LadderExhausted(RuntimeError):
    """Raised when every provider in the configured ladder failed."""

    def __init__(self, category: str, attempts: list[tuple[str, str]]):
        msg = f"all providers failed for {category}: " + ", ".join(
            f"{prov}: {err}" for prov, err in attempts
        )
        super().__init__(msg)
        self.category = category
        self.attempts = attempts


# ── Prometheus metrics (no-op if prometheus_client missing) ─────────

try:  # pragma: no cover
    from prometheus_client import Counter, Histogram
    LLM_REQUESTS_TOTAL = Counter(
        "llm_requests_total",
        "LLM call outcomes routed via the central router.",
        labelnames=("category", "provider", "outcome"),  # outcome: ok | fail | budget | breaker
    )
    LLM_COST_USD_TOTAL = Counter(
        "llm_cost_usd_total",
        "Cumulative USD spend on LLM calls (sum of api_usage.cost_usd per call).",
        labelnames=("category", "provider"),
    )
    LLM_DURATION_SECONDS = Histogram(
        "llm_request_duration_seconds",
        "Wall-clock latency of LLM calls including retries.",
        labelnames=("category", "provider"),
        buckets=(0.5, 1, 2, 5, 10, 20, 45, 90, 180),
    )
except Exception:  # pragma: no cover
    class _Noop:
        def labels(self, *a, **kw): return self
        def inc(self, *a, **kw): return None
        def observe(self, *a, **kw): return None
    LLM_REQUESTS_TOTAL = LLM_COST_USD_TOTAL = LLM_DURATION_SECONDS = _Noop()  # type: ignore


# ── Circuit breaker (process-local) ─────────────────────────────────


@dataclass
class _Breaker:
    events: deque = field(default_factory=lambda: deque(maxlen=20))
    open_until: float = 0.0

    def record(self, ok: bool) -> None:
        self.events.append((time.time(), ok))

    def open(self) -> bool:
        if time.time() < self.open_until:
            return True
        recent = [
            (t, ok) for (t, ok) in self.events if t >= time.time() - 300
        ]
        if len(recent) >= 6 and sum(1 for _, ok in recent if not ok) / len(recent) > 0.5:
            self.open_until = time.time() + 60
            return True
        return False


# ── Ladder configuration ────────────────────────────────────────────

# Default ladder per category. Env overrides via ``LLM_<CATEGORY>_LADDER``
# (uppercased, dots → underscores), e.g. ``LLM_SCRIPT_LADDER=claude,openai``.
_DEFAULT_LADDERS: dict[str, list[str]] = {
    "llm":           ["openai", "claude", "gemini"],
    "llm.research":  ["gemini", "openai", "claude"],
    "llm.script":    ["claude", "openai", "gemini"],
    "llm.factcheck": ["openai", "gemini", "claude"],
    "llm.qc":        ["gemini", "openai", "claude"],
    "llm.vision":    ["openai", "gemini"],
    "llm.ideation":  ["gemini", "openai", "claude"],
    "llm.hook":      ["claude", "openai"],
    "llm.direction": ["claude", "openai"],
    "llm.emotion":   ["gemini", "openai"],
}


def _ladder_for(category: str) -> list[str]:
    env_key = "LLM_" + category.replace(".", "_").upper() + "_LADDER"
    raw = os.getenv(env_key, "")
    if raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    return list(_DEFAULT_LADDERS.get(category, _DEFAULT_LADDERS["llm"]))


# ── Cost rollup (Postgres-backed) ───────────────────────────────────


async def _spent_today(channel_id: str) -> float:
    if not channel_id:
        return 0.0
    try:
        from src.db import get_pool
        pool = await get_pool()
        val = await pool.fetchval(
            "SELECT COALESCE(SUM(cost_usd), 0)::float8 FROM api_usage "
            "WHERE channel_id = $1 AND date = CURRENT_DATE",
            channel_id,
        )
        return float(val or 0.0)
    except Exception as exc:
        logger.warning("router.spent_today_failed", error=str(exc))
        return 0.0


async def _cap_for(channel_id: str) -> float:
    if not channel_id:
        return 0.0
    try:
        from src.db import get_pool
        pool = await get_pool()
        val = await pool.fetchval(
            "SELECT daily_cost_cap_usd FROM channels WHERE channel_id = $1",
            channel_id,
        )
        return float(val or 0.0)
    except Exception as exc:
        logger.warning("router.cap_lookup_failed", error=str(exc))
        return 0.0


async def _content_mode_for(content_id: str) -> str | None:
    """Look up `videos.content_mode` so the router can resolve mode-aware chains."""
    if not content_id:
        return None
    try:
        from src.db import get_pool
        pool = await get_pool()
        val = await pool.fetchval(
            "SELECT content_mode FROM videos WHERE content_id = $1",
            content_id,
        )
        return val or None
    except Exception as exc:
        logger.debug("router.content_mode_lookup_failed",
                     content_id=content_id, error=str(exc))
        return None


async def _db_chain_pairs(
    category: str,
    *,
    channel_id: str | None,
    content_mode: str | None,
) -> list[tuple[str, Any, str | None]]:
    """Return ``[(provider_name, member, pinned_model)]`` from the DB chain.

    Empty list when the chain isn't configured; the router then falls
    back to the env-driven ladder. Wrapping mistakes in DB resolution
    must never block a call.
    """
    try:
        from src.providers import chain as chain_mod
        registry = ProviderRegistry._registries.get(category, {})
        if not registry:
            return []
        wrapped = await chain_mod.resolve_chain(
            category, registry,
            channel_id=channel_id, content_mode=content_mode,
        )
    except Exception as exc:
        logger.debug("router.db_chain_failed",
                     category=category, error=str(exc))
        return []
    if wrapped is None:
        return []
    members = list(getattr(wrapped, "members", []))
    names: list[str] = list(getattr(wrapped, "provider_names", []))
    models: list[str | None] = list(getattr(wrapped, "models", []))
    pairs: list[tuple[str, Any, str | None]] = []
    for i, m in enumerate(members):
        name = names[i] if i < len(names) else getattr(m, "provider_name", lambda: "")()
        model = models[i] if i < len(models) else None
        pairs.append((str(name), m, model))
    return pairs


async def _record_usage(*, content_id: str, channel_id: str,
                        category: str, result: LLMResult) -> None:
    try:
        from src.db import get_pool
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO api_usage (content_id, channel_id, service, provider, "
            "model, tokens_in, tokens_out, cost_usd, latency_ms) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            content_id, channel_id, category, result.provider, result.model,
            result.tokens_in, result.tokens_out, float(result.cost_usd),
            result.latency_ms,
        )
    except Exception as exc:
        logger.warning("router.usage_log_failed", error=str(exc))


# ── Transient-vs-permanent error classifier ────────────────────────


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, asyncio.TimeoutError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or 500 <= code < 600
    return False


# ── Router ──────────────────────────────────────────────────────────


class Router:
    """Stateful router. One instance per process is sufficient."""

    def __init__(self) -> None:
        self._breakers: dict[str, _Breaker] = {}

    def _breaker(self, name: str) -> _Breaker:
        b = self._breakers.get(name)
        if b is None:
            b = _Breaker()
            self._breakers[name] = b
        return b

    async def route(
        self,
        *,
        category: str,
        request: LLMRequest,
        channel_id: str = "",
        content_id: str = "",
        content_mode: str | None = None,
        ladder: Iterable[str] | None = None,
        record_usage: bool = True,
    ) -> LLMResult:
        # 1. Budget check (DB-authoritative).
        cap = await _cap_for(channel_id)
        if cap > 0:
            spent = await _spent_today(channel_id)
            if spent >= cap:
                LLM_REQUESTS_TOTAL.labels(
                    category=category, provider="-", outcome="budget"
                ).inc()
                logger.warning("router.budget_exceeded",
                               channel_id=channel_id, spent=spent, cap=cap)
                raise BudgetExceeded(channel_id, spent, cap)

        # 2. Resolve content_mode if the caller didn't pass it (cheap
        #    lookup; DB chain key includes mode so this matters).
        if content_mode is None and content_id:
            content_mode = await _content_mode_for(content_id)

        # 3. Ladder. The DB chain (scope+mode aware) wins when configured;
        #    fall back to the env-driven ladder for back-compat.
        db_pairs = await _db_chain_pairs(
            category, channel_id=channel_id or None, content_mode=content_mode,
        )
        if ladder:
            candidates: list[tuple[str, Any | None, str | None]] = [
                (p, None, None) for p in ladder
            ]
        elif db_pairs:
            candidates = db_pairs
        else:
            candidates = [(p, None, None) for p in _ladder_for(category)]

        attempts: list[tuple[str, str]] = []
        for prov_name, db_member, pinned_model in candidates:
            br = self._breaker(prov_name)
            if br.open():
                attempts.append((prov_name, "circuit_open"))
                LLM_REQUESTS_TOTAL.labels(
                    category=category, provider=prov_name, outcome="breaker"
                ).inc()
                continue
            if db_member is not None:
                provider = db_member
            else:
                try:
                    provider = ProviderRegistry.get(
                        category, override=prov_name,
                        channel_id=channel_id or None,
                        content_mode=content_mode,
                    )
                except Exception as exc:
                    # Provider not registered for this category — silently skip.
                    attempts.append((prov_name, f"unregistered: {exc}"))
                    continue

            # Honor the credential's pinned model when the caller didn't
            # explicitly set one. Per-call request.model still wins.
            call_request = request
            effective_model = pinned_model or getattr(provider, "_pinned_model", None)
            if effective_model and not request.model:
                call_request = replace(request, model=effective_model)

            t0 = time.monotonic()
            try:
                result = await provider.complete(call_request)
            except Exception as exc:
                br.record(False)
                LLM_DURATION_SECONDS.labels(
                    category=category, provider=prov_name
                ).observe(time.monotonic() - t0)
                LLM_REQUESTS_TOTAL.labels(
                    category=category, provider=prov_name, outcome="fail"
                ).inc()
                attempts.append((prov_name, repr(exc)))
                if _is_transient(exc):
                    logger.warning("router.transient_error",
                                   provider=prov_name, error=str(exc))
                    continue
                logger.error("router.permanent_error",
                             provider=prov_name, error=str(exc))
                # Permanent — don't waste budget on the rest of the ladder.
                raise

            br.record(True)
            LLM_DURATION_SECONDS.labels(
                category=category, provider=prov_name
            ).observe(time.monotonic() - t0)
            LLM_REQUESTS_TOTAL.labels(
                category=category, provider=prov_name, outcome="ok"
            ).inc()
            LLM_COST_USD_TOTAL.labels(
                category=category, provider=prov_name
            ).inc(float(result.cost_usd))

            if record_usage:
                await _record_usage(
                    content_id=content_id, channel_id=channel_id,
                    category=category, result=result,
                )
            return result

        raise LadderExhausted(category, attempts)


# Process-wide singleton.
_ROUTER: Router | None = None


def get_router() -> Router:
    global _ROUTER
    if _ROUTER is None:
        _ROUTER = Router()
    return _ROUTER


async def route(
    *,
    category: str,
    request: LLMRequest,
    channel_id: str = "",
    content_id: str = "",
    content_mode: str | None = None,
    ladder: Iterable[str] | None = None,
    record_usage: bool = True,
) -> LLMResult:
    """Module-level convenience wrapper around :class:`Router.route`."""
    return await get_router().route(
        category=category, request=request,
        channel_id=channel_id, content_id=content_id,
        content_mode=content_mode,
        ladder=ladder, record_usage=record_usage,
    )
