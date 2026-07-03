# Harness Engineering Master Plan

**Status:** In Execution (v4)  
**Created:** 2026-06-20  
**Last Updated:** 2026-06-20 (7:58 PM)  
**Epic:** #638 Multi-Language Backend Migration  
**Review Required By:** Migration lead, team architects, security team, SRE team

**v4 Changes (Week 1 Day 1 — JWT fix executed, discoveries applied):**
- ✅ DECISION: JWT aligned Rust → Python (Option A) — implemented in `rust/gateway`
- ✅ DISCOVERY: Rust built a *fiction* DB schema (UUID/`user_roles`) vs Python's live integer-keyed schema (`workspace_members`/`sessions`)
- ✅ Section 13 rewritten: **no UUID backfill** — realign Rust to integer schema instead
- ✅ Config: Rust now reads `AUTH_JWT_SECRET` (shared with Python)
- ✅ Flagged follow-up: realign `models.rs` to `i64` keys + opaque refresh tokens

**v2 Changes:**
- ✅ Fixed REST vs gRPC protocol mismatch (Phase 1 is REST-only)
- ✅ Added OpenAPI schema generation requirement
- ✅ Documented JWT incompatibility (Rust UUID vs Python int)
- ✅ Added database schema validation tests
- ✅ Extended provider mock timeline (1 day → 3 days)
- ✅ Added Criterion benchmarks for Rust
- ✅ Added performance comparison dashboard
- ✅ Added rollback safety testing
- ✅ Updated timeline: 2-3 weeks → 3-4 weeks (more realistic)

**v3 Changes (Production-Ready):**
- ✅ Fixed math error in cost-benefit ($20K → $34K)
- ✅ Synced stale sections (2, 7, 9, 10) with updated plan
- ✅ Added Section 11: Production Rollout Strategy (canary + feature flags)
- ✅ Added Section 12: Observability Strategy (OpenTelemetry + Prometheus)
- ✅ Added Section 13: Database Migration Reconciliation
- ✅ Added Section 14: Load & Security Testing
- ✅ Specified test infrastructure (testcontainers-rs, pytest-postgresql)
- ✅ Added Definition of Done per harness
- ✅ Added execution time budget (smoke <5min, full <30min)
- ✅ Added divergence handling for intentional differences
- ✅ Added golden file testing for silent corruption detection

---

## Executive Summary

**Decision:** Build harness infrastructure FIRST (3-4 weeks), then migrate with confidence (17-23 weeks).

**Problem:** Migrating ~50K LOC across 27 route modules + 10 microservices + 8 Temporal workflows from Python → Rust/Go/Python without test harnesses carries unacceptable risk of production bugs, API contract breaks, and cost overruns.

**Solution:** Three categories of harnesses:
1. **Migration Validation** (Temporary): Prove Python ≡ Rust/Go behavior
2. **Permanent Service Tests** (Native): Unit/integration tests per language
3. **Contract Compliance** (Proto-based): Validate all services against schemas

**ROI:** 3-4 weeks investment saves $32K-100K in production incidents + API testing costs

---

## 1. Current Migration Status

### ✅ Completed (Stories P1.1-P1.4)

| Story | What Was Built | Files | Test Coverage |
|-------|----------------|-------|---------------|
| P1.1: Proto Setup | Buf CLI, 9 proto files, 4-language codegen | 17 | Contract schemas exist |
| P1.2: Rust Gateway | Axum + Tonic framework, health checks | 14 | 1 integration test |
| P1.3: Auth Service | JWT, Argon2, 4 auth endpoints, PostgreSQL | 16 | 2 integration tests |
| P1.4: Auth Middleware | RBAC, Principal context, `/me` endpoint | 9 | 2 middleware tests |

**Total:** 56 Rust files, 5 integration tests, **BUT:**
- ❌ No OpenAPI schema (REST endpoints not documented)
- ❌ No contract validation (no proof REST responses match schemas)
- ❌ No equivalence testing (no comparison vs Python dashboard)
- ❌ No provider mocks (will burn API credits in testing)
- ❌ JWT schemas INCOMPATIBLE (Rust uses UUIDs, Python uses ints)
- ❌ No database schema validation (UUID vs int ID mismatch)
- ❌ No performance benchmarks
- ⚠️ **Note:** Rust currently implements REST-only; gRPC comes in Phase 2

### 🔴 Remaining Migration Scope

| Component | LOC | Target Language | Status |
|-----------|-----|-----------------|--------|
| **Rust Services** | | | |
| Gateway (remaining routes) | ~9K | Rust | 🟡 Auth done, 23 routes left |
| Provider Router | ~800 | Rust | ❌ Not started |
| Prompt Compressor | ~500 | Rust | ❌ Not started |
| Assembly/Direction/Secrets/Metrics | ~2.8K | Rust | ❌ Not started |
| **Go Services** | | | |
| 10 microservices (Research, Script, Voice, etc.) | ~11K | Go | ❌ Not started |
| 2 Temporal workers + 8 workflows | ~4K | Go | ❌ Not started |
| **Python Services (add gRPC)** | | | |
| 10 AI services (Brain, Analytics, etc.) | ~13K | Python | ❌ gRPC wrappers needed |

**Total to migrate:** ~41K LOC (excluding already-done auth)

---

## 2. Harness Architecture

### Three Harness Categories

```
┌──────────────────────────────────────────────────────────┐
│  Category 1: CROSS-SERVICE VALIDATION (Permanent)        │
│  ├─ Language: Rust (performance + type safety)          │
│  ├─ Location: rust/harness/                             │
│  ├─ Purpose: Validate Python ↔ Rust ↔ Go contracts     │
│  └─ Lifespan: Permanent (HTTP/gRPC testing)            │
├──────────────────────────────────────────────────────────┤
│  Category 2: SERVICE-SPECIFIC TESTS (Permanent)          │
│  ├─ Rust: rust/*/tests/ (Cargo test)                   │
│  ├─ Go: go/*/internal/harness/ (Go test)               │
│  ├─ Python: tests/harnesses/ (pytest)                  │
│  └─ Purpose: Native unit/integration tests per service  │
├──────────────────────────────────────────────────────────┤
│  Category 3: CONTRACT COMPLIANCE (Permanent)             │
│  ├─ Language: Rust (OpenAPI + Proto validation)        │
│  ├─ Location: rust/harness/src/contract/               │
│  └─ Purpose: Validate REST (OpenAPI) + gRPC (Proto)    │
└──────────────────────────────────────────────────────────┘
```

