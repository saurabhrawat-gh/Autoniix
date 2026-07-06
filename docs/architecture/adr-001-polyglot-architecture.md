# ADR-001: Polyglot Architecture (Rust + Go + Python) with Connect-RPC

**Status:** Accepted
**Date:** 2026-06-20
**Decision Owners:** Saurabh Rawat (Owner), Cascade (Architect)
**Supersedes:** —
**Superseded By:** —

---

## Context

Autoniix is an agentic YouTube automation platform with a vision to scale from 1 user today to potentially **billions of users** in the future. The current backend is a Python-only monolith spread across ~50K lines of code in `src/`. It works for the current 1-user scale but has structural bottlenecks that will become fatal at growth.

This ADR locks the architecture from foundation to billion-user scale, including:
- Backend language split
- Frontend ↔ Backend protocol
- Inter-service communication protocol
- Database, caching, messaging, observability stacks
- Repository structure
- Trigger-based scale-out strategy
- 10-user → 1B-user evolution path

---

## Decision Summary

| Concern | Decision |
|---------|----------|
| Backend languages | Rust (CPU/perf) + Go (IO/orchestration) + Python (AI/ML) |
| Frontend ↔ Backend | **Connect-RPC** (gRPC-Web protocol, dual JSON+binary) |
| Backend ↔ Backend | **Native gRPC** over HTTP/2 |
| Contract source of truth | Protocol Buffers in `proto/` |
| Repository structure | **Microservices + Monorepo** (Bazel/Buck2/Turborepo) |
| Primary database | PostgreSQL → CockroachDB (at trigger) |
| Cache / pub-sub | Redis → Redis Cluster → NATS JetStream → Kafka (at triggers) |
| Object storage | MinIO → MinIO + Cloudflare R2 tee (at trigger) |
| Workflow engine | Temporal (self-hosted) → Temporal Cloud (at trigger) |
| Service mesh | None today → Linkerd (when on k8s) |
| Edge / CDN | Caddy today → Cloudflare (at public launch) |
| Container orchestration | Docker Compose → Kubernetes (when >5 hosts) |
| Observability | Prometheus + Grafana + Loki + Sentry (current) |

---

## Part 1: The "Why" — Problems This Architecture Solves

### 1.1 Python GIL & Memory Footprint

The Python GIL means a single process can only execute one CPU instruction at a time across all threads. Temporal workers running 10+ concurrent activities (research, script, voice fan-out) experience contention even though most of the work is IO-bound.

Each Python service consumes 80–200MB RAM baseline before doing any work. With 15+ microservices, the baseline memory is 2–3GB.

### 1.2 Cold Start Latency

Python services importing heavy packages (`temporalio`, `openai`, `anthropic`, `llmlingua`, `pandas`) take 3–8 seconds to start. Kubernetes autoscaling and serverless deployment patterns assume sub-second cold starts. Rust + Go services start in milliseconds.

### 1.3 Cost at Horizontal Scale

A Python container running an IO-bound service uses ~200MB RAM and ~5% of a CPU core for ~50 RPS throughput. The equivalent Go service uses ~20MB RAM and ~2% CPU for ~500 RPS. **10x throughput at 1/5 the resources** = ~50x cost efficiency.

### 1.4 Frontend Type Safety

The Next.js dashboard calls 200+ REST endpoints via hand-written `api-v2.ts` clients. There is no compile-time guarantee that the backend response matches the frontend's expected shape. Production bugs from field renames have happened repeatedly.

### 1.5 Real-Time Streaming Fragility

The current WebSocket implementation (`/api/ws/events`, `/api/ws/progress/{id}`) is fragile: connection drops, no auto-reconnect, no replay on reconnect, no per-message acknowledgment. At billion-user scale this is unworkable.

---

## Part 2: The Language Split

### 2.1 🦀 Rust — The Performance Layer

**Used for:** Anything latency-critical, CPU-bound, or security-sensitive.

