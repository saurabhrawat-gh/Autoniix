# Multi-stage build for Go Temporal workers.
# Build arg WORKER selects which worker binary to compile.
# Usage:
#   docker build --build-arg WORKER=production -t go-worker-production ./go
#   docker build --build-arg WORKER=scheduler  -t go-worker-scheduler  ./go

FROM golang:1.22-alpine AS builder
ARG WORKER=production
WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -o /worker ./worker/${WORKER}/

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata
COPY --from=builder /worker /worker
ENTRYPOINT ["/worker"]
