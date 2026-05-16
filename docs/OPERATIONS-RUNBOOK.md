# Operations Runbook

Single-page reference for day-to-day and incident tasks.
Keep this accurate — it is the source of truth, not chat history.

---

## Quick health check

```bash
make health              # checks every service endpoint
curl http://localhost:8020/health | jq   # BFF component breakdown
make alerts-status       # show firing Alertmanager alerts
```

---

## Starting and stopping

| Intent | Command |
|--------|---------|
| Start full stack | `make up` |
| Stop everything | `make down` |
| Restart app code after editing `src/` | `make restart-app` |
| Restart only BFF | `make restart-bff` |
| Start infra only (local dev) | `make infra` |
| Run BFF on host (local dev) | `make bff` |
| Run UI on host (local dev) | `make ui` |

---

## Auth management

### Enable v2 auth (email + MFA)
```bash
make auth-enable
# First user to register at /register becomes Owner.
```

### Disable v2 auth (fall back to legacy single-password)
```bash
docker compose exec -T postgres-app psql -U app -d autoniix -c \
  "UPDATE feature_flags SET enabled = FALSE WHERE key = 'auth.v2.enabled'; \
   UPDATE feature_flags SET enabled = TRUE  WHERE key = 'auth.legacy.enabled';"
```

---

## TLS (Traefik + Let's Encrypt)

Prerequisites: `DOMAIN`, `DASH_DOMAIN`, `API_DOMAIN`, etc., and `ACME_EMAIL`
set in `.env`, ports 80/443 open publicly, DNS A-records pointing to this VPS.

```bash
docker compose --profile tls up -d   # boots Traefik; certs auto-issue (~30s)
docker compose --profile tls down    # stops Traefik (certs preserved in letsencrypt_data volume)
```

Inspect routes:
```bash
docker compose logs --tail=50 traefik
```

---

## Backup & Restore

### Take a manual backup
```bash
bash scripts/backup.sh
# Writes to ${BACKUP_LOCAL_DIR:-/mnt/backups}/<stamp>/
# Optional offsite via BACKUP_S3_* env vars (Hostinger / B2 / R2 / S3).
```

### Restore drill (recommended monthly)
1. `bash scripts/backup.sh` → note the stamp
2. On a test host: `bash scripts/restore.sh /mnt/backups/<stamp>`
3. `make smoke` to verify
4. Record result here

**Last drill:** _not yet performed_

---

## Secrets rotation

All secrets are in `.env`.

| Secret | How to rotate |
|--------|---------------|
| `AUTH_JWT_SECRET` | `openssl rand -base64 48` → update `.env` → `make restart-bff`. Existing v2 sessions need re-login. |
| `DB_PASSWORD` | Update in `.env` → `docker compose up -d postgres-app` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Update in `.env` → MinIO console → `make restart-app` |
| `ADMIN_JWT_SECRET` | Same flow as `AUTH_JWT_SECRET`. |
| `GRAFANA_ADMIN_PASSWORD` | Update in `.env` → `docker compose up -d grafana` |
| `TRAEFIK_BASIC_AUTH` | `htpasswd -nbB user '<pw>'` → paste raw to `.env` → `docker compose up -d traefik` |

**Production safety gate:** the BFF startup event `_check_production_secrets`
refuses to boot if any of these are still default when `ENVIRONMENT_MODE=production`.

---

## Alerting

### Check firing alerts
```bash
make alerts-status
# or open https://alerts.autoniix.com (basic-auth)
```

### Add a Slack webhook
Set `SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...` in `.env`, then:
```bash
docker compose up -d alertmanager
```
Alerts route to `#yt-alerts` (warnings/info) and `#yt-alerts-critical` (critical).

---

## Production URLs (split-host)

