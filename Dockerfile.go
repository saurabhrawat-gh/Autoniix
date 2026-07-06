# Multi-stage build for any Go binary in this workspace.
#
# Usage (temporal workers):
#   docker build --build-arg BINARY_PATH=./worker/production -t go-worker-production ./go
#   docker build --build-arg BINARY_PATH=./worker/scheduler  -t go-worker-scheduler  ./go
#
# Usage (microservices):
#   docker build --build-arg BINARY_PATH=./notification-dispatcher/cmd/dispatcher \
#                -t notification-dispatcher ./go
#
# Legacy WORKER arg is still honored for existing docker-compose entries.

FROM golang:1.22-alpine AS builder
ARG BINARY_PATH=""
ARG WORKER="production"
WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY . .
# If BINARY_PATH is unset, fall back to legacy ./worker/${WORKER}/ layout.
RUN if [ -n "$BINARY_PATH" ]; then \
      CGO_ENABLED=0 GOOS=linux go build -trimpath -o /app "$BINARY_PATH"; \
    else \
      CGO_ENABLED=0 GOOS=linux go build -trimpath -o /app ./worker/${WORKER}/; \
    fi

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata
COPY --from=builder /app /app
ENTRYPOINT ["/app"]