### 🔒 LOCKED DECISION: Harness Language Strategy

**Rule:** Write harnesses in the TARGET migration language

| Service Type | Target Language | Harness Location | Rationale |
|--------------|----------------|------------------|-----------|
| **Rust Services** (Gateway, Provider Router, etc.) | Rust | `rust/harness/` | Permanent infrastructure, reusable across Rust services |
| **Go Services** (Microservices, Temporal) | Go | `go/harness/` | Native Go test utilities, workflow mocks |
| **Python Services** (AI services staying in Python) | Python | `tests/harnesses/` | Services not migrating, Python harness stays |
| **Cross-Service Validation** (Python ↔ Rust ↔ Go) | **Rust** | `rust/harness/` | Performance, type safety, permanent infrastructure |

**Why Rust for cross-service validation:**
- ✅ Type-safe HTTP/gRPC clients
- ✅ Fast execution (important for CI)
- ✅ Permanent infrastructure (not throwaway)
- ✅ Can test all services via HTTP/gRPC regardless of their language
- ✅ Single harness codebase for all migrations

### Why This Matters

| Without Harness | With Harness |
|----------------|--------------|
| ❌ No proof Rust auth = Python auth | ✅ Automated equivalence tests |
| ❌ $500/week burning API credits | ✅ $0 with mocks |
| ❌ Manual testing of 270+ endpoints | ✅ Automated contract validation |
| ❌ Production bugs discovered by users | ✅ Bugs caught in CI |
| ❌ No confidence in rollback | ✅ Instant rollback safety |

---

## 3. Implementation Plan (Phase 0)

### Week 1: Rust Harness Foundation (REVISED)

**🔒 LOCKED:** All harnesses in Rust per language strategy

**Day 1-2: Rust Harness Crate Setup + OpenAPI Validation**
```bash
# Create rust/harness crate
cd rust
cargo new --lib harness
cd harness
cargo add reqwest tokio serde serde_json jsonschema
cargo add utoipa --features axum_extras  # OpenAPI schema parsing
```

```rust
// rust/harness/src/contract/mod.rs (~200 LOC)
pub struct ContractValidator {
    schema: OpenApiSchema,
}

impl ContractValidator {
    pub async fn validate_endpoint(
        &self,
        url: &str,
        method: Method,
        path: &str,
        request_body: Option<Value>,
    ) -> Result<(), ValidationError> {
        // Make HTTP request, validate response against OpenAPI schema
    }
}

// rust/harness/tests/contract_tests.rs (~150 LOC)
#[tokio::test]
async fn test_signup_matches_openapi() {
    let validator = ContractValidator::from_file("../../gateway/openapi.json");
    validator.validate_endpoint(
        "http://localhost:8080",
        Method::POST,
        "/api/v2/auth/signup",
        Some(json!({"email": "test@example.com", ...})),
    ).await.unwrap();
}
```

**Goal:** Type-safe contract validation in Rust

**Day 3-5: Provider Mock Harness in Rust**
```rust
// rust/harness/src/providers/mod.rs (~600 LOC total)
pub struct ProviderMockHarness {
    cache_dir: PathBuf,
}

impl ProviderMockHarness {
    pub async fn openai_mock(&self, req: OpenAIRequest) -> OpenAIResponse { }
    pub async fn anthropic_mock(&self, req: AnthropicRequest) -> AnthropicResponse { }
    pub async fn fish_audio_mock(&self, req: FishRequest) -> Vec<u8> { }
    pub async fn dalle_mock(&self, req: DalleRequest) -> DalleResponse { }
    pub async fn pexels_mock(&self, req: PexelsRequest) -> PexelsResponse { }
    pub async fn serpapi_mock(&self, req: SerpApiRequest) -> SerpApiResponse { }
    pub async fn youtube_mock(&self, req: YouTubeRequest) -> YouTubeResponse { }
    pub async fn gemini_mock(&self, req: GeminiRequest) -> GeminiResponse { }
}
```

**Goal:** Type-safe provider mocks with disk caching, saves $500/week

**Deliverables:**
- ✅ `rust/harness/` crate with contract validator
- ✅ OpenAPI schema validation (reqwest + jsonschema)
- ✅ 8 provider mocks with type-safe request/response structs
- ✅ Disk caching for fixtures
- ✅ Integration tests for all mocks
- ✅ CI job: `cargo test -p harness`

---

### Week 2: Rust Harnesses

**Day 1-2: Gateway Test Harness**
```rust
// rust/gateway/tests/common/harness.rs (~300 LOC)
pub struct GatewayHarness {
    pub db_pool: PgPool,
    pub app: Router,
}

impl GatewayHarness {
    pub async fn new() -> Self { /* ephemeral test DB, migrations, seeds */ }
    pub async fn signup(&self, email: &str) -> AuthResponse { /* helper */ }
    pub async fn signin(&self, email: &str, pass: &str) -> String { /* helper */ }
    pub async fn cleanup(&self) { /* drop test DB */ }
}
```

**Before:**
```rust
#[tokio::test]
async fn test_signup() {
    let app = create_test_app().await;
    // 50 lines of manual setup...
}
```

**After:**
```rust
#[tokio::test]
async fn test_signup() {
    let h = GatewayHarness::new().await;
    let user = h.signup("test@ex.com", "pass").await;
    assert_eq!(user.email, "test@ex.com");
    h.cleanup().await;
}
```

**Day 3-4: Criterion Benchmarks**
```toml
# rust/gateway/Cargo.toml
[dev-dependencies]
criterion = "0.5"

[[bench]]
name = "auth_bench"
harness = false
```