| Service | URL | Auth |
|---------|-----|------|
| Dashboard UI | https://dash.autoniix.com | Dashboard login |
| BFF API | https://api.autoniix.com | none (CORS-restricted to dash) |
| Grafana | https://grafana.autoniix.com | Grafana login |
| Prometheus | https://prometheus.autoniix.com | basic-auth |
| Alertmanager | https://alerts.autoniix.com | basic-auth |
| Temporal UI | https://temporal.autoniix.com | basic-auth |

---

## VPS Provisioning (first-time)

One-shot script:

```bash
# As root on the fresh Ubuntu 22.04+ VPS
export DEPLOY_SSH_PUBKEY='ssh-ed25519 AAAA... you@laptop'
export SSH_PORT=2222
curl -fsSL https://raw.githubusercontent.com/saurabhrawat-gh/Autoniix/main/scripts/vps_bootstrap.sh -o /tmp/bs.sh
bash /tmp/bs.sh
```

Result:
- `autoniix` user with sudo + your SSH key
- SSH on port 2222, root login + password auth disabled
- UFW: 2222/80/443 only
- fail2ban (sshd jail)
- Docker + Compose plugin
- 4 GB swap, log rotation, `/mnt/backups`

Reconnect: `ssh -p 2222 autoniix@<vps-ip>`

### Required GitHub secrets

| Secret | Value |
|---|---|
| `VPS_HOST` | VPS public IPv4 |
| `VPS_USER` | `autoniix` |
| `VPS_SSH_PORT` | `2222` |
| `VPS_SSH_KEY` | Private ed25519 key matching the pubkey |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook |

### Production .env preparation

```bash
cp .env.production.example .env
openssl rand -base64 48                                     # JWT / DB passwords
htpasswd -nbB admin 'StrongPassword!'                       # TRAEFIK_BASIC_AUTH (paste raw)
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
$EDITOR .env
```

### First deploy

```bash
make deploy-check
docker compose --profile tls up -d --build
make health
make schedule-register
make auth-enable
make smoke
```

Verify each URL above, then trigger a test alert by stopping postgres briefly.

### Daily backups

```bash
crontab -e
# Daily 03:30 UTC:
30 3 * * * /home/autoniix/autoniix/scripts/backup.sh >> /var/log/autoniix-backup.log 2>&1
sudo touch /var/log/autoniix-backup.log
sudo chown autoniix:autoniix /var/log/autoniix-backup.log
```

### CI/CD

`.github/workflows/ci.yml` `deploy` job runs on every push to `main`
(excluding commits with `[skip deploy]`). The job:
1. SSHes to VPS, `git reset --hard origin/main`, `docker compose --profile tls up -d --build --remove-orphans`
2. Polls `/health`, runs `make smoke`
3. Posts deploy success / failure to Slack

---

## Database operations

```bash
docker compose exec postgres-app psql -U app -d autoniix
make migrate
make backfill   # idempotent
```

---

## Logs

| Need | Command |
|------|---------|
| Tail | `docker compose logs -f dashboard-bff worker-production` |
| Loki (Grafana) | <https://grafana.autoniix.com> → Explore → Loki |

Retention: Loki 30d, Prometheus 15d.

---

## Emergency procedures

### Stop all video production
```bash
curl -X POST https://api.autoniix.com/api/system/emergency-stop -H "Authorization: Bearer <token>"
```

### BFF down
1. `docker compose logs --tail=50 dashboard-bff | grep -E "error|FATAL"`
2. `make verify-bff`
3. `make restart-bff`
4. If persists: `make restart-app`

### Disk space critical
```bash
df -h /
docker system prune -af
ls -1t /mnt/backups/ | tail -n +8 | xargs -I{} rm -rf /mnt/backups/{}
```

### Troubleshooting TLS
- DNS propagation: `dig dash.autoniix.com`
- UFW: `sudo ufw status`
- ACME logs: `docker compose logs traefik | grep -i acme`
- Rate limit: 5 LE failures/hour — wait or use staging directory

---

_Last updated: May 16, 2026 (Phase G)_