| Component | Module Today | New Location | Justification |
|-----------|-------------|--------------|---------------|
| API Gateway / BFF | `src/services/dashboard/v2/` | `rust/gateway/` | 27 route modules, ~10K LOC. Auth, rate limiting, JSON ser/de — all per-request CPU work. Axum can serve 100K+ RPS per node. |
| Provider Router | `src/llm/router.py`, `src/providers/llm/` | `rust/provider-router/` | Token counting, cost calculation, fallback logic. Called on every LLM request — the hottest hot path. |
| Prompt Compressor | `src/llm/compressor.py` | `rust/compressor/` | LLMLingua + custom pruning. String-heavy. Rust SIMD is orders of magnitude faster. |
| Secrets Vault | `src/providers/secrets.py` | `rust/secrets/` | Memory safety for credentials. Zero-copy deserialization. No GC means no chance of credentials leaking to swap. |
| Assembly Engine | `src/workers/activities/assembly.py` | `rust/assembly/` | Scene composition, timing math. Pure compute. |
| Direction Engine | `src/workers/activities/direction.py` | `rust/direction/` | Video direction layout. CPU-intensive. |
| Observability Hot Path | `src/observability/metrics.py` | `rust/metrics/` | Metric collection must never block. |

**Tech stack:**
- Runtime: **Tokio** (async runtime)
- Web: **Axum** (vs Actix-web — better ergonomics, same performance)
- gRPC: **Tonic** (de-facto standard, official tokio project)
- DB: **sqlx** (compile-time SQL verification)
- Serialization: **prost** (protobuf), **serde** (JSON when needed)

### 2.2 🐹 Go — The Concurrency Layer

**Used for:** Temporal workflows, IO-bound fan-out, network-heavy services.

| Component | Module Today | New Location |
|-----------|-------------|--------------|
| Temporal Workflow (Video Production) | `src/temporal_workflows/video_production.py` | `go/temporal-worker-production/workflows/` |
| Temporal Workflow (Scheduler) | `src/temporal_workflows/daily_scheduler.py` + 6 others | `go/temporal-worker-scheduler/workflows/` |
| Temporal Production Worker | `src/workers/run_production.py` | `go/temporal-worker-production/` |
| Temporal Scheduler Worker | `src/workers/run_scheduler.py` | `go/temporal-worker-scheduler/` |
| Research Service | `services/research/` | `go/service-research/` |
| Script Service | `services/script/` | `go/service-script/` |
| Voice Service | `services/voice/` | `go/service-voice/` |
| Thumbnail Service | `services/thumbnail/` | `go/service-thumbnail/` |
| Delivery Service | `services/delivery/` | `go/service-delivery/` |
| WebSocket / Streaming Hub | inline in `dashboard/main.py` | `go/streaming-hub/` |
| Notification Dispatcher | `src/services/dashboard/v2/notifications.py` (dispatch portion) | `go/notification-dispatcher/` |

**Why Go for Temporal:**
- The Go SDK is **the** reference implementation (Temporal was originally Go-only).
- Workflow determinism is enforced at compile time.
- Goroutine-per-activity model handles 10,000+ concurrent activities trivially.
- Single binary deployment = no Python venv hell.

**Tech stack:**
- HTTP: stdlib `net/http` (or **chi** for routing if needed)
- gRPC: **google.golang.org/grpc** + **buf** for codegen
- DB: **pgx** (PostgreSQL driver, faster than database/sql)
- Logging: **slog** (stdlib since 1.21)
- Config: **viper** or **koanf**

### 2.3 🐍 Python — The AI/ML Layer

**Used for:** Anything that calls LLMs, runs ML models, or uses the Python data science ecosystem.

| Component | Stays at | New gRPC interface |
|-----------|----------|-------------------|
| Brain Service | `src/services/brain/` → `python/brain/` | Yes |
| Critic Agent | `src/agents/critic.py` → `python/agent-critic/` | Yes |
| Preventor Agent | `src/agents/preventor.py` → `python/agent-preventor/` | Yes |
| Reflector | `src/services/brain/reflector.py` → `python/brain/` (same service) | Yes |
| Analytics Service | `src/services/analytics/` → `python/analytics/` | Yes |
| Experiments Engine | `src/services/experiments/` → `python/experiments/` | Yes |
| Quality Gates | `src/intelligence/` → `python/quality-gates/` | Yes |
| Finishing Service | `src/services/finishing/` → `python/finishing/` | Yes |
| Brand Service | `src/workers/activities/brand.py` → `python/brand/` | Yes |
| Editor Service | `src/workers/activities/editor.py` → `python/editor/` | Yes |
| Embeddings Service | `src/llm/embeddings.py` → `python/embeddings/` | Yes |

