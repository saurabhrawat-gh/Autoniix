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

## Environment switching

```bash
make use-test   # activate .env.test (mock providers, ~$0/video)
make use-prod   # activate .env.prod (paid APIs, requires confirmation)
make env-status # show active environment
```

> **Before switching to production:** verify all CHANGE_ME values in `.env.prod` are
> replaced with real secrets.

---

## Auth management

### Enable v2 auth (email + MFA)
```bash
make auth-enable
# First user to register at http://localhost:3000/register becomes Owner.
```

### Disable v2 auth (fall back to legacy single-password)
```bash
docker compose exec -T postgres-app psql -U app -d yt_automation -c \
  "UPDATE feature_flags SET enabled = FALSE WHERE key = 'auth.v2.enabled'; \
   UPDATE feature_flags SET enabled = TRUE  WHERE key = 'auth.legacy.enabled';"
```

---

## TLS (Traefik + Let's Encrypt)

Prerequisites: `DOMAIN` and `ACME_EMAIL` set in `.env`, ports 80/443 open publicly.

```bash
make tls-up     # start Traefik; certs provision automatically (~30s)
make tls-down   # stop Traefik (certs preserved in letsencrypt_data volume)
```

Traefik dashboard is disabled. Inspect routes via:
```bash
docker compose logs --tail=50 traefik
```

---

## Backup & Restore

### Take a manual backup
```bash
make backup
# Writes to ./backups/<stamp>/  and optionally pushes to R2 (BACKUP_R2_* in .env)
```

### List available snapshots
```bash
ls -1t backups/
```

### Restore from latest
```bash
make restore
```

### Restore from a specific snapshot
```bash
make restore STAMP=20260510T033000Z
```

> **What is backed up:** Postgres `yt_automation` DB (compressed custom format) +
> MinIO `prod/` and `public/` prefixes. Test data (`test/` prefix) is excluded.

### Restore drill (recommended monthly)
1. `make backup` → note the stamp
2. On a test host or in a fresh docker volume: `make restore STAMP=<above>`
3. `make smoke` to verify data integrity
4. Record result in this file under the drill log below

**Last drill:** _not yet performed_

---

## Secrets rotation

All secrets are in `.env` (or `.env.prod` for production).

| Secret | How to rotate |
|--------|---------------|
| `AUTH_JWT_SECRET` | `openssl rand -base64 48` → update `.env` → `make restart-bff`. Existing v2 sessions will need to re-login. |
| `DB_PASSWORD` | Update in `.env` + `docker-compose.yml` postgres env → `docker compose up -d postgres-app` (new sessions use new pw). |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Update in `.env` → MinIO console → `make restart-app` |
| `ADMIN_JWT_SECRET` | Same flow as `AUTH_JWT_SECRET`. |
| `GRAFANA_ADMIN_PASSWORD` | Update in `.env` → `docker compose up -d grafana` |

**Production safety gate:** the BFF startup event `_check_production_secrets` will refuse
to boot if any of these are still at their default values when `ENVIRONMENT_MODE=production`.

---

## Alerting

### Check firing alerts
```bash
make alerts-status
# or: open http://localhost:9093 in browser (Alertmanager UI)
```

### Silence a noisy alert (e.g., during planned maintenance)
```bash
# Create silence via Alertmanager API (2-hour window)
curl -X POST http://localhost:9093/api/v2/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [{"name": "alertname", "value": "ServiceDown", "isRegex": false}],
    "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "endsAt": "'$(date -u -d '+2 hours' +%Y-%m-%dT%H:%M:%SZ)'",
    "comment": "Planned maintenance",
    "createdBy": "ops"
  }'
```

### Add a Slack webhook
Set `SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...` in `.env`, then:
```bash
docker compose up -d alertmanager
```
Alerts route to `#yt-alerts` (warnings/info) and `#yt-alerts-critical` (critical).

---

## Database operations

### Connect to Postgres
```bash
docker compose exec postgres-app psql -U app -d yt_automation
```

### Apply pending migrations
```bash
make migrate
```

### Backfill channel profiles
```bash
make backfill   # idempotent — safe to re-run
```

### Check DB pool / connection count
```sql
SELECT count(*), state FROM pg_stat_activity
WHERE datname = 'yt_automation' GROUP BY state;
```

---

## Logs

| Need | Command |
|------|---------|
| Tail all app logs | `docker compose logs -f dashboard-bff worker-production` |
| Filter by level | `docker compose logs dashboard-bff | grep '"level":"error"'` |
| Loki (Grafana) | Open http://localhost:3001 → Explore → Loki |
| Last 50 BFF lines | `docker compose logs --tail=50 dashboard-bff` |

