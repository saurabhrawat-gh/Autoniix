# syntax=docker/dockerfile:1

FROM rust:1-bookworm AS builder

# protoc is required by the gateway build script (tonic-build) to compile .proto files
RUN apt-get update && apt-get install -y protobuf-compiler && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY rust/Cargo.toml rust/Cargo.lock ./
COPY rust/gateway gateway/
COPY rust/harness harness/
COPY proto ../proto/

WORKDIR /build/gateway

RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/target/release/gateway /app/gateway

ENV RUST_LOG=info
ENV PORT=8080

EXPOSE 8080

CMD ["/app/gateway"]
