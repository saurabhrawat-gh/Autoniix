# Harness Language Strategy — LOCKED DECISION

**Date:** 2026-06-20  
**Status:** 🔒 LOCKED  
**Decision Maker:** Migration Team  
**Applies To:** All test harness infrastructure

---

## Decision

**Write harnesses in the TARGET migration language, with Rust for cross-service validation.**

---

## Language Breakdown

| Service Type | Target Language | Harness Location | Lifespan |
|--------------|----------------|------------------|----------|
| **Rust Services** | Rust | `rust/harness/` | Permanent |
| **Go Services** | Go | `go/harness/` | Permanent |
| **Python Services** (staying) | Python | `tests/harnesses/` | Permanent |
| **Cross-Service Validation** | **Rust** | `rust/harness/` | Permanent |

---

## Migration Scope

From HARNESS-ENGINEERING-PLAN.md:

### Services Migrating to Rust (~13K LOC)
- Gateway (remaining 23 routes)
- Provider Router
- Prompt Compressor
- Assembly/Direction/Secrets/Metrics

**Harness:** `rust/harness/` + `rust/gateway/tests/`

### Services Migrating to Go (~15K LOC)
- 10 microservices (Research, Script, Voice, Image, etc.)
- 2 Temporal workers
- 8 Temporal workflows

**Harness:** `go/harness/` + `go/*/internal/harness/`

### Services Staying in Python (~13K LOC)
- 10 AI services (Brain, Analytics, Preventor, etc.)
- Adding gRPC wrappers only

**Harness:** `tests/harnesses/` (existing Python infrastructure)

---

## Why Rust for Cross-Service Validation?

**Cross-service validation** tests contracts between Python ↔ Rust ↔ Go services via HTTP/gRPC.

**Why Rust (not Python or Go):**

1. **Performance** — Fast execution critical for CI (100+ tests in <5 seconds)
2. **Type Safety** — Compile-time guarantees for HTTP/gRPC clients
3. **Permanent Infrastructure** — Not throwaway code, reusable across all migrations
4. **Language Agnostic** — Can test any service via HTTP/gRPC regardless of implementation language
5. **Single Codebase** — One harness for all cross-service testing
6. **Memory Efficiency** — Low overhead for parallel test execution

**Example:**
```rust
// rust/harness/src/cross_service/mod.rs
pub async fn test_python_rust_equivalence() {
    let python_resp = http_client.post("http://localhost:8000/auth/register", ...).await;
    let rust_resp = http_client.post("http://localhost:8080/api/v2/auth/signup", ...).await;
    
    assert_eq!(python_resp.user.id, rust_resp.user.id);
    assert_eq!(python_resp.access_token_valid(), rust_resp.access_token_valid());
}
```

---

## Rationale

### Previous Approach (Rejected)
- ❌ Python for all harnesses (language-agnostic)
- ❌ Throwaway code (deleted after migration)
- ❌ Slower execution
- ❌ No type safety

### New Approach (Locked)
- ✅ Rust for Rust services (permanent)
- ✅ Go for Go services (permanent)
- ✅ Python for Python services (permanent)
- ✅ Rust for cross-service (performance + type safety)
- ✅ All harnesses are permanent infrastructure

---

## Implementation Impact

### Week 1 (REVISED)

**Before (Python):**
```python
# tests/contracts/rest_validator.py
class RESTValidator:
    def validate_openapi(self, url, method, path, schema):
        # ...
```

**After (Rust):**
```rust
// rust/harness/src/contract/mod.rs
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
        // Type-safe HTTP client + JSON schema validation
    }
}
```

**Benefits:**
- Type-safe request/response structs
- Compile-time validation
- Faster execution (Rust vs Python)
- Permanent infrastructure (not throwaway)

---

## File Structure

```
rust/
├── harness/                    # Cross-service + contract validation
│   ├── Cargo.toml
│   ├── src/
│   │   ├── lib.rs
│   │   ├── contract/          # OpenAPI validation
│   │   │   ├── mod.rs
│   │   │   └── validator.rs
│   │   ├── providers/         # Provider mocks (OpenAI, etc.)
│   │   │   ├── mod.rs
│   │   │   ├── openai.rs
│   │   │   ├── anthropic.rs
│   │   │   └── ...
│   │   └── cross_service/     # Python ↔ Rust ↔ Go tests
│   │       ├── mod.rs
│   │       └── equivalence.rs
│   └── tests/
│       ├── contract_tests.rs
│       ├── provider_tests.rs
│       └── cross_service_tests.rs
│
├── gateway/                    # Service-specific tests
│   └── tests/
│       ├── common/
│       │   └── harness.rs     # GatewayHarness helper
│       └── integration_tests.rs
│
└── ...

go/
├── harness/                    # Go service test utilities
│   ├── go.mod
│   ├── harness.go
│   └── harness_test.go
│
└── services/
    └── research/
        └── internal/
            └── harness/       # Service-specific helpers

tests/
└── harnesses/                  # Python services (staying)
    ├── provider_harness.py
    └── test_provider_harness.py
```

---

## Migration Path

### Phase 1: Rust Harness (Week 1-2)
1. Create `rust/harness/` crate
2. Implement contract validator (OpenAPI)
3. Implement provider mocks (8 providers)
4. Implement cross-service validation
5. Migrate existing Python harness tests to Rust

### Phase 2: Go Harness (Week 3-4)
1. Create `go/harness/` package
2. Implement gRPC test clients
3. Implement Temporal workflow mocks
4. Implement microservice test utilities

### Phase 3: Integration (Week 5+)
1. Cross-service equivalence tests (Python ↔ Rust ↔ Go)
2. Performance benchmarks
3. Load testing
4. CI integration

---

## Success Criteria

- ✅ All Rust services tested with Rust harness
- ✅ All Go services tested with Go harness
- ✅ All Python services tested with Python harness
- ✅ Cross-service validation in Rust
- ✅ Zero throwaway code (all harnesses permanent)
- ✅ CI execution time <5 minutes for smoke tests
- ✅ Type-safe test infrastructure
- ✅ $500/week cost savings (provider mocks)

---

## Related Documents

- `docs/architecture/harness-engineering-plan.md` — Overall harness plan
- `docs/migration/WEEK1-COMPLETE.md` — Week 1 summary (Python, to be revised)
- `docs/future/post-harness-tasks.md` — Post-harness tasks

---

## Status

🔒 **LOCKED** — This decision is final. All future harness work follows this strategy.
