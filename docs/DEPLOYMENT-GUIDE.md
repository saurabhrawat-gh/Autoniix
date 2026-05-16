# Autoniix — Step-by-Step Deployment Guide

End-to-end runbook with your specific values pre-filled. Follow top to bottom.

| Resource | Value |
|---|---|
| VPS | Hostinger KVM 8 — `srv1666017.hstgr.cloud` |
| VPS IP | `187.127.155.126` |
| OS | Ubuntu 22.04 LTS |
| Domain | `autoniix.com` |
| Repo | `github.com/saurabhrawat-gh/yt-automation-n8n` |

---

## Status overview

| Step | Status | Action |
|---|---|---|
| 0  | ✅ DONE | DNS configured (apex + 6 subdomains via Hostinger MCP) |
| 1  | ⬜ YOU  | Generate SSH keypair on your laptop |
| 2  | ⬜ YOU  | Run VPS bootstrap (root SSH, one shot) |
| 3  | ⬜ YOU  | Create Slack webhook |
| 4  | ⬜ YOU  | Create Sentry project (optional, free) |
| 5  | ⬜ YOU  | Add 5 GitHub repository secrets |
| 6  | ⬜ YOU  | Clone repo on VPS, fill `.env`, first deploy |
| 7  | ⬜ YOU  | Verify all 6 URLs and Slack alerts |

---

## Step 0 — DNS (already done)

Configured automatically. All A-records point to `187.127.155.126`:

| Subdomain | Verified? |
|---|---|
| `autoniix.com` (apex) | ✅ |
| `dash.autoniix.com` | ✅ |
| `api.autoniix.com` | ✅ |
| `grafana.autoniix.com` | ✅ |
| `prometheus.autoniix.com` | ✅ |
| `alerts.autoniix.com` | ✅ |
| `temporal.autoniix.com` | ✅ |

Verify propagation from your laptop (5–30 min):
```bash
dig +short dash.autoniix.com
# expected: 187.127.155.126
```

---

## Step 1 — Generate SSH keypair (on your laptop)

Skip if you already have `~/.ssh/id_ed25519`.

```bash
ssh-keygen -t ed25519 -C "saurabh-autoniix" -f ~/.ssh/id_ed25519_autoniix
# Press Enter for empty passphrase or set one (recommended)

# Print the PUBLIC key — you'll paste this into the bootstrap command
cat ~/.ssh/id_ed25519_autoniix.pub
```

**Copy the entire `ssh-ed25519 AAAA...` line** — you need it in Step 2 and Step 5.

---

## Step 2 — Bootstrap the VPS (one shot, ~3 min)

SSH in **as root** for this single step (after this, root login is disabled):

```bash
ssh root@187.127.155.126
# Use the root password from Hostinger hPanel → VPS → Settings
```

Once on the VPS, run:

```bash
export DEPLOY_SSH_PUBKEY='ssh-ed25519 AAAA... saurabh-autoniix'   # paste from Step 1
export SSH_PORT=2222
curl -fsSL https://raw.githubusercontent.com/saurabhrawat-gh/yt-automation-n8n/main/scripts/vps_bootstrap.sh -o /tmp/bootstrap.sh
bash /tmp/bootstrap.sh
```

What it does (idempotent):
- Creates `autoniix` user with sudo + your SSH key
- Disables root login + password auth, moves SSH to port **2222**
- UFW firewall: only `2222`, `80`, `443` open
- fail2ban (sshd jail)
- Docker Engine + Compose plugin
- 4 GB swap file
- Docker JSON log rotation (20 MB × 5 files per container)
- Creates `/mnt/backups` owned by `autoniix`

Exit and reconnect as the deploy user:
```bash
exit
ssh -p 2222 -i ~/.ssh/id_ed25519_autoniix autoniix@187.127.155.126
# You should land in /home/autoniix
docker --version   # verify
```

> If port 2222 is blocked by your local firewall, set `SSH_PORT=22` before running bootstrap.

---

## Step 3 — Slack webhook

1. Open <https://api.slack.com/apps> → **Create New App** → **From scratch**
2. Name: `Autoniix Alerts`, pick your workspace
3. **Incoming Webhooks** → toggle **On** → **Add New Webhook to Workspace**
4. Pick a default channel (e.g. `#yt-alerts`); also create `#yt-alerts-critical`
5. Copy the webhook URL: `https://hooks.slack.com/services/T.../B.../...`

You'll need this in Step 5 and Step 6.

---

## Step 4 — Sentry project (optional, recommended)

1. <https://sentry.io/signup/> → free account
2. **Create Project** → Platform: **Python** → Project name: `autoniix-backend`
3. Copy the DSN: `https://abc123@o12345.ingest.sentry.io/789`