**Why keep Python:**
- The entire ML ecosystem (numpy, scipy, scikit-learn, sentence-transformers, llmlingua) is Python-first.
- LangChain / LlamaIndex / OpenAI / Anthropic SDKs are Python-native.
- These services are LLM-API-bound — Rust/Go offers no performance gain.
- Rewriting prompt chains in Rust is a massive cost with zero benefit.

**Tech stack:**
- gRPC: **grpcio** (native C extensions, fastest Python gRPC)
- Async: **asyncio** + **uvloop**
- DB: **asyncpg** (already in use)
- HTTP (for LLM calls): **httpx**
- Logging: **structlog** (already in use)

---

## Part 3: Communication Protocols

### 3.1 Frontend ↔ Gateway: Connect-RPC

**Connect-RPC** is Buf's modern implementation of gRPC for browsers. Same `.proto` files, but:
- Works in every browser (no special plugin)
- Negotiates between binary protobuf (fast, prod) and JSON (debuggable, dev) via `Content-Type` header
- Uses Server-Sent Events for streaming (works through every firewall)
- Generates type-safe TypeScript clients automatically
- Same `.proto` generates native iOS (Connect-Swift) and Android (Connect-Kotlin) clients when mobile is needed

**Why not GraphQL:**

| Concern | GraphQL | Connect-RPC |
|---------|---------|-------------|
| Type safety FE↔BE | ✅ via codegen | ✅ via codegen |
| Caching | ❌ Hard (per-query unique) | ✅ Easy (HTTP standard) |
| Query cost predictability | ❌ Arbitrary complexity | ✅ Per-endpoint |
| Streaming | ✅ Subscriptions | ✅ Native |
| N+1 server-side | ❌ Needs DataLoader for every relation | ✅ Server controls fetch shape |
| Payload size | Smaller (no over-fetch) | 40% smaller (binary) |
| Backend protocol match | ❌ Translation needed | ✅ Same protobuf |
| Mobile clients | Manual setup | ✅ Auto |

**Why not REST + OpenAPI:**
- No type safety enforcement (OpenAPI is a spec, not a contract)
- No streaming
- Versioning hell at scale
- No backend match with gRPC services

**Why not tRPC:**
- TypeScript-only. Backed by Rust gateway = impossible.

### 3.2 Backend ↔ Backend: Native gRPC

- Binary protocol over HTTP/2 multiplexing
- All services expose gRPC servers via the Connect protocol (so the same client code works internally and externally)
- mTLS via Linkerd when on Kubernetes
- Distributed tracing headers injected via OpenTelemetry

### 3.3 Async Events: Redis Streams → NATS JetStream → Kafka

| Scale | Tech | Why |
|-------|------|-----|
| Today (1–10K users) | Redis Streams (already in use as Redis Pub/Sub) | Sufficient, low ops |
| 100K users | Redis Streams with consumer groups | Durability + replay |
| 1M users | NATS JetStream | Microsecond latency, durable, lightweight |
| 10M+ users | Apache Kafka (Confluent Cloud) | Cross-region replication, ordering guarantees |

**Event shape:** Protocol Buffers (same as RPC). Single contract everywhere.

### 3.4 Public API (Future)

When external developers need access:
- Same `.proto` files → generate REST + OpenAPI via `protoc-gen-openapiv2`
- Connect-RPC gateway exposes both grpc-web AND REST endpoints from the same handlers
- Per-tenant API keys, scoped by workspace

---

## Part 4: Data Layer

### 4.1 Primary Database

**Today: Single PostgreSQL 15 with pgvector**

**Scale evolution:**

| User Tier | DB Strategy | Trigger |
|-----------|------------|---------|
| 1–10K | Single PG + nightly backups | Foundation |
| 10K–100K | Single PG + 1–2 read replicas | DB pool pressure > 0.5 sustained |
| 100K–1M | PG + Citus extension OR PG + PgBouncer + 5 replicas | Single primary hits 80% CPU |
| 1M–100M | **CockroachDB** (PostgreSQL wire-compatible) | PG can't be sharded without rewrite |
| 100M–1B | CockroachDB multi-region + global tables for shared data | First non-NA paying customer |