```rust
// rust/gateway/benches/auth_bench.rs (~150 LOC)
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn signup_benchmark(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();
    let harness = runtime.block_on(GatewayHarness::new());
    
    c.bench_function("signup", |b| {
        b.to_async(&runtime).iter(|| async {
            harness.signup("test@example.com", "password").await
        });
    });
}

criterion_group!(benches, signup_benchmark, signin_benchmark, refresh_benchmark);
criterion_main!(benches);
```

**Goal:** Set performance baselines — Rust must be ≤ Python latency

**Deliverables:**
- ✅ Rust harness with DB fixtures
- ✅ Refactored existing 5 tests to use harness
- ✅ Criterion benchmarks (signup < 30ms p95, signin < 25ms p95)
- ✅ CI job that fails if benchmarks regress > 10%

---

### Week 3: Go + Python Harnesses

**Day 1-2: Go Service Harness Template**
```go
// go/shared/testharness/harness.go (~400 LOC)
type ServiceHarness struct {
    Server *grpc.Server  // in-memory via bufconn
    Client pb.ServiceClient
    MockLLM *MockLLMProvider
}

func NewServiceHarness(t *testing.T, service string) *ServiceHarness
```

**Day 3: Python gRPC Harness**
```python
# python/shared/testharness/grpc_harness.py (~300 LOC)
class GRPCServiceHarness:
    """Template for adding gRPC to existing Python services"""
    async def __aenter__(self): # start server
    async def __aexit__(self): # stop server
```

**Deliverables:**
- ✅ Go harness template (reusable for 12 services)
- ✅ Python gRPC harness template (reusable for 10 services)
- ✅ Mock LLM providers (Go + Python)

---

### Week 4: Migration Validation Harnesses

**Day 1: Equivalence Testing**
```python
# tests/migration/harnesses/equivalence_harness.py (~500 LOC)
class EquivalenceHarness:
    """Compare Python vs Rust/Go responses side-by-side"""
    
    async def compare_endpoint(self, method, path, payload):
        python_resp = await self.python_client.request(...)
        new_resp = await self.new_client.request(...)
        return ComparisonResult(equivalent=..., diffs=...)
```

**Usage:**
```python
# tests/migration/test_auth_equivalence.py
async def test_signup_equivalence():
    h = EquivalenceHarness(python_url="localhost:5009", new_url="localhost:8080")
    result = await h.compare_endpoint("POST", "/api/v2/auth/signup", {...})
    assert result.equivalent  # Status + body must match
```

**Day 2: E2E Orchestration**
```yaml
# docker-compose.test.yml
# Spins up: postgres-test, redis-test, rust-gateway-test, python-dashboard-test
```

```python
# tests/e2e/harness.py (~300 LOC)
class E2EHarness:
    async def __aenter__(self):  # docker-compose up
    async def __aexit__(self):   # docker-compose down
```

**Day 3: Performance Comparison Dashboard**
```python
# tests/migration/harnesses/perf_comparison.py (~200 LOC)
class PerformanceComparison:
    async def benchmark_both(self, endpoint, payload):
        python_p95 = await self._benchmark(python_url, endpoint, payload)
        rust_p95 = await self._benchmark(rust_url, endpoint, payload)
        
        return ComparisonResult(
            python_ms=python_p95,
            rust_ms=rust_p95,
            speedup_factor=python_p95 / rust_p95
        )
    
    def generate_report(self) -> str:
        # Markdown table of Python vs Rust latencies
```

**Day 4: Rollback Testing**
```python
# tests/migration/test_rollback.py (~150 LOC)
async def test_can_rollback_to_python():
    # Create data via Rust
    rust_user = await rust_gateway.signup(...)
    
    # Stop Rust, start Python
    await docker.stop("rust-gateway")
    await docker.start("python-dashboard")
    
    # Verify Python can read Rust-created data
    python_user = await python_dashboard.get_user(rust_user.id)
    assert python_user.email == rust_user.email
```

**Deliverables:**
- ✅ Equivalence harness (compares old vs new)
- ✅ E2E orchestration harness
- ✅ Performance comparison dashboard (visual latency comparison)
- ✅ Rollback safety tests (Rust → Python → Rust)
- ✅ CI job: `pnpm test:migration`

---

## 4. Handling Already-Migrated Rust Auth (P1.2-P1.4)

### Problem

Auth endpoints exist but have NO:
- OpenAPI schema documentation
- REST contract validation
- Equivalence testing vs Python
- JWT compatibility (schemas are INCOMPATIBLE)
- Database schema validation (UUID vs int mismatch)
- Performance benchmarks

### 🔴 CRITICAL: JWT Schema Incompatibility Discovered

**Python JWT Claims:**
```json
{
  "sub": 123,              // int user_id
  "wid": 1,                // int workspace_id
  "email": "user@example.com",
  "role": "owner",         // single string
  "global_role": "user"
}
```

**Rust JWT Claims (Current):**
```json
{
  "sub": "uuid-string",       // String user_id
  "workspace_id": "uuid",    // Different field name
  "email": "user@example.com",
  "roles": ["owner"],        // Array, not string
  "exp": 1234567890,
  "iat": 1234567890,
  "jti": "uuid"
}
```

**Impact:** Tokens are NOT interchangeable. Rust tokens will be rejected by Python and vice versa.

**Decision Required (Week 1, Day 1):**

**Option A: Align Rust to Python** (Recommended if keeping Python dashboard)
```rust
// rust/gateway/src/auth/jwt.rs - UPDATE Claims struct
pub struct Claims {
    pub sub: i64,              // Change String → i64
    pub wid: i64,              // Rename workspace_id → wid
    pub email: String,
    pub role: String,          // Change Vec<String> → String
    pub global_role: String,   // Add this field
    pub exp: i64,
    pub iat: i64,
}
```

