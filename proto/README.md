# Proto Contracts

This directory contains all Protocol Buffer (protobuf) definitions for the Autoniix platform. These `.proto` files serve as the **single source of truth** for all API contracts across Rust, Go, Python, and TypeScript services.

## Directory Structure

```
proto/
├── buf.yaml              # Buf configuration (linting, breaking change detection)
├── buf.gen.yaml          # Code generation config for all languages
├── autoniix/
│   ├── common/v1/        # Shared types (Principal, Pagination, Errors, etc.)
│   ├── gateway/v1/       # API Gateway contracts (Auth, Jobs, etc.)
│   ├── research/v1/      # Research service (topics, similarity, saturation)
│   ├── brain/v1/         # Brain/decision engine service
│   ├── script/v1/        # Script generation service
│   ├── voice/v1/         # Voice synthesis service
│   ├── analytics/v1/     # Analytics and metrics service
│   └── streaming/v1/     # Event streaming (SSE/WebSocket replacement)
└── README.md             # This file
```

## Prerequisites

Install Buf CLI:

```bash
# macOS
brew install bufbuild/buf/buf

# Linux
curl -sSL "https://github.com/bufbuild/buf/releases/latest/download/buf-$(uname -s)-$(uname -m)" -o /usr/local/bin/buf
chmod +x /usr/local/bin/buf

# Verify installation
buf --version
```

## Usage

### Lint Proto Files

```bash
pnpm proto:lint
# or
cd proto && buf lint
```

### Format Proto Files

```bash
pnpm proto:format
# or
cd proto && buf format -w
```

### Generate Code for All Languages

```bash
pnpm proto:generate
# or
cd proto && buf generate
```

This generates:
- **Rust**: `gen/rust/` (Tonic + Prost)
- **Go**: `gen/go/` (protoc-gen-go + protoc-gen-go-grpc)
- **Python**: `gen/python/` (protoc-gen-python + protoc-gen-grpc-python)
- **TypeScript**: `dashboard/src/generated/` (Connect-Web for browser)

### Check for Breaking Changes (in CI)

```bash
pnpm proto:breaking
# or
cd proto && buf breaking --against '.git#branch=main'
```

This ensures backward compatibility. A PR will be blocked if it introduces breaking changes to the public API surface.

## Adding a New Service

1. Create a new directory under `proto/autoniix/<service-name>/v1/`
2. Add `<service-name>.proto` with service definition
3. Run `pnpm proto:lint` to validate
4. Run `pnpm proto:generate` to generate client code
5. Commit both `.proto` files and generated code

Example:

```proto
syntax = "proto3";

package autoniix.myservice.v1;

import "autoniix/common/v1/common.proto";

service MyService {
  rpc DoSomething(DoSomethingRequest) returns (DoSomethingResponse);
}

message DoSomethingRequest {
  string input = 1;
}

message DoSomethingResponse {
  string result = 1;
}
```

## Versioning Strategy

- **v1**: Initial stable version
- **v2**: Breaking changes require a new version (e.g., `autoniix.gateway.v2`)
- Old versions coexist during migration
- Deprecated fields use `[deprecated = true]` annotation

## Guidelines

1. **All fields must have comments** — Buf lint enforces this
2. **Use semantic field names** — avoid abbreviations
3. **Never reuse field numbers** — once assigned, field numbers are permanent
4. **Always use `repeated` for lists** — never use a separate wrapper message
5. **Use `oneof` for polymorphic types** — not multiple optional fields
6. **Enums must have `_UNSPECIFIED` as value 0** — Buf lint enforces this
7. **Services must end with `Service` suffix** — enforced by lint
8. **RPC methods use Request/Response suffix** — enforced by lint

## Migration from REST

During the migration, the Rust gateway exposes **both** protocols:

```
/api/v2/*    → REST (JSON) — old clients, gradual deprecation
/rpc/*       → Connect-RPC (gRPC-Web) — new clients
```

Both routes call the same internal gRPC handlers, so no duplication.

## CI Integration

The `.github/workflows/proto-validate.yml` workflow runs on every PR:

1. ✅ Lint all `.proto` files
2. ✅ Check for breaking changes (blocks PR if found)
3. ✅ Test code generation for all 4 languages
4. ✅ Verify generated files are not empty

## Troubleshooting

### `buf generate` fails with "plugin not found"

Ensure you have network access. Buf downloads remote plugins on first use.

### Breaking change detected but I need to make it

1. Bump the version: `autoniix.gateway.v1` → `autoniix.gateway.v2`
2. Keep v1 running alongside v2 during migration
3. Deprecate v1 after all clients migrate

### Generated code not updating

```bash
# Clean and regenerate
rm -rf gen dashboard/src/generated
pnpm proto:generate
```

## References

- [Buf Documentation](https://buf.build/docs)
- [Protocol Buffers Style Guide](https://protobuf.dev/programming-guides/style/)
- [Connect-RPC](https://connectrpc.com/)
- [ADR-001: Polyglot Architecture](../docs/architecture/adr-001-polyglot-architecture.md)
