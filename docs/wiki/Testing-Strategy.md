# Testing Strategy

## Purpose

Guard quality without slowing iteration. 348 unit tests pass on every CI run.

## Source

- `tests/` (unit + integration + e2e + load)
- `tests/conftest.py` — shared fixtures
- `pytest.ini` — markers + asyncio mode

## Layout

```
tests/
  conftest.py                 # mock_pool, FakeRecord, sample factories
  test_environment_mode.py    # mode resolution, prefixing, safety guards
  test_ab_framework.py        # deterministic assignment, t-test
  test_observability.py       # log_decision, savings, model_health
  test_synthetic_data.py      # row generators yield valid ranges
  test_model_maintenance.py   # TRAINABLE_MODELS config validation
  test_voice_intelligence.py  # 25+
  test_assets_intelligence.py # 15+
  test_thumbnail_intelligence.py
  test_direction_intelligence.py
  test_assembly_intelligence.py
  test_delivery_intelligence.py
  test_analytics_intelligence.py
  e2e/test_render_smoke.py    # full pipeline in test mode
  load/test_fleet_health_under_load.py
  fixtures/llm/ fixtures/search/  # cached provider responses
  golden/legacy_api_contract.json # frozen contract for legacy /api/*
```

## Markers

- `unit` (default)
- `integration` — needs DB/Redis/MinIO; gated in CI
- `e2e` — needs full stack up
- `load` — needs at least 4 cores, deselected by default

## Running

```bash
make test               # unit only, fast
pytest -m integration
pytest tests/e2e
pytest tests/load -k fleet --maxfail=1
```

## Async tests

`pytest-asyncio` in `auto` mode — any `async def test_...` is awaited
without a decorator.

## Mock provider determinism

Mock LLM/search providers cache by prompt fingerprint into
`tests/fixtures/`, so PRs that change a prompt see exactly which fixtures
need regenerating.

## Long-horizon test debt

In `PENDING.md`:

- Circuit breaker behaviour under sustained outage — not yet covered.
- Cross-channel dedup with ≥ 3 channels concurrently — no fixture.
- Sustained 10-channel load test (k6 / locust) —
  `load-test-graduation`.

## Related pages

- [[CI-CD]] · [[Quality-Gates]]