**Why CockroachDB over alternatives:**

| Alternative | Why not |
|-------------|---------|
| Vitess (MySQL) | Not PG-compatible. Migration cost huge. |
| Spanner | GCP lock-in. Expensive. |
| Aurora (AWS) | Single-region active. AWS lock-in. |
| AlloyDB | GCP lock-in. Not multi-region active-active. |
| CitusData | Sharding works but multi-region is bolt-on. |
| TiDB | MySQL-compatible. Worse PG migration. |
| YugabyteDB | Similar to Cockroach, smaller community. |

**CockroachDB wins because:** PostgreSQL wire protocol + range-based auto-sharding + active-active multi-region + serializable isolation by default.

### 4.2 Specialized Data Stores

| Workload | Today | Scale-Out | Trigger |
|---------|-------|-----------|---------|
| Cache + Pub/Sub | Redis single | Redis Cluster | Memory > 70% sustained |
| Time-series metrics | Prometheus (15d retention) | VictoriaMetrics (90d retention, 10x cheaper than Mimir) | Prom hits 30d storage cap |
| Vector embeddings | pgvector | Qdrant | >100M vectors |
| Full-text search | PostgreSQL FTS | Meilisearch | Search p95 > 200ms |
| Audit log | `audit_log_v2` table | **ClickHouse** | Table > 100M rows |
| Object storage (renders) | MinIO single | MinIO + Cloudflare R2 tee | First MinIO outage OR multi-region need |
| Hot session store | Redis | Redis Cluster | Memory pressure |
| Background job queue | Redis Streams | Temporal (already in use for workflows) | Foundation |

### 4.3 Data Migration Strategy (Zero-Downtime)

For every storage migration:
1. **Dual-write phase:** Application writes to both old and new store.
2. **Backfill phase:** Background job copies historical data.
3. **Dual-read phase:** Application reads from new, falls back to old on miss.
4. **Verification phase:** Compare row counts, sample checksums.
5. **Cutover phase:** Stop writing to old. Monitor for 1 week.
6. **Cleanup phase:** Drop old store.

This pattern works for PG → CockroachDB, Redis → Redis Cluster, MinIO → MinIO+R2.

---

## Part 5: Edge, Load Balancing, and Service Mesh

### 5.1 Edge Layer (Global)

**Cloudflare** (when public launch fires the trigger):
- 200+ POPs worldwide → static asset cache
- DDoS protection (free tier covers up to 100Gbps)
- WAF (managed rules + custom for credential stuffing)
- TLS termination at edge
- Bot management
- Smart routing (Argo)
- Workers for ultra-low-latency endpoints (auth check, rate limit lookup)

**Cost at 1M users:** ~$200/month (Pro plan + a bit of Workers usage).

### 5.2 Regional Load Balancer

When on Kubernetes:
- Cloud-provider native (AWS ALB / GCP HTTPS LB / Cloudflare Load Balancing)
- Health checks → drain unhealthy pods
- Connection draining on rolling deploys

When on single VPS (today):
- Caddy (already in use) handles TLS + reverse proxy + cert renewal

### 5.3 Service Mesh

**Today:** None. Direct gRPC calls between containers on Docker network.

**At trigger (move to k8s):** **Linkerd**
- Lighter than Istio (10x lower resource footprint)
- mTLS by default
- Built-in retries, timeouts, circuit breakers
- Distributed tracing via OpenTelemetry
- Per-route SLO tracking

### 5.4 gRPC-Web Translation

Envoy or the Rust gateway itself handles the gRPC-Web ↔ native gRPC translation:
```
Browser (Connect-Web)
  ↓ HTTP/1.1 or HTTP/2 with framing
Rust Gateway (also speaks Connect natively)
  ↓ HTTP/2 native gRPC
Internal services
```

No separate Envoy needed if the gateway speaks Connect — which it will (Tonic + tower-http supports gRPC-Web reflection out of the box).

---

## Part 6: Compute & Orchestration

### 6.1 Container Orchestration

