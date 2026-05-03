# Testing Expectations

## What Must Be Tested
- Provider pattern: every new provider must have unit tests
- Intelligence modules: every new scoring/prediction function must have tests
- API endpoints: critical paths (happy path + error cases)
- Temporal activities: mock service calls, verify retry logic
- Environment mode: test vs production behavior differences

## Framework & Tools
- **pytest** with pytest-asyncio for async tests
- **conftest.py** in tests/ provides shared fixtures (mock_pool, FakeRecord, sample data factories)
- Run: `pytest` or `python -m pytest tests/`
- Async tests: use `@pytest.mark.asyncio` decorator

## Test Location
- `tests/test_<module>.py` mirrors `src/services/<module>/`
- Example: `tests/test_script_intelligence.py` tests `src/services/script/`

## Coverage Targets
- Intelligence modules: 80%+ (critical for self-learning accuracy)
- Provider implementations: 70%+ (mock external APIs)
- API endpoints: 60%+ (happy path + error codes)
- Overall: 70%+

## Test Patterns
- Use `mock_pool` fixture from conftest.py for DB mocking
- Use `FakeRecord` for simulating asyncpg Record objects
- Mock external APIs (OpenAI, Anthropic, Fish Audio) — never call real APIs in tests
- Use `ProviderRegistry.reset()` between tests to avoid cached instances
- Test environment mode: verify `_TEST_PROVIDER_MAP` remapping works

## Running Tests
```bash
# All tests
pytest

# Specific module
pytest tests/test_script_intelligence.py

# With verbose output
pytest -v

# Skip slow/integration tests
pytest -m "not integration"
```

## Synthetic Data
- `scripts/generate_training_data.py` generates training data for ML models
- Usage: `python -m scripts.generate_training_data --niches tech,health --count 60`
- 5 niche profiles: tech, health, finance, education, entertainment
