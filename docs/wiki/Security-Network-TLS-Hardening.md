# Security: Network, TLS & Hardening

## TLS

Traefik 3.1 terminates TLS for every external host. Cert provisioning is
automatic via Let’s Encrypt HTTP-01 challenge using the `letsencrypt_data`
volume.

```yaml
# traefik/traefik.yml (excerpt)
certificatesResolvers:
  letsencrypt:
    acme:
      email: ${ACME_EMAIL}
      storage: /letsencrypt/acme.json
      httpChallenge: { entryPoint: web }
entryPoints:
  web:       { address: ":80",  http: { redirections: { entryPoint: { to: websecure, scheme: https } } } }
  websecure: { address: ":443" }
```

## Secure headers middleware

Defined in `traefik/dynamic.yml`, applied to every router:

- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'self'` (relaxed for dashboard inline scripts)

## Admin basic-auth

Observability and Temporal UI hosts (`prometheus.`, `alerts.`,
`temporal.`) require Traefik basic-auth using `TRAEFIK_BASIC_AUTH` (an
htpasswd-encoded `user:hash` string, dollar signs doubled).

## Production secret guards

Startup event in `dashboard-bff/main.py` validates 6 env vars:
`ADMIN_JWT_SECRET`, `AUTH_JWT_SECRET`, `DB_PASSWORD`, `S3_ACCESS_KEY`,
`S3_SECRET_KEY`, `GRAFANA_ADMIN_PASSWORD`. The BFF refuses to start in
production if any equals an insecure default. Generate replacements with
`openssl rand -hex 32`.

## SBOM + vulnerability scan

GitHub Actions job `dependency-scan` runs on every push:

- `pip-audit` against `requirements.txt`
- `cyclonedx-py` produces an SBOM
- Artifacts retained 90 days for compliance audits

## CORS

Dashboard-bff CORS middleware is allowlist-only: `${DASH_DOMAIN}` and
`http://localhost:3000` in dev. Wildcards are explicitly rejected.

## Network ports

With TLS profile, only 22 / 80 / 443 are exposed externally. All
internal traffic stays on the `autoniix-net` Docker bridge.

## Related pages

- [[Operations-VPS-Bootstrap]] · [[Architecture-Network-And-Gateway]] ·
  [[Security-Authn-Authz]] · [[CI-CD]]
