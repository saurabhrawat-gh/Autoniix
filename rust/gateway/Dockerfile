# syntax=docker/dockerfile:1
# Pinned via versions.env RUST_IMAGE=rust:1.83.0-bookworm DEBIAN_IMAGE=debian:bookworm-slim
ARG RUST_IMAGE=rust:1.83.0-bookworm
ARG DEBIAN_IMAGE=debian:bookworm-slim

FROM ${RUST_IMAGE} AS builder

# protoc is required by the gateway build script (tonic-build) to compile .proto files
RUN apt-get update && apt-get install -y protobuf-compiler && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY rust/Cargo.toml rust/Cargo.lock ./
COPY rust-toolchain.toml ./
COPY rust/gateway gateway/
COPY rust/harness harness/
COPY proto ../proto/

WORKDIR /build/gateway

RUN cargo build --release

FROM ${DEBIAN_IMAGE}

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