| Scale | Tech | Why |
|-------|------|-----|
| 1–10 users (today) | **Docker Compose** | Single VPS, simple ops |
| 10K users | Docker Compose on 3–5 VPS hosts (Swarm or just SSH) | Still simple |
| 100K users | **Kubernetes** (EKS / GKE / DigitalOcean) | Need >5 hosts, autoscaling, rolling deploys |
| 1M+ users | Multi-cluster k8s, federated | Cross-region |

### 6.2 Autoscaling

| Service | Scaling Signal |
|---------|---------------|
| Rust Gateway | RPS + p95 latency (HPA) |
| Go Temporal Workers | Temporal queue depth (KEDA) |
| Go IO services | gRPC RPS + p99 latency |
| Python AI services | LLM in-flight count (KEDA) + GPU utilization (for embedding service) |
| Streaming hub | Active connection count |

### 6.3 GPU / Specialized Compute

**Today:** None. All LLM calls are external (OpenAI/Anthropic/Gemini).

**Future trigger (running own models for cost optimization):**
- **Modal** or **RunPod** for burst inference (per-second billing)
- Dedicated GPU nodes for steady-state inference workloads
- Remotion render pool on dedicated CPU-heavy nodes

### 6.4 Workflow Engine

**Today:** Self-hosted Temporal (`docker-compose.yml`).

**At trigger (>10K workflows/day OR multi-region):** **Temporal Cloud**
- Managed by Temporal Inc.
- Same SDK, zero code change
- Built-in cross-region replication
- $/workflow billing, no infra to manage

---

## Part 7: Observability

| Concern | Tool | Notes |
|---------|------|-------|
| Metrics | **Prometheus** → **VictoriaMetrics** at scale | Already in use |
| Logs | **Grafana Loki** | Already in use, 30d retention |
| Traces | **OpenTelemetry → Tempo** | Add at multi-service scale |
| Errors | **Sentry** | Already in use |
| Real User Monitoring | **PostHog** | Add at public launch |
| Synthetic monitoring | **Checkly** | Add at public launch |
| Cost monitoring | **OpenCost** + Grafana | Add at k8s migration |
| Status page | **Statuspage** or **Instatus** | Add at public launch |

**Standardization rule:** Every service emits in the **OpenTelemetry** format. Backends (Loki, Tempo, Prometheus) are swappable.

---

## Part 8: Security & Compliance

