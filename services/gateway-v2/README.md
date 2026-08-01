# Gateway v2 (Node/Fastify)

**Status:** 🚧 In Development (Phase 2)  
**Framework:** Fastify 5 + TypeScript  
**Replaces:** `services/gateway` (Rust/Axum)

---

## Overview

Gateway v2 is a complete rewrite of the Autoniix API Gateway in Node.js/Fastify, part of the two-language simplification migration (ADR-004).

**Why rewrite?**
- **Build speed:** 30-60s (Node) vs. 8-15min (Rust cold build)
- **CI simplicity:** Eliminate Rust toolchain, sqlx cache, cross-compilation
- **Developer velocity:** Faster iteration, simpler debugging, unified stack

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Fastify Server (Port 8080)                     │
├─────────────────────────────────────────────────┤
│  Middleware:                                     │
│  - Helmet (security headers)                    │
│  - CORS                                          │
│  - Rate limiting                                 │
│  - JWT authentication                            │
│  - Cookie parsing                                │
├─────────────────────────────────────────────────┤
│  Routes:                                         │
│  - /health, /ready                               │
│  - /api/v2/auth/*                                │
│  - /api/v2/jobs/* (TODO)                         │
│  - /api/v2/channels/* (TODO)                     │
│  - ... (18 route modules total)                  │
├─────────────────────────────────────────────────┤
│  Database: postgres (pg client)                  │
│  Contracts: @autoniix/contracts (Zod schemas)   │
└─────────────────────────────────────────────────┘
```

---

## Development

```bash
# Install dependencies
npm install

# Start dev server (watch mode)
npm run dev

# Build for production
npm run build

# Type check
npm run typecheck

# Run tests
npm test
```

---

## Environment Variables

See `.env.example` for all required variables:

- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Min 32 chars for JWT signing
- `CORS_ORIGIN` - Allowed origin for CORS
- `PORT` - Server port (default: 8080)

---

## Migration Status

**Phase 2 Progress:**

- [x] Project structure
- [x] Fastify app setup
- [x] Health endpoints (`/health`, `/ready`)
- [x] Auth routes (stubs)
- [x] JWT middleware
- [x] Database connection (postgres)
- [x] Zod schema validation
- [ ] Auth implementation (login, register, refresh)
- [ ] Job routes
- [ ] Channel routes
- [ ] All 18 route modules from Rust gateway
- [ ] Cron jobs (workspace deletion, hard delete)
- [ ] Feature flag at Caddy level
- [ ] Load testing & benchmarks

**Rollback:** If issues arise, revert Caddy config to route to old Rust gateway.

---

## API Endpoints

### Health
- `GET /health` - Health check with DB status
- `GET /ready` - Readiness probe

### Auth (v2)
- `POST /api/v2/auth/login` - Sign in
- `POST /api/v2/auth/register` - Sign up
- `POST /api/v2/auth/refresh` - Refresh access token
- `POST /api/v2/auth/logout` - Sign out
- `GET /api/v2/auth/me` - Get current user

### Jobs (TODO)
- `GET /api/v2/jobs` - List jobs
- `GET /api/v2/jobs/:id` - Get job
- `POST /api/v2/jobs` - Create job
- `PATCH /api/v2/jobs/:id` - Update job
- `DELETE /api/v2/jobs/:id` - Delete job
- `POST /api/v2/jobs/:id/pause` - Pause job
- `POST /api/v2/jobs/:id/resume` - Resume job
- `POST /api/v2/jobs/:id/retry` - Retry job

---

## Testing

```bash
# Unit tests
npm test

# With coverage
npm run test:coverage

# Integration tests (requires DB)
npm run test:integration
```

---

## Deployment

Gateway v2 will be deployed behind a feature flag at the Caddy level:

```caddyfile
# Route to v2 if header present
@v2 header X-Gateway-Version v2
handle @v2 {
  reverse_proxy localhost:8080
}

# Default: route to Rust gateway
handle {
  reverse_proxy localhost:8000
}
```

This allows instant rollback by removing the header routing rule.

---

## Performance Targets

| Metric | Target | Rust Gateway (baseline) |
|--------|--------|-------------------------|
| Cold start | <2s | ~15s |
| p50 latency | <50ms | ~30ms |
| p99 latency | <200ms | ~150ms |
| Throughput | >5000 req/s | ~8000 req/s |
| Memory | <512MB | ~200MB |

**Note:** We accept slightly higher memory usage and lower throughput in exchange for 10× faster build times and simpler CI.

---

## References

- ADR-004: Two-Language Simplification
- MIGRATION.md: Phase 2 details
- `@autoniix/contracts`: Zod schemas
