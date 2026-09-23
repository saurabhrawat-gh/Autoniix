"""Unit tests for the LLM router (Phase 4).

Strategy:
- Register three fake providers (one OK, one transient-fail, one permanent-fail)
  under the live :class:`ProviderRegistry`.
- Stub the DB-backed cost-cap helpers so the router doesn't need Postgres.
- Drive the router with explicit ``ladder=...`` lists to keep each test focused
  on a single behaviour.
"""

from __future__ import annotations

import httpx
import pytest
from llm import BudgetExceeded, LadderExhausted, Router, router as router_mod

from providers.llm.base import LLMProvider, LLMRequest, LLMResult
from providers.registry import ProviderRegistry


class _FakeOK(LLMProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResult:
        self.calls += 1
        return LLMResult(
            content='{"ok": true}',
            model="fake-ok",
            tokens_in=10,
            tokens_out=5,
            cost_usd=0.0001,
            provider="fake_ok",
            latency_ms=1,
        )

    def estimate_cost(self, *a, **kw):
        return 0.0

    async def health_check(self):
        return True

    def provider_name(self):
        return "fake_ok"

    def default_model(self):
        return "fake-ok"

    def supported_models(self):
        return ["fake-ok"]


class _FakeTransient(LLMProvider):
    """Always raises a transient (timeout) error — router should fall through."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResult:
        self.calls += 1
        raise httpx.TimeoutException("simulated timeout")

    def estimate_cost(self, *a, **kw):
        return 0.0

    async def health_check(self):
        return False

    def provider_name(self):
        return "fake_transient"

    def default_model(self):
        return "fake-t"

    def supported_models(self):
        return ["fake-t"]


class _FakePermanent(LLMProvider):
    """Raises a non-transient, non-config error (caller schema bug) — router must
    surface it. 401/403/404 are treated as per-provider config errors and skipped
    (see ``router._is_provider_config_error``), so use 400 here."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResult:
        self.calls += 1
        req = httpx.Request("POST", "https://example.invalid/x")
        resp = httpx.Response(400, request=req)
        raise httpx.HTTPStatusError("bad request", request=req, response=resp)

    def estimate_cost(self, *a, **kw):
        return 0.0

    async def health_check(self):
        return False

    def provider_name(self):
        return "fake_permanent"

    def default_model(self):
        return "fake-p"

    def supported_models(self):
        return ["fake-p"]


CATEGORY = "llm.router_test"


@pytest.fixture
def registered(monkeypatch):
    """Register the fake providers under a unique category for each test.

    Reset per-test so the registry's instance cache doesn't leak state and
    so circuit-breaker counters don't carry over.
    """
    ProviderRegistry.register(CATEGORY, "ok", _FakeOK)
    ProviderRegistry.register(CATEGORY, "transient", _FakeTransient)
    ProviderRegistry.register(CATEGORY, "permanent", _FakePermanent)
    yield
    ProviderRegistry.reset()


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    """Stub the DB-backed cost cap helpers so the router runs without Postgres."""

    async def _zero_spent(_):
        return 0.0

    async def _no_cap(_):
        return 0.0

    async def _record(**kw):
        return None

    monkeypatch.setattr(router_mod, "_spent_today", _zero_spent)
    monkeypatch.setattr(router_mod, "_cap_for", _no_cap)
    monkeypatch.setattr(router_mod, "_record_usage", _record)
    yield


@pytest.fixture
def router():
    return Router()


def _req() -> LLMRequest:
    return LLMRequest(messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_primary_succeeds(registered, router):
    out = await router.route(category=CATEGORY, request=_req(), ladder=["ok"])
    assert out.provider == "fake_ok"
    assert out.cost_usd > 0


@pytest.mark.asyncio
async def test_transient_falls_through(registered, router):
    out = await router.route(
        category=CATEGORY,
        request=_req(),
        ladder=["transient", "ok"],
    )
    assert out.provider == "fake_ok"


@pytest.mark.asyncio
async def test_permanent_error_does_not_fall_through(registered, router):
    """A non-transient error means the request itself is broken (auth, schema).
    Burning ladder budget on it just hides the bug."""
    with pytest.raises(httpx.HTTPStatusError):
        await router.route(
            category=CATEGORY,
            request=_req(),
            ladder=["permanent", "ok"],
        )


@pytest.mark.asyncio
async def test_ladder_exhausted(registered, router):
    with pytest.raises(LadderExhausted) as exc_info:
        await router.route(
            category=CATEGORY,
            request=_req(),
            ladder=["transient", "transient"],
        )
    assert len(exc_info.value.attempts) == 2


@pytest.mark.asyncio
async def test_budget_exceeded_short_circuits(registered, router, monkeypatch):
    async def _spent(_):
        return 5.0

    async def _cap(_):
        return 1.0

    monkeypatch.setattr(router_mod, "_spent_today", _spent)
    monkeypatch.setattr(router_mod, "_cap_for", _cap)

    with pytest.raises(BudgetExceeded) as exc_info:
        await router.route(
            category=CATEGORY,
            request=_req(),
            channel_id="CH_TEST",
            ladder=["ok"],
        )
    assert exc_info.value.spent == 5.0
    assert exc_info.value.cap == 1.0


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_repeated_failures(registered, router):
    for _ in range(6):
        try:
            await router.route(
                category=CATEGORY,
                request=_req(),
                ladder=["transient"],
            )
        except LadderExhausted:
            pass
    transient = ProviderRegistry.get(CATEGORY, override="transient")
    calls_before_open = transient.calls
    out = await router.route(
        category=CATEGORY,
        request=_req(),
        ladder=["transient", "ok"],
    )
    assert out.provider == "fake_ok"
    assert transient.calls == calls_before_open


@pytest.mark.asyncio
async def test_ladder_skips_unregistered_providers(registered, router):
    """Naming a provider that isn't registered for the category should be a
    silent skip (so env-driven ladders are forgiving), not a hard error."""
    out = await router.route(
        category=CATEGORY,
        request=_req(),
        ladder=["does_not_exist", "ok"],
    )
    assert out.provider == "fake_ok"
