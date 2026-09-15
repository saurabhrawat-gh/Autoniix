# Contract Validation Tests

**Status:** Week 1 Day 1-2 Complete  
**Per:** HARNESS-ENGINEERING-PLAN.md Section 3

## Overview

This directory contains REST contract validation tests that verify API responses match OpenAPI schemas.

## Structure

```
tests/contracts/
├── README.md                    # This file
├── extract_schemas.py           # Extract OpenAPI schemas from services
├── rest_validator.py            # REST contract validator
├── test_gateway_rest.py         # Rust gateway contract tests
├── schemas/                     # Generated OpenAPI schemas
│   ├── rust-gateway.json        # Auto-generated from Rust
│   └── python-dashboard.json    # Auto-generated from Python
└── fixtures/                    # Test fixtures (future)
```

## Usage

### 1. Extract Schemas

Extract OpenAPI schemas from running services:

```bash
# Start Python dashboard
cd src/services/dashboard
uvicorn main:app --port 8000

# Start Rust gateway (in another terminal)
cd rust/gateway
cargo run --release -- --port 8080

# Extract schemas (in another terminal)
cd tests/contracts
python extract_schemas.py

# Or extract individually
python extract_schemas.py --python-only
python extract_schemas.py --rust-only
```

**Output:**

- `schemas/python-dashboard.json` — Python FastAPI auto-generated schema
- `schemas/rust-gateway.json` — Rust gateway schema (from `/openapi.json` or handwritten fallback)

### 2. Run Contract Tests

```bash
# Run all contract tests
pytest tests/contracts/test_gateway_rest.py -v

# Run specific test
pytest tests/contracts/test_gateway_rest.py::TestRustGatewayContracts::test_signup_matches_openapi -v

# Run with detailed output
pytest tests/contracts/test_gateway_rest.py -vv --tb=short
```

### 3. Compare Schemas

Compare Python and Rust schemas to find differences:

```python
from tests.contracts.rest_validator import compare_schemas

result = compare_schemas(
    "tests/contracts/schemas/python-dashboard.json",
    "tests/contracts/schemas/rust-gateway.json",
)

print(f"Endpoints only in Python: {result['endpoints_only_in_a']}")
print(f"Endpoints only in Rust: {result['endpoints_only_in_b']}")
print(f"Schema mismatches: {result['schema_mismatches']}")
```

## OpenAPI Schema Sources

### Python Dashboard

FastAPI auto-generates OpenAPI schema at `/openapi.json`. No manual work required.

### Rust Gateway

**Current (Week 1 Day 1):** Handwritten schema at `rust/gateway/openapi.yaml`

**Future (Phase 1):** Auto-generated from code annotations using `utoipa`:

```rust
// rust/gateway/src/routes/auth.rs
use utoipa::ToSchema;

// Post-#350: register returns onboarding metadata only — NO tokens.
// The client must call /signin afterwards to obtain a session.
#[derive(Serialize, ToSchema)]
struct RegisterResponse {
    status: String,         // always "ok"
    user_id: i64,
    workspace_id: i64,
    role: String,           // always "owner" for the first user
    onboarding_required: bool,
}

#[utoipa::path(
    post,
    path = "/api/v2/auth/register",
    request_body = RegisterRequest,
    responses(
        (status = 201, description = "User + workspace created", body = RegisterResponse),
        (status = 409, description = "Email exists", body = Error),
    )
)]
async fn register(/* ... */) -> ApiResult<impl IntoResponse> {
    // ...
}
```

Then generate schema:

```bash
cd rust/gateway
cargo run --bin openapi-gen > ../../docs/openapi/rust-gateway.json
```

## Test Coverage

### Rust Gateway Auth Endpoints

- [x] `POST /api/v2/auth/register` — Create user account (canonical; post-#350)
- [x] `POST /api/v2/auth/signup` — Deprecated alias for `/register`
- [x] `POST /api/v2/auth/signin` — Sign in
- [x] `POST /api/v2/auth/refresh` — Refresh access token
- [x] `POST /api/v2/auth/verify` — Verify JWT token
- [x] `POST /api/v2/auth/logout` — Logout and revoke session
- [x] `GET /api/v2/me` — Get current user info

### Python Dashboard (Comparison)

- [x] `POST /api/v2/auth/register` — Create user account

## Dependencies

```bash
pip install httpx jsonschema pyyaml structlog pytest
```

## CI Integration

Add to `.github/workflows/test.yml`:

```yaml
- name: Extract OpenAPI Schemas
  run: |
    python tests/contracts/extract_schemas.py --python-only
    # Rust schema uses handwritten fallback for now

- name: Run Contract Tests
  run: pytest tests/contracts/test_gateway_rest.py -v
```

## Troubleshooting

### Schema Not Found

**Error:** `Rust schema not found at tests/contracts/schemas/rust-gateway.json`

**Solution:** Run `python extract_schemas.py` or ensure handwritten schema exists at `rust/gateway/openapi.yaml`

### Service Not Running

**Error:** `Connection refused to http://localhost:8080`

**Solution:** Start the Rust gateway: `cd rust/gateway && cargo run`

### Schema Validation Failed

**Error:** `Schema validation failed: ['user.id: 123 is not of type string']`

**Solution:** Update OpenAPI schema to match actual response types. For example, if `user.id` is `i64`, schema should be:

```yaml
user:
  type: object
  properties:
    id:
      type: integer
      format: int64
```

## Next Steps

Per HARNESS-ENGINEERING-PLAN.md:

- **Week 1 Day 3-5:** Provider mock harness (OpenAI, Anthropic, etc.)
- **Week 2:** Rust gateway test harness (GatewayHarness helper)
- **Week 3:** Equivalence testing (Python vs Rust response diffing)
- **Week 4:** Performance benchmarks (Criterion)

## Related Documents

- `docs/architecture/harness-engineering-plan.md` — Overall harness plan
- `docs/future/post-harness-tasks.md` — Post-harness implementation tasks
- `rust/gateway/DB_REALIGNMENT_SUMMARY.md` — DB schema realignment summary