**Option B: Migrate Python to Rust schema** (If Python being phased out soon)
```python
# src/services/dashboard/v2/_deps.py - UPDATE _decode_jwt
def _decode_jwt(token: str) -> dict[str, Any] | None:
    claims = jwt.decode(token, secret, algorithms=["HS256"])
    # Convert UUID strings, handle role array
    return {
        "sub": claims["sub"],  # Keep as string
        "wid": claims["workspace_id"],  # Read from workspace_id
        "role": claims["roles"][0] if claims.get("roles") else "viewer",
        ...
    }
```

### Immediate Actions (Week 1, Day 1-2)

**1. Fix JWT schema incompatibility**
```bash
# MUST DO FIRST - Choose Option A or B above and implement
# Without this, equivalence tests will fail on token validation
```

**2. Add OpenAPI schema**
```rust
// rust/gateway/Cargo.toml
utoipa = { version = "4.0", features = ["axum_extras"] }

// Annotate handlers with #[utoipa::path(...)]
// Generate docs/openapi/gateway.json
```

**3. Add REST contract validation**
```python
# tests/contracts/test_gateway_rest.py (NEW - ~120 LOC)
import openapi_core

def test_signup_matches_openapi():
    schema = load_openapi_schema("docs/openapi/gateway.json")
    validator = RESTValidator(schema)
    
    response = requests.post("http://localhost:8080/api/v2/auth/signup", {...})
    validator.validate_response(response)  # Fails if schema mismatch
```

**4. Add database schema validation**
```python
# tests/migration/test_schema_compatibility.py (NEW - ~100 LOC)
async def test_rust_and_python_share_database():
    # Create user via Rust
    rust_user = await rust_gateway.signup(
        email="test@example.com",
        password="secure123",
        full_name="Test User",
        workspace_name="Test WS"
    )
    
    # Verify Python can read Rust-created user
    python_user = await python_dashboard.get_user(rust_user.id)
    assert python_user is not None
    assert python_user.email == "test@example.com"
    
    # Create user via Python
    python_user2 = await python_dashboard.create_user(...)
    
    # Verify Rust can read Python-created user
    rust_user2 = await rust_gateway.get_user(python_user2.id)
    assert rust_user2 is not None
```

**5. Add equivalence testing**
```python
# tests/migration/test_auth_equivalence.py (NEW - ~200 LOC)
async def test_all_auth_endpoints_match_python():
    harness = EquivalenceHarness(
        python_url="http://localhost:5009",
        rust_url="http://localhost:8080"
    )
    
    # Test signup
    result = await harness.compare_endpoint(
        method="POST",
        path="/api/v2/auth/signup",
        payload={
            "email": "test@example.com",
            "password": "secure123",
            "full_name": "Test User",
            "workspace_name": "Test WS"
        }
    )
    assert result.status_match
    assert result.body_match
    
    # Repeat for signin, refresh, verify
    # ...
    
    harness.assert_all_equivalent()  # MUST pass before continuing
```

**6. Add JWT cross-compatibility test** (After fixing schema)
```python
# tests/migration/test_jwt_compatibility.py (NEW - ~80 LOC)
def test_rust_token_works_in_python():
    # Create token in Rust
    rust_token = rust_gateway.signin("user@example.com", "password")
    
    # Verify Python can decode it
    python_claims = python_dashboard.verify_token(rust_token.access_token)
    assert python_claims.user_id is not None
    assert python_claims.email == "user@example.com"

def test_python_token_works_in_rust():
    # Create token in Python
    python_token = python_dashboard.signin("user@example.com", "password")
    
    # Verify Rust can decode it
    rust_response = requests.get(
        "http://localhost:8080/api/v2/me",
        headers={"Authorization": f"Bearer {python_token}"}
    )
    assert rust_response.status_code == 200
```

**7. Refactor Rust tests to use harness (Week 2)**
```rust
// Refactor auth_test.rs, middleware_test.rs to use GatewayHarness
```

**8. Add Criterion benchmarks (Week 2)**
```rust
// rust/gateway/benches/auth_bench.rs
// Ensure Rust p95 ≤ Python p95
```

### Validation Checklist Before Continuing Migration

- [ ] **JWT Schema:** Aligned between Rust and Python (Option A or B implemented)
- [ ] **Database Schema:** Both services can read each other's data
- [ ] **OpenAPI:** REST endpoints documented in gateway.json
- [ ] **Contract:** All 4 auth endpoints pass OpenAPI validation
- [ ] **Equivalence:** Rust responses = Python responses (status + body)
- [ ] **JWT Cross-Compat:** Rust tokens work in Python AND Python tokens work in Rust
- [ ] **Performance:** Rust p95 ≤ Python p95 (via benchmarks)
- [ ] **Errors:** Same error codes/messages for invalid inputs

**If any fail:** Fix before migrating more code. This proves harness strategy works.

---

## 5. Updated Migration Workflow

### Phase 1 Stories (REST-only) — P1.5 through P1.9

**Important:** Phase 1 implements REST endpoints only. gRPC/Connect-RPC comes in Phase 2.

#### Per-Story Template (Example: P1.5 Jobs Endpoints)

```
Story P1.5: Jobs CRUD Endpoints (REST)
├─ Task 1: Write OpenAPI schema + contract test (1 day)
│  ├─ docs/openapi/jobs.yaml (manual or utoipa-generated)
│  └─ tests/contracts/test_jobs_rest.py
│
├─ Task 2: Implement in Rust (3 days)
│  └─ rust/gateway/src/routes/jobs.rs (REST JSON endpoints)
│
├─ Task 3: Write unit tests with harness (1 day)
│  └─ rust/gateway/tests/jobs_test.rs (uses GatewayHarness)
│
├─ Task 4: Write equivalence test (1 day)
│  └─ tests/migration/test_jobs_equivalence.py (vs Python REST)
│
├─ Task 5: Fix until equivalent (1-2 days)
│  └─ Iterate until all tests pass
│
└─ Task 6: Merge (1 day)
   └─ All harness tests must pass in CI
```

**Total:** 8-9 days per story WITH harness (vs 5-7 days without + production bugs)

### Phase 2 Stories (Add gRPC) — P2.1 onwards