| Layer | Tech | Trigger |
|-------|------|---------|
| Secrets | **Infisical** (current) | Foundation |
| Vault (when Infisical isn't enough) | **HashiCorp Vault** | First compliance audit |
| WAF | Cloudflare WAF + custom rules in Rust gateway | Public launch |
| SSO/SAML | **WorkOS** | First B2B customer |
| OAuth 2.1 | Built into Rust gateway | Foundation |
| API keys | Per-workspace, rotatable, scoped | Foundation |
| Encryption at rest | DB-level (CockroachDB native AES-256) | At CockroachDB migration |
| Encryption in transit | TLS everywhere; mTLS via Linkerd | TLS today, mTLS at k8s |
| Audit log | ClickHouse | When `audit_log_v2` > 100M rows |
| Rate limiting | Cloudflare (edge) + Rust gateway (per-user token bucket) | Foundation for gateway part |
| Compliance | SOC 2 Type I → Type II → ISO 27001 → GDPR | First enterprise customer |

---

## Part 9: Repository Structure (Microservices + Monorepo)

```
autoniix/
├── proto/                          ← THE SOURCE OF TRUTH
│   ├── autoniix/
│   │   ├── v1/
│   │   │   ├── channel.proto
│   │   │   ├── content.proto
│   │   │   ├── job.proto
│   │   │   ├── brain.proto
│   │   │   └── ... (one per domain)
│   │   └── buf.yaml
│   └── buf.gen.yaml                ← codegen config for all 3 langs + TS
│
├── rust/
│   ├── Cargo.toml                  ← workspace root
│   ├── gateway/                    ← Rust service: API gateway
│   ├── provider-router/            ← Rust service: LLM router
│   ├── compressor/                 ← Rust service: prompt compression
│   ├── secrets/                    ← Rust service: secrets vault
│   ├── assembly/                   ← Rust service: scene assembly
│   ├── direction/                  ← Rust service: video direction
│   ├── metrics/                    ← Rust service: observability hot path
│   └── shared/                     ← shared crates (proto bindings, db, telemetry)
│
├── go/
│   ├── go.work                     ← Go workspace
│   ├── temporal-worker-production/ ← Go service
│   ├── temporal-worker-scheduler/  ← Go service
│   ├── service-research/           ← Go service
│   ├── service-script/             ← Go service
│   ├── service-voice/              ← Go service
│   ├── service-thumbnail/          ← Go service
│   ├── service-delivery/           ← Go service
│   ├── streaming-hub/              ← Go service: WebSocket/SSE
│   ├── notification-dispatcher/    ← Go service
│   └── shared/                     ← shared modules (proto, db, telemetry)
│
├── python/
│   ├── pyproject.toml              ← uv workspace
│   ├── brain/                      ← Python service
│   ├── agent-critic/               ← Python service
│   ├── agent-preventor/            ← Python service
│   ├── analytics/                  ← Python service
│   ├── experiments/                ← Python service
│   ├── quality-gates/              ← Python service
│   ├── finishing/                  ← Python service
│   ├── brand/                      ← Python service
│   ├── editor/                     ← Python service
│   ├── embeddings/                 ← Python service
│   └── shared/                     ← shared packages
│
├── frontend/
│   ├── package.json
│   ├── src/
│   ├── public/
│   └── generated/                  ← Connect-Web TS clients (gitignored, built by buf)
│
├── infrastructure/
│   ├── docker-compose.yml          ← dev + small-deploy
│   ├── docker-compose.prod.yml     ← prod single-host
│   ├── helm/                       ← k8s charts (future)
│   │   ├── gateway/
│   │   ├── temporal-workers/
│   │   └── ai-services/
│   ├── terraform/                  ← IaC (future)
│   │   ├── aws/
│   │   ├── gcp/
│   │   └── cloudflare/
│   └── scripts/                    ← bootstrap, migrate, backup, smoke
│
├── docs/
│   ├── architecture/               ← ADRs
│   │   ├── ADR-001-polyglot-architecture.md
│   │   └── ... (one per major decision)
│   ├── runbooks/                   ← incident response
│   └── sprint-audit/               ← per-feature inventories
│
├── tools/
│   ├── codegen/                    ← buf templates, custom plugins
│   └── ci/                         ← shared CI scripts
│
├── .github/
│   └── workflows/
│       ├── proto-validate.yml      ← buf lint + breaking-change check
│       ├── rust-build.yml          ← affected-only Rust builds
│       ├── go-build.yml            ← affected-only Go builds
│       ├── python-build.yml        ← affected-only Python builds
│       ├── frontend-build.yml      ← Next.js build
│       └── integration.yml         ← cross-service smoke tests
│
├── BUILD.bazel                     ← (option A) Bazel root
├── turbo.json                      ← (option B) Turborepo root
└── README.md
```

### Build Tooling: Buck2 vs Bazel vs Turborepo vs Nx

**Recommendation: Start with Turborepo + native build tools per language. Migrate to Buck2 if/when the monorepo exceeds 100K LOC or builds take >10min.**

- **Turborepo:** Trivial setup. Caches per-package. Works great with `cargo`, `go build`, `uv`, `pnpm`. **Pick this first.**
- **Buck2** (Meta): Fastest at scale. Steep learning curve. Adopt when Turborepo is too slow.
- **Bazel** (Google): Most powerful. Hardest to learn. Overkill until 100K+ LOC.
- **Nx:** Frontend-focused. Not great for Rust/Go.

### Codegen: Buf

**Buf** is the standard tool for protobuf:
- `buf lint` — enforces style
- `buf breaking` — blocks breaking changes
- `buf generate` — generates Rust + Go + Python + TS clients from one config
- `buf format` — auto-formats proto files

---

## Part 10: The 10-User Deployment (TODAY)

```yaml
# docker-compose.yml (simplified)
services:
  caddy:                # current
  postgres-app:         # current
  postgres-temporal:    # current
  redis:                # current
  minio:                # current
  temporal:             # current
  rust-gateway:         # NEW — replaces dashboard-bff
  go-worker-production: # NEW — replaces Python worker-production
  go-worker-scheduler:  # NEW — replaces Python worker-scheduler
  go-service-research:  # NEW
  go-service-script:    # NEW
  go-service-voice:     # NEW
  go-service-thumbnail: # NEW
  go-service-delivery:  # NEW
  go-streaming-hub:     # NEW — replaces WS in dashboard-bff
  python-brain:         # current, gRPC interface added
  python-agents:        # current, gRPC interface added
  python-analytics:     # current, gRPC interface added
  python-finishing:     # current, gRPC interface added
  prometheus:           # current
  grafana:              # current
  loki:                 # current
  remotion:             # current (Node.js, stays)
```

**Resource footprint at 10 users:**
- Total RAM: ~3GB
- Total CPU: ~2 idle cores
- Cost: ~$40/month VPS (unchanged)
- p95 latency: <50ms (vs current ~250ms)
- Container startup: ~1s (vs current ~8s)

---

## Part 11: Scale-Out Triggers (Locked)

| Trigger | Action |
|---------|--------|
| DB pool pressure > 0.5 sustained 1h | Add PostgreSQL read replica |
| Single PG > 80% CPU at peak | Begin CockroachDB migration |
| Single Redis > 70% memory | Migrate to Redis Cluster |
| Memory pressure on VPS | Add 2nd VPS host + Docker Swarm OR move to k8s |
| >5 VPS hosts | Migrate to Kubernetes |
| First MinIO outage | Add Cloudflare R2 tee |
| First non-NA paying customer | Add 2nd region + Cloudflare |
| First DDoS attempt OR public launch | Enable Cloudflare WAF |
| First B2B customer | Add WorkOS for SSO/SAML |
| audit_log_v2 > 100M rows | Migrate audit to ClickHouse |
| Redis Streams throughput ceiling | Migrate events to NATS JetStream |
| NATS hits cross-region need | Migrate events to Kafka |
| Prometheus storage > 30d cap | Migrate to VictoriaMetrics |
| Self-hosted Temporal > 10K workflows/day | Migrate to Temporal Cloud |
| First user requests mobile app | Generate Connect-Swift / Connect-Kotlin clients |
| First enterprise compliance need | Begin SOC 2 Type I |

---

## Part 12: Migration Safety

### Dual-Protocol Gateway During Transition

The Rust gateway exposes BOTH protocols simultaneously:

```
Rust Gateway
├── /api/v2/*    → REST + JSON  (old FE clients, all existing pages)
├── /rpc/*       → Connect-RPC  (new FE clients, page-by-page migration)
└── (internal)   → Native gRPC  (downstream services)
```

All three call the SAME internal handlers, which were generated from the SAME `.proto` file. **Nothing breaks.** A page works on REST until the day it's migrated to Connect. The day it migrates, it works on Connect. Pages migrate independently.

### Phased Rollout (Per Service)

Every service migration follows this pattern:
1. **Build new (Rust/Go) service alongside old (Python) service**
2. **Wire both to the same DB/Redis/Temporal**
3. **Switch traffic via feature flag (per-tenant if needed)** — 1% → 10% → 50% → 100%
4. **Monitor metrics + error rates at each step**
5. **Rollback is instant** (flip the flag back)
6. **Delete old service after 2 weeks of 100% on new with zero incidents**

### Database Compatibility

PostgreSQL stays the database throughout. Rust (sqlx) and Go (pgx) and Python (asyncpg) all speak the same wire protocol. There is NO database migration in Phase 1–6. Database migrations (PG → Cockroach) happen later, triggered separately, with the dual-write pattern.

---

## Part 13: Is This Overkill for 10 Users?

**The full billion-user scale-out infrastructure is massive overkill at 10 users.** That's why we DON'T build it until triggers fire. See Part 11.

**The polyglot foundation (Rust + Go + Python + Connect-RPC + Monorepo) is NOT overkill.** It costs the same to run at 10 users or 10 million users:
- Same ~$40/month VPS
- Same single PostgreSQL
- Same single Redis
- Same Docker Compose

The DIFFERENCE is what happens when you scale:
- With the polyglot foundation: scale = add nodes (linear cost growth)
- With a Python monolith: scale = 12-month rewrite at exactly the moment you can't afford to slow down

**Build the foundation that costs the same. Defer the infrastructure that costs more until you NEED it.**

---

## Part 14: Anti-Patterns We Explicitly Avoid

1. **Distributed monolith** — services that share databases or have circular sync calls. Mitigation: strict `.proto` boundaries. Every service owns its own tables.
2. **Premature multi-region** — running multi-region before having multi-region users. Trigger-locked.
3. **Microservices for microservices' sake** — splitting services along arbitrary lines. Our split follows runtime characteristics (CPU/IO/AI).
4. **Hand-written API clients** — every client is generated from `.proto`. No exceptions.
5. **2-Phase Commit (2PC)** — never. Use Temporal Sagas for cross-service transactions.
6. **Shared mutable state across services** — every service owns its data. Communication is via gRPC, never direct DB access.
7. **Latency from Python in hot paths** — Rust handles all hot paths. Python only on LLM-bound paths where Python's overhead is dwarfed by 5s LLM latency.
8. **Multiple sources of truth** — `.proto` is the contract. Database schemas, API responses, frontend types all derive from it.
9. **Tight coupling between frontend deploy and backend deploy** — Connect-RPC contracts can evolve independently as long as `buf breaking` passes.
10. **Manual scale-out** — every scale-out is automated (HPA, KEDA, autoscaling groups).

---

## Part 15: Rejected Alternatives

| Alternative | Why Rejected |
|-------------|-------------|
| All-Rust backend | Python AI ecosystem irreplaceable. Months of needless work. |
| All-Go backend | Same as above. Plus Go's CPU performance < Rust for hot paths. |
| Python monolith (status quo) | GIL, memory, cold-start, no type safety. Fatal at scale. |
| GraphQL frontend | Caching hard. Query cost unpredictable. N+1 nightmare. |
| tRPC frontend | TypeScript-only. Rust gateway makes it impossible. |
| REST + OpenAPI only | No type safety, no streaming, versioning hell. |
| MySQL / Vitess | Not PostgreSQL-compatible. Migration cost huge. |
| Spanner / AlloyDB | Cloud lock-in. Expensive. |
| Istio service mesh | 10x heavier than Linkerd. Overkill. |
| Polyrepo | Atomic contract changes impossible. CI complexity explodes. |
| Modular monolith (Python) | Same Python problems. |
| Microservices in polyrepo | Cross-service refactors become release-coordination nightmares. |

---

## Part 16: Open Questions (To Be Resolved Per Phase)

These are NOT blocking. They get resolved during the relevant phase:

1. **Phase 1:** Buck2 vs Turborepo final decision (recommendation: Turborepo first, migrate to Buck2 if needed)
2. **Phase 2:** OAuth refresh token rotation strategy in Rust (recommendation: opaque tokens stored in Redis)
3. **Phase 3:** Temporal Cloud vs self-hosted final cost analysis (recommendation: self-host until 10K workflows/day)
4. **Phase 4:** LLMLingua port — pure Rust rewrite vs Rust FFI to Python (recommendation: FFI first, rewrite if FFI bottlenecks)
5. **Phase 5:** Brain service — single gRPC service vs separate microservice per agent (recommendation: single service with internal agent registry, split if hot)
6. **Phase 6:** Per-tenant feature flag granularity (recommendation: workspace-level, not user-level)

---

## Part 17: Glossary

- **Connect-RPC:** Modern gRPC protocol for browsers, by Buf
- **Buf:** Tool for protobuf linting, generation, and breaking-change detection
- **Tonic:** Rust gRPC framework
- **Axum:** Rust web framework (Tokio ecosystem)
- **pgx:** Go PostgreSQL driver
- **sqlx:** Rust SQL toolkit with compile-time SQL verification
- **KEDA:** Kubernetes Event-Driven Autoscaling
- **HPA:** Horizontal Pod Autoscaler
- **CockroachDB:** PostgreSQL-compatible distributed database
- **NATS JetStream:** Lightweight durable messaging system
- **Linkerd:** Lightweight service mesh
- **Temporal:** Workflow engine (already in use)
- **Saga pattern:** Cross-service distributed transaction pattern (used via Temporal)
- **MTLS:** Mutual TLS authentication
- **Bounded context:** DDD concept — a logical boundary of related entities

---

## Approval

- **Architect (Cascade):** ✅ Approved 2026-06-20
- **Owner (Saurabh Rawat):** ✅ Approved 2026-06-20

This ADR is the constitution. All future PRs that contradict this document require a new ADR superseding the relevant section.
