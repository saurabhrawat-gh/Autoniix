# Architecture: Network & Gateway

## Purpose

All services share a single Docker bridge network (`autoniix-net`) and
are optionally fronted by Traefik for TLS, host-based routing and admin
basic-auth on observability UIs.

## Source files

- `docker-compose.yml:3-6` — network definition
- `docker-compose.yml:758-790` — Traefik service (profile `tls`)
- `traefik/traefik.yml`, `traefik/dynamic.yml` — static + dynamic config

## Network

```yaml
networks:
  autoniix-net:
    driver: bridge
```

Every service joins `[autoniix-net]`. Inter-service DNS uses the compose
service name (e.g. `http://research:8001`, `http://redis:6379`,
`http://minio:9000`).

## Published host ports (no TLS profile)

| Service | Host port | Container port |
|---|---|---|
| dashboard-ui | 3000 | 3000 |
| grafana | 3001 | 3000 |
| remotion-api | 4000 | 4000 |
| remotion-mcp | 4100 | 4100 |
| postgres-app | 5433 | 5432 |
| postgres-temporal | 5434 | 5432 |
| redis | 6380 | 6379 |
| temporal-frontend | 7233 | 7233 |
| temporal-ui | 8080 | 8080 |
| research..editor | 8001–8013 | same |
| dashboard-bff | 8020 | 8020 |
| infisical (profile `secrets`) | 8222 | 8080 |
| minio (S3) | 9000 | 9000 |
| minio (console) | 9001 | 9001 |
| prometheus | 9090 | 9090 |
| alertmanager | 9093 | 9093 |

## Traefik (profile `tls`)

Enabled with `make tls-up` (or `docker compose --profile tls up -d`). Reads
config from `traefik/traefik.yml` and uses Docker provider for
auto-discovery of `traefik.*` labels.

Host-based routers (configured via env vars in `.env.production.example`):

| Host | Service |
|---|---|
| `${DASH_DOMAIN}` | dashboard-ui |
| `${API_DOMAIN}` | dashboard-bff |
| `${GRAFANA_DOMAIN}` | grafana |
| `${PROMETHEUS_DOMAIN}` | prometheus (admin-auth) |
| `${ALERTS_DOMAIN}` | alertmanager (admin-auth) |
| `${TEMPORAL_DOMAIN}` | temporal-ui (admin-auth) |

### TLS

- `letsencrypt` cert resolver (HTTP-01) provisions certs to
  `letsencrypt_data` volume.
- `ACME_EMAIL` env var required.
- All routers use `entrypoints=websecure` (port 443) + `tls.certresolver=letsencrypt`.
- A `web` entrypoint on port 80 only serves the ACME challenge and redirects
  to https.

### Admin basic-auth middleware

Defined on the Traefik service itself via labels (see `docker-compose.yml:773-780`):

```yaml
- "traefik.http.middlewares.admin-auth.basicauth.users=${TRAEFIK_BASIC_AUTH}"
- "traefik.http.middlewares.admin-auth.basicauth.realm=Autoniix Admin"
```

`TRAEFIK_BASIC_AUTH` is an htpasswd-encoded `user:hash` with dollar signs
doubled (`$$`). Applied to Prometheus, Alertmanager and Temporal UI routers.
Grafana is exempt to avoid double-prompt because it has its own login.

### Secure headers

A `secureHeaders` middleware defined in `traefik/dynamic.yml` adds HSTS,
frame-deny, content-type sniffing protection, etc., applied to every router.

## CORS

The dashboard-bff applies an allowlist CORS middleware (see
`src/services/dashboard/main.py`) restricted to `${DASH_DOMAIN}` plus
`http://localhost:3000` in dev.

## Related pages

- [[Architecture-Container-Topology]]
- [[Operations-Runbook]]
- [[Security-Network-TLS-Hardening]]