```
Story P2.1: Add Connect-RPC Protocol Support
├─ Task 1: Implement Tonic gRPC server
├─ Task 2: Add Connect-Web translation layer
├─ Task 3: Dual-protocol routing (REST + gRPC)
├─ Task 4: Write proto contract tests (NOW use buf-generated schemas)
│  └─ tests/contracts/test_jobs_grpc.py
├─ Task 5: Validate both protocols pass equivalence
└─ Task 6: Merge
```

**Note:** Proto contract validation becomes relevant in Phase 2 after gRPC is implemented.

---

## 6. Success Metrics

| Metric | Target |
|--------|--------|
| **OpenAPI coverage** | 100% of REST endpoints documented |
| **Contract coverage (REST)** | 100% of REST endpoints validated vs OpenAPI |
| **Contract coverage (gRPC)** | 100% of proto methods validated (Phase 2+) |
| **Equivalence coverage** | 100% of migrated endpoints have Python comparison |
| **JWT compatibility** | 100% token interchangeability (Rust ↔ Python) |
| **Database compatibility** | Both services can read each other's data |
| **Provider mock coverage** | 100% of external APIs mocked (zero cost testing) |
| **Production incidents** | ≤1 per migration phase |
| **Performance regression** | 0% slower than Python (ideally 2-10x faster) |

---

## 7. Cost-Benefit Analysis

### Without Harness

| Cost Item | Amount |
|-----------|--------|
| API testing costs | $500/week × 4 weeks = **$2,000** |
| Production incidents | 5-10 incidents × $2K-5K = **$10K-50K** |
| Debugging time | 4-8 weeks × $10K/week = **$40K-80K** |
| **Total Risk** | **$52K-132K** |

### With Harness

| Cost Item | Amount |
|-----------|--------|
| Harness development | 17 engineer-days × $2K/day = **$34K** |
| API testing costs | **$0** (mocks) |
| Production incidents | 0-1 incidents × $2K = **$0-2K** |
| Debugging time | **Minimal** |
| Harness maintenance (post-migration) | $5K/year (permanent harnesses only) |
| **Total Cost (Year 1)** | **$36K-41K** |

**Savings:** $16K-96K (Year 1)

**ROI:** 1.5-4x return on harness investment

**Note:** Temporary migration harnesses (`tests/migration/`) are deleted after migration completes (~12 months), reducing ongoing maintenance to permanent harnesses only.

---

## 8. Resource Requirements

| Role | Effort | Timeline |
|------|--------|----------|
| Backend Engineer (Python) | 6 days | Week 1 (OpenAPI + REST validation + provider mocks), Week 4 (migration harnesses) |
| Backend Engineer (Rust) | 5 days | Week 1 (JWT fix), Week 2 (Rust harnesses + benchmarks) |
| Backend Engineer (Go) | 3 days | Week 3 (Go harnesses) |
| QA Engineer | 3 days | Week 4 (E2E + rollback + perf comparison) |

**Total:** 17 engineer-days = 3.4 weeks (parallelizable to 3-4 calendar weeks)

**Critical Path:**
1. Week 1, Day 1: Fix JWT incompatibility (BLOCKING)
2. Week 1, Day 1-2: Generate OpenAPI schema
3. Week 1, Day 2-5: Provider mocks + REST validation
4. Week 2-4: Parallel harness development

---

## 9. Risk Analysis

### Harness-First Risks

| Risk | Mitigation |
|------|------------|
| Takes longer than 4 weeks | Start with highest-value harnesses first; defer Go/Python harnesses if needed |
| Doesn't catch real bugs | Validate against known Python bugs as smoke test |
| Over-engineering | Keep simple, add features only when needed |
| Test flakiness blocks CI | Quarantine flaky tests, fix within 24h SLA |
| JWT migration breaks existing sessions | Dual-validate (accept old + new) during transition |

### No-Harness Risks (MUCH HIGHER)

| Risk | Impact | Probability |
|------|--------|-------------|
| Production bugs from migration | Severe | 80% |
| API contract breaks | Severe | 70% |
| $2K-5K API cost for testing | Medium | 100% |
| No rollback confidence | Severe | 60% |

**Conclusion:** Harness-first is dramatically lower risk.

---

## 10. Next Steps

### Immediate (This Week)

1. **Review this plan** with migration team
2. **Get approval** from lead developer
3. **Assign resources** (1-2 engineers for Week 1)

### Week 1 (If Approved)

1. **Day 1 (BLOCKING):** Fix JWT schema incompatibility (choose Option A or B)
2. **Day 1-2:** Generate OpenAPI schema (utoipa annotations)
3. **Day 2:** Build REST contract validator
4. **Day 3-5:** Build provider mock harness (8 APIs)
5. **Milestone:** Zero-cost testing infrastructure + JWT compatibility

### Week 2-4

Continue harness implementation per timeline above.

### Post-Harness (Week 5+)

Resume migration with confidence. Every new service:
- Must pass contract tests
- Must pass equivalence tests  
- Must not regress performance
- Cannot merge without harness coverage

---

## 11. Production Rollout Strategy

### Phased Traffic Shifting (Per Endpoint)

```
Stage 1: Shadow Mode (Week 1 of rollout)
├─ Python receives 100% traffic, returns response
├─ Rust receives 100% traffic in parallel, response discarded
└─ Compare outputs in background, log divergences

Stage 2: Canary (Week 2)
├─ Rust serves 1% of traffic
├─ Monitor error rate, p95 latency, business metrics
└─ Auto-rollback if error rate > 0.1% or p95 > Python + 10%

Stage 3: Progressive Rollout (Week 3-4)
├─ 1% → 10% → 25% → 50% → 100%
├─ 24-hour soak time at each stage
└─ Manual approval gate at 50% → 100%

Stage 4: Cutover (Week 5)
├─ Rust serves 100%, Python kept hot for 7 days
├─ Decommission Python after 7-day grace period
└─ Delete migration harness for that endpoint
```

### Feature Flag Infrastructure

```python
# Use Unleash (open-source) or LaunchDarkly
# Each migrated endpoint gets a flag:

# python/dashboard/v2/auth.py (proxy layer)
async def signup(request):
    if feature_flags.is_enabled("rust_auth_signup", user_id=request.user_id):
        return await rust_gateway.proxy(request)
    return await python_signup_legacy(request)
```