You'll paste it into `.env` in Step 6.

> Skip this step if you don't want error tracking — `SENTRY_DSN=` (empty) makes the SDK a no-op.

---

## Step 5 — GitHub repository secrets

Go to <https://github.com/saurabhrawat-gh/yt-automation-n8n/settings/secrets/actions>

Click **New repository secret** for each:

| Name | Value |
|---|---|
| `VPS_HOST` | `187.127.155.126` |
| `VPS_USER` | `autoniix` |
| `VPS_SSH_PORT` | `2222` |
| `VPS_SSH_KEY` | Contents of `~/.ssh/id_ed25519_autoniix` (the **private** key — `cat ~/.ssh/id_ed25519_autoniix`, copy the whole `-----BEGIN ... -----END-----` block) |
| `SLACK_WEBHOOK_URL` | Webhook URL from Step 3 |

After saving, every push to `main` will auto-deploy + smoke-test + Slack-notify.

---

## Step 6 — Clone repo on VPS and first deploy

SSH in as `autoniix` (Step 2 confirmed it works):

```bash
ssh -p 2222 -i ~/.ssh/id_ed25519_autoniix autoniix@187.127.155.126
```

### 6a. Clone repo

```bash
git clone https://github.com/saurabhrawat-gh/yt-automation-n8n.git ~/autoniix
cd ~/autoniix
```

### 6b. Generate secrets

```bash
echo "AUTH_JWT_SECRET=$(openssl rand -base64 48)"
echo "ADMIN_JWT_SECRET=$(openssl rand -base64 48)"
echo "DB_PASSWORD=$(openssl rand -base64 32)"
echo "TEMPORAL_DB_PASSWORD=$(openssl rand -base64 32)"
echo "S3_ACCESS_KEY=$(openssl rand -hex 12)"
echo "S3_SECRET_KEY=$(openssl rand -base64 32)"
echo "GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 24)"
echo "SECRETS_ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' 2>/dev/null || pip install --quiet cryptography && python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

# Basic-auth hash for grafana/prometheus/alerts/temporal admin pages
sudo apt install -y apache2-utils
htpasswd -nbB admin 'PickAStrongPassword!'
# → e.g. admin:$2y$05$abc...   ← copy this whole line as TRAEFIK_BASIC_AUTH
```

Save all the printed values somewhere temporarily (a password manager).

### 6c. Create `.env`

```bash
cp .env.production.example .env
nano .env
```

Replace every `CHANGE_ME` value. Mandatory:

```ini
# Domain (already correct in template)
DOMAIN=autoniix.com
DASH_DOMAIN=dash.autoniix.com
API_DOMAIN=api.autoniix.com
GRAFANA_DOMAIN=grafana.autoniix.com
PROMETHEUS_DOMAIN=prometheus.autoniix.com
ALERTS_DOMAIN=alerts.autoniix.com
TEMPORAL_DOMAIN=temporal.autoniix.com
ACME_EMAIL=admin@autoniix.com
ALLOWED_ORIGINS=https://dash.autoniix.com

# Paste from Step 6b
TRAEFIK_BASIC_AUTH=admin:$2y$05$...
DB_PASSWORD=...
TEMPORAL_DB_PASSWORD=...
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
ADMIN_JWT_SECRET=...
AUTH_JWT_SECRET=...
GRAFANA_ADMIN_PASSWORD=...
SECRETS_ENCRYPTION_KEY=...

# Slack (from Step 3)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Sentry (from Step 4 — leave empty to disable)
SENTRY_DSN=

# Your real LLM / TTS / YouTube keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_AI_API_KEY=...
FISH_AUDIO_API_KEY=...
PIXABAY_API_KEY=...
PEXELS_API_KEY=...
YOUTUBE_API_KEY=...
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REFRESH_TOKEN=...
```

> **Important:** `TRAEFIK_BASIC_AUTH` — paste the **raw** htpasswd output. Do NOT double the `$` signs; docker compose handles escaping.

Save (`Ctrl+O`, `Enter`, `Ctrl+X`).

### 6d. Pre-flight check

```bash
make deploy-check
```

This validates:
- All `CHANGE_ME` placeholders are gone
- DB passwords are not defaults
- Required env vars are set
- Migrations are clean
- Unit tests pass

Fix anything red before continuing.

### 6e. First deploy

```bash
docker compose --profile tls up -d --build
# ~5-10 min on first build (Docker layer cache makes subsequent deploys 1-2 min)

# Watch progress
docker compose ps

# Wait for all services to be healthy:
make health
```

### 6f. One-time post-deploy steps

