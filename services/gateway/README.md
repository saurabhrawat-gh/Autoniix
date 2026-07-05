# Autoniix Gateway

High-performance Rust API gateway built with Axum and Tonic.

## Features

- **Dual-protocol support**: REST (JSON) + Connect-RPC (gRPC-Web)
- **Type-safe contracts**: Generated from Protocol Buffers
- **Observability**: Structured JSON logging with tracing
- **Health checks**: Kubernetes-ready `/health/live` and `/health/ready` endpoints
- **Production-ready**: CORS, compression, graceful shutdown

## Architecture

```
Gateway
├── REST JSON endpoints    → /api/v2/*    (existing clients)
├── Connect-RPC endpoints  → /rpc/*       (new clients, phase 2)
└── Internal gRPC clients  → backend services
```

## Prerequisites

- Rust 1.75+
- PostgreSQL 15+
- Buf CLI (for proto generation)

## Development

### Setup

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your database credentials
# Then run from the monorepo root:

# Generate proto code
pnpm proto:generate

# Build the gateway
cd rust/gateway
cargo build
```

### Run

```bash
# Development mode
cargo run

# Release mode
cargo build --release
./target/release/gateway
```

The gateway will start on `http://localhost:8080`.

### Test

```bash
# Health check
curl http://localhost:8080/health

# API info
curl http://localhost:8080/api/v2/info
```

## Endpoints

### Health Checks

- `GET /health` — Overall health status
- `GET /health/live` — Liveness probe (returns 200 if running)
- `GET /health/ready` — Readiness probe (returns 200 if ready to serve)

### API Routes

- `GET /api/v2/info` — Service metadata

*More routes will be added in Phase 1, Story 3+*

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `development` | Environment name |
| `PORT` | No | `8080` | HTTP port |
| `DATABASE_URL` | Yes | - | PostgreSQL connection URL |
| `JWT_SECRET` | Yes | - | Secret key for JWT signing |
| `RUST_LOG` | No | `info` | Log level |

## Build for Production

```bash
# Build optimized binary
cargo build --release

# Binary will be at: target/release/gateway
```

## Docker

```bash
# Build image
docker build -f rust/gateway/Dockerfile -t autoniix/gateway:latest .

# Run container
docker run -p 8080:8080 \
  -e DATABASE_URL="postgresql://..." \
  -e JWT_SECRET="your-secret" \
  autoniix/gateway:latest
```

## Project Structure

```
rust/gateway/
├── src/
│   ├── main.rs           # Entry point
│   ├── config.rs         # Environment config
│   ├── error.rs          # Error types & handlers
│   ├── health.rs         # Health check routes
│   ├── observability.rs  # Tracing setup
│   └── routes/
│       └── mod.rs        # API routes
├── Cargo.toml            # Dependencies
├── build.rs              # Proto code generation
├── Dockerfile            # Container image
└── README.md             # This file
```

## Next Steps (Phase 1)

- **P1.3**: Add Auth service implementation (SignIn, SignUp, JWT)
- **P1.4**: Add dual-protocol gateway (REST + Connect-RPC)
- **P1.5**: Wire up PostgreSQL connection pool
- **P1.6**: Add rate limiting and middleware

## References

- [Axum Documentation](https://docs.rs/axum)
- [Tonic Documentation](https://docs.rs/tonic)
- [ADR-001: Polyglot Architecture](../../docs/architecture/adr-001-polyglot-architecture.md)