**Flag naming convention:** `rust_<service>_<endpoint>` (e.g., `rust_auth_signup`)

**Kill-switch SLA:** Disable any flag in <60 seconds without deploy.

### Rollback Triggers (Automatic)

| Trigger | Action |
|---------|--------|
| Error rate > 0.1% for 5 min | Auto-rollback to Python |
| p95 latency > Python + 20% for 10 min | Auto-rollback |
| Equivalence test fails in prod (sampling) | Page on-call, manual decision |
| 5xx spike > 10/min | Auto-rollback |

### Deliverables

- ✅ Unleash/LaunchDarkly integration
- ✅ Per-endpoint feature flags (~30 flags)
- ✅ Shadow mode infrastructure (`tests/migration/shadow_mode.py`)
- ✅ Auto-rollback rules in deployment config
- ✅ Runbook: `docs/runbooks/rollback-migration.md`

---

## 12. Observability Strategy

### Three-Pillar Approach

**1. Distributed Tracing (OpenTelemetry)**
```rust
// rust/gateway/Cargo.toml
opentelemetry = "0.21"
opentelemetry-otlp = "0.14"
tracing-opentelemetry = "0.22"

// Every request gets a trace_id propagated across:
// Rust gateway → Python services → Postgres → Redis
```

**Goal:** Same `trace_id` visible in Python and Rust dashboards (Jaeger/Tempo).

**2. Metrics (Prometheus)**

```rust
// Standard metrics per endpoint:
http_requests_total{service="rust-gateway", endpoint="/auth/signup", status="200"}
http_request_duration_seconds{service="rust-gateway", endpoint="/auth/signup", quantile="0.95"}
auth_failed_total{service="rust-gateway", reason="invalid_password"}
```

**Comparison Dashboard (Grafana):**
```
┌─────────────────────────────────────────┐
│ Endpoint: /api/v2/auth/signup           │
├─────────────────────────────────────────┤
│ Python p95:  28ms │ Rust p95:  12ms ✅  │
│ Python err:  0.3% │ Rust err:  0.1% ✅  │
│ Python RPS:  450  │ Rust RPS:  1,200 ✅ │
└─────────────────────────────────────────┘
```

**3. Structured Logs (JSON)**

```rust
// Rust uses tracing crate with JSON formatter
tracing::info!(
    user_id = %user.id,
    workspace_id = %user.workspace_id,
    duration_ms = elapsed.as_millis(),
    "user signed up"
);
```

**Goal:** Logs parseable by same Loki/ELK queries that work for Python.

### Production Equivalence Sampling

```python
# tests/migration/prod_equivalence_sampler.py (~150 LOC)
# Runs 24/7 in production, samples 0.1% of requests
async def sample_and_compare():
    # Hit both Python and Rust with same payload (read-only endpoints)
    # Log divergences to Sentry/Datadog
    # Alert if divergence rate > 0.5%
```

### Deliverables

- ✅ OpenTelemetry integration (Rust + Python)
- ✅ Prometheus metrics for all migrated endpoints
- ✅ Grafana comparison dashboard (Python vs Rust side-by-side)
- ✅ Structured JSON logs (parseable by existing tooling)
- ✅ Production equivalence sampler (0.1% traffic)
- ✅ Sentry alerts for divergence > 0.5%

---

## 13. Database Schema Realignment

> **⚠️ REVISED (v4):** The original v3 plan assumed Rust used UUIDs and prescribed a
> "dual-write with UUID backfill" strategy. **Code inspection during Week 1 Day 1
> proved this wrong and unnecessary.** The Rust gateway had built a *fiction* schema
> that matches neither production nor the migration goal. There is **no UUID backfill**.
> The correct strategy is to **realign Rust to Python's existing integer-keyed schema.**

### The Real Problem (Discovered, Not Assumed)

```
Python (existing production — source of truth):
├─ users:             SERIAL int id, role, display_name,
│                     active_workspace_id, mfa_*, disabled, password_hash
├─ workspaces:        SERIAL int id, slug, plan, owner_user_id
├─ workspace_members: (workspace_id, user_id, role)  ← workspace-scoped roles
├─ sessions:          opaque refresh_token_hash (NOT JWT)
└─ ~50K rows of live production data

Rust (P1.2–P1.4 — fiction schema, ZERO users):
├─ users:             gen_random_uuid()::text id, full_name, workspace_id (TEXT)
├─ workspaces:        gen_random_uuid()::text id, owner_id
├─ user_roles:        (user_id, role)            ← table that doesn't exist in prod
└─ refresh tokens:    issued as JWTs             ← incompatible with sessions model
```

**Root cause:** Rust invented its own tables instead of reading Python's. Since Rust
has **zero users** and Python is **live**, Rust must conform — not the reverse.

### Strategy: Realign Rust to Production Schema (No Backfill, No Dual-Write)

**Step 1: Drop the fiction migration**
```
rust/gateway/migrations/001_create_users_and_workspaces.sql  → DELETE
```
Rust does not own these tables. It reads/writes Python's existing schema. Schema
ownership stays with Python's migration system until the service is fully migrated.

**Step 2: Realign Rust models to integer keys**
```rust
// rust/gateway/src/auth/models.rs
pub struct User {
    pub id: i64,                 // was String (UUID)
    pub email: String,
    pub password_hash: String,
    pub display_name: Option<String>,   // was full_name
    pub role: String,            // global role (users.role)
    pub active_workspace_id: Option<i64>,
    pub disabled: bool,
}
// Roles read from workspace_members, NOT user_roles:
//   SELECT role FROM workspace_members WHERE workspace_id=$1 AND user_id=$2
```