Log retention: **30 days** (Loki). Prometheus metrics: **15 days**.

---

## Observability URLs

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| BFF API | http://localhost:8020 |
| BFF health | http://localhost:8020/health |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |
| Grafana | http://localhost:3001 (admin / see `GRAFANA_ADMIN_PASSWORD`) |
| Temporal UI | http://localhost:8080 |
| MinIO console | http://localhost:9001 |

---

## Emergency procedures

### Stop all video production immediately
```bash
# Via dashboard: toggle "Emergency Stop" switch
# Via API:
curl -X POST http://localhost:8020/api/system/emergency-stop \
  -H "Authorization: Bearer <token>"
```

### BFF is down / returning 500 errors
1. `docker compose logs --tail=50 dashboard-bff | grep -E "error|Error|FATAL"`
2. If v2 router disabled: `make verify-bff` to see the count
3. `make restart-bff` to force a clean restart
4. If persists: `make restart-app` to rebuild everything

### Temporal worker not processing jobs
1. `docker compose ps worker-production` — verify it's running
2. `docker compose logs --tail=30 worker-production`
3. Check Temporal UI at http://localhost:8080 for stuck workflows
4. `docker compose restart worker-production`

### Disk space critical
```bash
df -h /
docker system prune -f          # remove dangling images/containers
docker volume ls -f dangling=true | xargs docker volume rm  # orphaned volumes
# If still low: trim old backups
ls -1t backups/ | tail -n +4 | xargs -I{} rm -rf backups/{}
```

---

## SSH hardening (run once on server, before opening to public traffic)

```bash
# 1. Create a non-root deploy user
adduser deploy
usermod -aG sudo,docker deploy

# 2. Copy your public key
ssh-copy-id -i ~/.ssh/id_ed25519.pub deploy@<SERVER_IP>

# 3. Disable password auth and root login
sudo sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?Port .*/Port 2222/' /etc/ssh/sshd_config
sudo systemctl reload sshd

# 4. Verify (from a DIFFERENT terminal — do not close the current session)
ssh -p 2222 deploy@<SERVER_IP> echo "OK"
```

> **Critical:** verify connectivity before closing your current SSH session,
> or you will lock yourself out.

---

## UFW firewall (run after SSH hardening)

```bash
# Allow only what's needed
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 2222/tcp    # SSH (matches Port 2222 above)
sudo ufw allow 80/tcp      # HTTP (Traefik → Let's Encrypt)
sudo ufw allow 443/tcp     # HTTPS (Traefik)

# Enable
sudo ufw enable
sudo ufw status verbose
```

Docker bypasses UFW for container-to-container traffic on the Docker network —
that's intentional. Only inbound traffic from the public internet is filtered.

---

## Production deploy checklist (first deploy)

Run in order. Each step has a verification command.

```bash
# 1. Pull latest code
git pull origin main

# 2. Build images
docker compose build

# 3. Run DB schema migrations (idempotent — safe to re-run)
docker compose exec postgres-app psql -U app -d yt_automation \
  -f /docker-entrypoint-initdb.d/init-db.sql

# 4. Seed config + prompts (ON CONFLICT DO UPDATE — safe to re-run)
docker compose exec postgres-app psql -U app -d yt_automation \
  -f /docker-entrypoint-initdb.d/seed-data.sql

# 5. Start all services
make up

# 6. Verify stack health
make health

# 7. Register Temporal workflow schedules (idempotent)
python -m scripts.register_schedules --temporal-host localhost:7233

# 8. Verify schedules registered
#   Open Temporal UI → http://localhost:8080 → Schedules
#   Expect: 5 schedules (gate-calibration, niche-pulse, retention-fetch,
#           model-maintenance, daily-scheduler)

# 9. Enable v2 auth (flip feature flag)
make auth-enable

# 10. Smoke test
make smoke
```

### Post-deploy watch items (first week)

| Metric | What to watch | Alert if |
|--------|--------------|----------|
| Budget | Grafana → Budget panel | `today_spend > 80%` of daily limit |
| QC fail rate | Grafana → QC panel | `yt_qc_failed_total / yt_qc_checked_total > 20%` |
| Disk space | Grafana → Node Exporter panel | `< 20 GB free` |
| Temporal | http://localhost:8080 → Workers | Worker count = 0 for > 5 min |
| BFF health | `curl http://localhost:8020/health` | `v2_router_loaded: false` |

---

_Last updated: May 10, 2026 (Phase F — Production Deploy)_