```bash
# Register the 5 Temporal schedules (gate-cal, niche-pulse, retention,
# model-maint, daily-scheduler)
make schedule-register

# Flip auth from legacy to v2 (JWT)
make auth-enable

# End-to-end smoke test
make smoke
```

### 6g. Daily backups via cron

```bash
crontab -e
# Add this line (daily 03:30 UTC):
30 3 * * * /home/autoniix/autoniix/scripts/backup.sh >> /var/log/autoniix-backup.log 2>&1
sudo touch /var/log/autoniix-backup.log
sudo chown autoniix:autoniix /var/log/autoniix-backup.log
```

---

## Step 7 — Verify everything

From your laptop browser (in this order):

| URL | Expected | Login |
|---|---|---|
| <https://dash.autoniix.com> | Dashboard login page, valid LE cert | Set up via dashboard or `make auth-enable` |
| <https://api.autoniix.com/health> | `{"status":"ok","v2_router_loaded":true,...}` | none |
| <https://grafana.autoniix.com> | Grafana login | `admin` / `GRAFANA_ADMIN_PASSWORD` |
| <https://prometheus.autoniix.com/targets> | Basic-auth → 14 targets all UP | TRAEFIK_BASIC_AUTH credentials |
| <https://alerts.autoniix.com> | Basic-auth → Alertmanager UI | same |
| <https://temporal.autoniix.com> | Basic-auth → 5 schedules listed | same |

### Test Slack alerting

Trigger a critical alert by stopping postgres briefly:

```bash
docker compose stop postgres-app
# Wait ~2 min — Slack #yt-alerts-critical should fire `PostgresDown`
docker compose start postgres-app
# A "RESOLVED" message follows in 1-2 min
```

### Test CI/CD

From your laptop:

```bash
git checkout -b ci-test
echo "# CI test $(date)" >> README.md
git add README.md && git commit -m "test: verify CI/CD pipeline"
git push origin ci-test
# Create a PR, see GitHub Actions run lint+tests
# Merge → main → watch GitHub Actions deploy → Slack notify "Deploy OK"
```

---

## Step 8 — Day 2 operations

### Manual deploy (if CI is down)

```bash
ssh -p 2222 -i ~/.ssh/id_ed25519_autoniix autoniix@187.127.155.126
cd ~/autoniix
git pull origin main
docker compose --profile tls up -d --build --remove-orphans
make smoke
```

### View logs

```bash
docker compose logs -f --tail=100 dashboard-bff
docker compose logs -f --tail=100 worker-production
```

Or via Grafana → Explore → pick `Loki` datasource → query by service.

### Restart one service after code change (without full deploy)

```bash
docker compose up -d --build research
```

### Restore from backup

```bash
ls /mnt/backups/                      # find timestamp
bash scripts/restore.sh /mnt/backups/<TIMESTAMP>
```

---

## Troubleshooting cheatsheet

| Symptom | Likely cause | Fix |
|---|---|---|
| `make deploy-check` complains about CHANGE_ME | placeholder still in `.env` | grep `CHANGE_ME .env` and replace |
| TLS cert not issuing | DNS not propagated / port 80 blocked | `dig dash.autoniix.com`; `sudo ufw status`; `docker compose logs traefik` |
| `502 Bad Gateway` on dashboard | dashboard-bff unhealthy | `docker compose ps`, `docker compose logs dashboard-bff` |
| Grafana asks for login twice | Both basic-auth AND Grafana auth | We disabled basic-auth on Grafana — re-pull latest if it persists |
| Out of disk on `/` | Docker images / logs | `docker system prune -af`; check `/var/lib/docker/containers/*/json.log` |
| Backups not running | crontab missing or path wrong | `crontab -l`; verify path matches |
| Slack alert never fires | webhook wrong / Alertmanager not reloaded | `docker compose restart alertmanager`; check `/alerts.autoniix.com` UI |

---

## Cost summary

| Item | Monthly |
|---|---|
| Hostinger KVM 8 | ~$25 (already paid) |
| Domain `autoniix.com` | ~$1 amortized |
| Slack | $0 (free tier) |
| Sentry | $0 (free 5k errors/mo) |
| Grafana / Prom / Loki / Traefik / Alertmanager / fail2ban / UFW | $0 (self-hosted) |
| Let's Encrypt TLS | $0 |
| GitHub Actions | $0 (private repo gets 2k min free) |
| **Infra recurring** | **~$26/mo** |
| OpenAI / Claude / Gemini / Fish Audio | depends on volume |

---

_Last updated: May 16, 2026 — VPS IP `187.127.155.126`, DNS automated via Hostinger MCP._