**Step 3: Adopt opaque refresh tokens (Python's model)**
```rust
// Refresh tokens are random opaque tokens stored hashed in `sessions`,
// NOT JWTs. Matches Python so refresh works across both services.
//   INSERT INTO sessions (user_id, refresh_token_hash, expires_at) ...
```

**Step 4: JWT `sub` now carries a stringified int**
Because `User.id` is `i64`, the JWT `sub` becomes `user.id.to_string()` → `"123"`,
which Python's `int(claims["sub"])` decodes successfully. ✅ (Completed conceptually
in the Week 1 Day 1 JWT fix; this step makes the *value* correct, not just the shape.)

### Why This Is Strictly Better Than v3's UUID Backfill

| v3 (UUID backfill) | v4 (Realign to int) |
|--------------------|---------------------|
| Add `id_uuid` columns to prod | No schema changes to prod |
| Backfill 50K rows | Zero backfill |
| Dual-write coordination (race conditions) | No dual-write — single int key |
| 6-month int→UUID cutover | No cutover needed |
| New failure modes in prod | Prod untouched |

### Schema Compatibility Tests

```python
# tests/migration/test_schema_compatibility.py
async def test_rust_reads_python_created_user():
    # Python creates user (int id)
    py = await python_dashboard.register(email="t@ex.com", ...)

    # Rust must read the SAME row by int id
    rust_user = await rust_gateway.get_user(id=py["user_id"])
    assert rust_user.email == "t@ex.com"

async def test_rust_token_decodes_in_python():
    # Rust signs in → token.sub is a stringified int
    tok = await rust_gateway.signin("t@ex.com", "pw")
    claims = python_dashboard.verify_token(tok.access_token)  # int(sub) works
    assert claims.user_id == py["user_id"]
```

### Deliverables

- ✅ Delete `rust/gateway/migrations/001_*.sql` (fiction schema)
- ✅ Realign `models.rs` to integer keys + `workspace_members` + `users.role`
- ✅ Opaque refresh tokens via `sessions` table (drop JWT-refresh)
- ✅ Shared `AUTH_JWT_SECRET` across Rust + Python (done in Week 1 Day 1)
- ✅ Schema compatibility test suite (replaces reconciliation suite)
- ✅ Runbook: `docs/runbooks/db-migration-rollback.md`

> **Note:** Section 11's dual-write/shadow infrastructure still applies at the
> *request* level (compare responses), but there is **no database dual-write** —
> both services share one integer-keyed schema throughout the migration.

---

## 14. Load & Security Testing

### Load Testing (K6)

**Why:** Criterion benchmarks are single-threaded micro-benchmarks. Production has concurrent load.

```javascript
// tests/load/auth_load_test.js
import http from 'k6/http';
import { check } from 'k6';

export let options = {
    stages: [
        { duration: '1m', target: 100 },   // Ramp to 100 RPS
        { duration: '3m', target: 1000 },  // Ramp to 1K RPS
        { duration: '5m', target: 10000 }, // Ramp to 10K RPS
        { duration: '2m', target: 0 },     // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<100'], // 95% under 100ms
        http_req_failed: ['rate<0.001'],  // <0.1% errors
    },
};

export default function() {
    const res = http.post('http://gateway:8080/api/v2/auth/signin', ...);
    check(res, { 'status is 200': (r) => r.status === 200 });
}
```

**Targets:**
| Endpoint | Target RPS | Target p95 | Target Error Rate |
|----------|-----------|------------|-------------------|
| Auth signin | 10K | <100ms | <0.1% |
| Auth signup | 1K | <200ms | <0.1% |
| Read-heavy (e.g., /me) | 50K | <50ms | <0.01% |

### Security Testing

**OWASP Top 10 Coverage:**

```python
# tests/security/test_auth_security.py
def test_sql_injection_email():
    payload = {"email": "admin'--", "password": "x"}
    r = requests.post("/auth/signin", json=payload)
    assert r.status_code in [400, 401]  # Must NOT be 200

def test_jwt_algorithm_confusion():
    # Try to use 'none' algorithm
    forged = jwt.encode({"sub": 1}, "", algorithm="none")
    r = requests.get("/api/v2/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401

def test_password_brute_force_rate_limit():
    for _ in range(20):
        r = requests.post("/auth/signin", json={"email": "x", "password": "y"})
    assert r.status_code == 429  # Rate limited

def test_timing_attack_resistance():
    # Login with wrong password should take same time as valid email
    # Argon2 handles this, but verify in tests
    pass
```

**Tools:**
- **Static analysis:** `cargo audit` (Rust), `bandit` (Python)
- **Dependency scanning:** Dependabot, Snyk
- **Penetration testing:** OWASP ZAP automated scans
- **Secret scanning:** gitleaks pre-commit hook

### Deliverables

- ✅ K6 load test scripts (`tests/load/`)
- ✅ Performance SLA dashboard (RPS targets per endpoint)
- ✅ OWASP Top 10 test suite (`tests/security/`)
- ✅ `cargo audit` + `bandit` in CI
- ✅ Dependabot for Rust + Python + Go
- ✅ OWASP ZAP weekly scan in CI

---

## 15. Test Infrastructure & Operational Standards

### Test Database Strategy

**Rust:** `testcontainers-rs` (ephemeral Postgres per test run)
```toml
# rust/gateway/Cargo.toml
[dev-dependencies]
testcontainers = "0.15"
testcontainers-modules = { version = "0.3", features = ["postgres"] }
```

```rust
// rust/gateway/tests/common/harness.rs
use testcontainers::{clients, images::postgres::Postgres};

impl GatewayHarness {
    pub async fn new() -> Self {
        let docker = clients::Cli::default();
        let postgres_image = Postgres::default();
        let postgres = docker.run(postgres_image);
        let port = postgres.get_host_port_ipv4(5432);
        // ... run migrations, seed data
    }
}
```

**Python:** `pytest-postgresql` (similar pattern)
**Go:** `dockertest` (similar pattern)

### Test Parallelization

**Strategy:** Each test gets its own database schema (not full DB):
```rust
// Each test creates: test_<unique_id> schema
// All tables live in that schema
// Cleanup drops the schema
```

**Result:** 16 parallel test workers possible without contention.

### Execution Time Budget

| Test Tier | Max Duration | Run When | Failure Action |
|-----------|--------------|----------|----------------|
| **Smoke** | <2 min | Pre-commit hook | Block commit |
| **Unit** | <5 min | Every PR | Block merge |
| **Integration** | <15 min | Every PR | Block merge |
| **Equivalence** | <20 min | Every PR | Block merge |
| **Load** | <30 min | Nightly | Slack alert |
| **Security (ZAP)** | <60 min | Weekly | Jira ticket |

**Fast suite (<15 min):** Smoke + Unit + Integration + Equivalence  
**Full suite (<2h):** All of above + Load + Security

### Definition of Done (Per Harness)

| Harness | DoD Criteria |
|---------|-------------|
| **REST Contract Validator** | 100% endpoint coverage, OpenAPI 3.1 compliant, runs in <5min |
| **Provider Mock Harness** | All 8 providers, 95% fixture coverage, <100ms response |
| **Gateway Test Harness** | All routes have tests, ≥80% line coverage, runs in <10min |
| **Equivalence Harness** | All migrated endpoints, JSON diff support, runs in <20min |
| **E2E Harness** | Docker-compose up <60s, smoke tests pass, runs in <15min |
| **Load Harness** | All public endpoints tested, SLA dashboard live |

### Divergence Handling (Intentional Differences)

```python
# tests/migration/divergence_registry.py
INTENTIONAL_DIVERGENCES = {
    "POST /auth/signup": {
        "field": "password",
        "python_behavior": "min 6 chars",
        "rust_behavior": "min 8 chars + complexity",
        "reason": "Security hardening — Rust enforces stronger policy",
        "approved_by": "security-team",
        "approved_date": "2026-06-20",
        "expected_python_409": False,  # Python won't 400, Rust will
    },
}

# Equivalence harness checks registry before failing
async def compare(method, path, payload):
    diff = compute_diff(...)
    if path in INTENTIONAL_DIVERGENCES:
        diff = filter_intentional(diff, INTENTIONAL_DIVERGENCES[path])
    assert diff.empty
```

### Golden File Testing

**Purpose:** Detect silent corruption when both Python and Rust return identically wrong data.

```python
# tests/golden/auth_signup_golden.json (committed to git)
{
  "input": {"email": "test@example.com", "password": "secure123"},
  "expected_response": {
    "user_id": "<UUID>",
    "email": "test@example.com",
    "workspace": {...}
  },
  "expected_db_state": {
    "users": [{"email": "test@example.com", "role": "owner"}],
    "workspaces": [{"name": "Default"}]
  }
}

# tests/golden/test_auth_golden.py
def test_signup_matches_golden():
    golden = load_golden("auth_signup_golden.json")
    actual = rust_gateway.signup(golden["input"])
    assert_matches_golden(actual, golden["expected_response"])
    assert_db_matches_golden(db, golden["expected_db_state"])
```

**Update process:** Reviewed manually when intentionally changing behavior.

### Deliverables

- ✅ testcontainers-rs in Cargo.toml
- ✅ pytest-postgresql in Python dev deps
- ✅ Per-schema test isolation (16 parallel workers)
- ✅ Test tier configuration in CI (smoke/fast/full)
- ✅ DoD checklist per harness
- ✅ Divergence registry with approval workflow
- ✅ Golden file test suite for critical paths

---

## Appendix: File Structure

```
docs/openapi/                     # OpenAPI schemas (NEW)
├── gateway.json                  # Auto-generated from Rust utoipa
├── jobs.yaml
└── *.yaml

tests/
├── contracts/                    # Category 3: Contract compliance
│   ├── rest_validator.py        # OpenAPI/JSON Schema validator (NEW)
│   ├── proto_validator.py       # Proto schema validator (Phase 2)
│   ├── test_gateway_rest.py     # REST contract tests (NEW)
│   ├── test_gateway_grpc.py     # gRPC contract tests (Phase 2)
│   └── test_*_contracts.py      # One per service
│
├── migration/                    # Category 1: Migration validation (temporary)
│   ├── harnesses/
│   │   ├── equivalence_harness.py  # Compare Python vs new
│   │   ├── provider_harness.py      # Mock all external APIs
│   │   └── perf_comparison.py       # Performance comparison dashboard (NEW)
│   ├── test_auth_equivalence.py
│   ├── test_jwt_compatibility.py   # Cross-service JWT validation
│   ├── test_schema_compatibility.py # Database schema validation (NEW)
│   ├── test_rollback.py             # Rollback safety tests (NEW)
│   └── test_*_equivalence.py        # One per migrated service
│
├── e2e/                          # Full-stack tests
│   ├── harness.py                # Docker-compose orchestration
│   └── test_smoke.py
│
├── load/                         # K6 load tests (NEW - Section 14)
│   ├── auth_load_test.js
│   └── *_load_test.js
│
├── security/                     # OWASP Top 10 tests (NEW - Section 14)
│   ├── test_auth_security.py
│   └── test_*_security.py
│
├── golden/                       # Golden file tests (NEW - Section 15)
│   ├── auth_signup_golden.json
│   └── *_golden.json
│
└── fixtures/                     # Shared test data
    ├── llm/
    ├── audio/
    └── images/

docs/runbooks/                    # Operational runbooks (NEW)
├── rollback-migration.md         # Section 11
└── db-migration-rollback.md      # Section 13

rust/gateway/
├── tests/                        # Category 2: Permanent Rust tests
│   ├── common/
│   │   ├── harness.rs           # GatewayHarness
│   │   └── fixtures.rs
│   ├── auth_test.rs
│   ├── middleware_test.rs
│   └── *_test.rs
├── benches/                      # Criterion performance benchmarks (NEW)
│   ├── auth_bench.rs
│   └── *_bench.rs
└── Cargo.toml                    # + criterion dev-dependency

go/shared/testharness/            # Category 2: Permanent Go harness
├── harness.go                    # Reusable for all Go services
└── mocks.go

python/shared/testharness/        # Category 2: Permanent Python harness
├── grpc_harness.py
└── mocks.py
```

---

**END OF PLAN**

**Action Required:** Review + approval before implementation begins.
