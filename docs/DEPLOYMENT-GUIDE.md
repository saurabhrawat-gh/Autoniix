# Autoniix — Deployment Guide

Everything you need to go from zero to a live deployment on Hostinger KVM 8.

---

## Table of Contents

1. [Buy in This Order](#1-buy-in-this-order)
2. [Point DNS to VPS](#2-point-dns-to-vps)
3. [First-Time VPS Setup](#3-first-time-vps-setup)
4. [Clone & Configure the App](#4-clone--configure-the-app)
5. [Start the Stack](#5-start-the-stack)
6. [Enable TLS (HTTPS)](#6-enable-tls-https)
7. [Set Up CI/CD (Auto-Deploy on Git Push)](#7-set-up-cicd-auto-deploy-on-git-push)
8. [Daily Development Workflow](#8-daily-development-workflow)
9. [Useful Commands](#9-useful-commands)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Buy in This Order

> Do this in sequence — domain first so DNS is propagating while you set up the VPS.

| Step | What | Where | Est. Cost |
|------|------|--------|-----------|
| 1 | Buy `autoniix.com` domain | Hostinger → Domains | ~$10–12/yr |
| 2 | Buy KVM 8 VPS | Hostinger → VPS | $25.99/mo |
| 3 | Business email (optional) | Hostinger → Email | ~$1–2/mo |

**VPS purchase options:**
- **Term:** Monthly to start (upgrade to 12/24 months once stable)
- **Location:** India — Mumbai 2 (best latency for you)
- **OS:** Ubuntu 22.04 LTS
- **Daily auto-backup:** Skip — the repo has `scripts/backup.sh` and weekly snapshots are included free

---

## 2. Point DNS to VPS

Once the VPS is provisioned, copy its IP from hPanel → VPS → Overview.

Go to **Hostinger → Domains → autoniix.com → DNS Zone** and add:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | `@` | `<VPS_IP>` | 300 |
| A | `dashboard` | `<VPS_IP>` | 300 |
| A | `api` | `<VPS_IP>` | 300 |
| A | `grafana` | `<VPS_IP>` | 300 |

DNS usually propagates within 5–30 minutes on Hostinger. Verify with:

```bash
ping dashboard.autoniix.com   # should return your VPS IP
```

---

## 3. First-Time VPS Setup

SSH in as root initially:

```bash
ssh root@<VPS_IP>
```

### 3a. System update

```bash
apt update && apt upgrade -y
```

### 3b. Create non-root user

```bash
adduser saurabh
usermod -aG sudo saurabh
```

### 3c. Copy your SSH key (run from YOUR local machine)

```bash
ssh-copy-id saurabh@<VPS_IP>
```

Then verify you can SSH without a password:
```bash
ssh saurabh@<VPS_IP>
```

From now on, **never SSH as root**.

### 3d. Harden SSH (on VPS)

```bash
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
# Set: PasswordAuthentication no
sudo systemctl restart sshd
```

### 3e. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

### 3f. Install Docker + tools

```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker saurabh

# Docker Compose plugin (v2)
sudo apt install docker-compose-plugin -y

# Git + Make
sudo apt install git make -y

# Log out and back in for docker group to take effect
exit
ssh saurabh@<VPS_IP>

# Verify
docker compose version
```

---

## 4. Clone & Configure the App

```bash
# Clone the repo
git clone https://github.com/<your-username>/autoniix.git
cd autoniix

# Create .env from example
cp .env.example .env
nano .env
```

### Minimum required `.env` values

```bash
ENVIRONMENT_MODE=test          # Keep as 'test' while developing

# Database
DB_PASSWORD=<strong-password>

# MinIO (object storage)
S3_ACCESS_KEY=<choose-any>
S3_SECRET_KEY=<choose-strong>

# LLM (at least one)
OPENAI_API_KEY=<your-key>

# Stock footage (free)
PEXELS_API_KEY=<your-key>      # https://www.pexels.com/api/
PIXABAY_API_KEY=<your-key>     # https://pixabay.com/api/docs/

# TTS
FISH_API_KEY=<your-key>        # https://fish.audio

# Auth (generate with: openssl rand -hex 32)
ADMIN_JWT_SECRET=<generate>
AUTH_JWT_SECRET=<generate>
ADMIN_PASSWORD=<choose>
```

> **Tip:** Generate secrets with `openssl rand -hex 32`

---

## 5. Start the Stack

```bash
# Start all containers
docker compose up -d

# Wait ~60 seconds for everything to initialize
sleep 60

# Check all containers are healthy
docker compose ps

# Run database migrations
make migrate

# Seed database (prompts, system config, niche templates)
make seed

# Verify the stack is responding
make health
```

The dashboard is now accessible at `http://<VPS_IP>:3000` (HTTP, before TLS).

---

## 6. Enable TLS (HTTPS)

> Do this only after DNS has propagated (`ping dashboard.autoniix.com` returns your VPS IP).

```bash
# Set your email for Let's Encrypt in traefik config
nano traefik/traefik.yml
# → update: certificatesResolvers.letsencrypt.acme.email = "you@example.com"

nano traefik/dynamic.yml
# → verify domain names match: dashboard.autoniix.com, api.autoniix.com

# Start with TLS profile
make tls-up
```

After ~30 seconds, Let's Encrypt issues the cert automatically. Visit:
- `https://dashboard.autoniix.com` — Admin dashboard
- `https://grafana.autoniix.com` — Observability

---

## 7. Set Up CI/CD (Auto-Deploy on Git Push)

Every push to `main` automatically deploys to the VPS via GitHub Actions. This means you never manually SSH to deploy — just `git push` and the VPS updates itself.

### 7a. Add GitHub Secrets

Go to **GitHub → Your Repo → Settings → Secrets and variables → Actions → New repository secret**:

| Secret Name | Value |
|-------------|-------|
| `VPS_HOST` | `autoniix.com` or your VPS IP |
| `VPS_USER` | `saurabh` (your non-root username) |
| `VPS_SSH_KEY` | Contents of `~/.ssh/id_rsa` (your **private** key) |

To get your private key:
```bash
cat ~/.ssh/id_rsa   # copy the entire output including -----BEGIN/END lines
```

### 7b. The Deploy Pipeline

The CI/CD pipeline in `.github/workflows/ci.yml` runs automatically:

```
push to main
    ↓
Python lint + unit tests
    ↓
Remotion typecheck
    ↓
Security scan (pip-audit)
    ↓
[all pass] → SSH into VPS → git pull → docker compose up --build
```

**The deploy only fires if all tests pass.** A broken push will not reach the VPS.

### 7c. Monitor Deploys

Go to **GitHub → Actions** to see live deploy logs. Each deploy takes ~2–4 minutes (Docker layer cache makes rebuilds fast after the first one).

---

## 8. Daily Development Workflow

### Option A — Remote SSH in Cursor (Recommended)

Edit code directly on the VPS from your IDE. Nothing runs locally.

1. Open Cursor → `Ctrl+Shift+P` → **Remote-SSH: Connect to Host**
2. Enter: `saurabh@autoniix.com`
3. Open `/home/saurabh/autoniix` as your workspace
4. Edit code, then restart the affected service:

```bash
docker compose restart assets    # restart single service
docker compose up -d --build assets  # rebuild + restart
```

### Option B — Git Push Deploy

Edit locally, push, CI deploys automatically:

```bash
# Local
git add .
git commit -m "fix: resolve asset query bug"
git push origin main
# → GitHub Actions runs tests → deploys to VPS on pass
# → Takes ~2-4 minutes
```

### Checking Logs

```bash
# Live logs for a specific service
docker compose logs -f assets

# All services
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100 research
```

---

## 9. Useful Commands

```bash
# Stack management
make up              # start all containers
make down            # stop all containers
make restart         # restart all containers
make health          # check all service health endpoints

# Database
make migrate         # run pending migrations
make seed            # seed prompts + system config

# Logs
make logs            # tail all logs
docker compose logs -f <service-name>

# Deploy (manual, if not using CI/CD)
git pull origin main && docker compose up -d --build

# Backup (DB + MinIO)
bash scripts/backup.sh

# Check resource usage
docker stats --no-stream

# Free up disk space (remove old images)
docker image prune -f
docker volume prune -f   # WARNING: removes unused volumes
```

---

## 10. Troubleshooting

### Container keeps restarting
```bash
docker compose logs <service-name> --tail=50
# Look for the error, fix .env or code, then:
docker compose up -d --build <service-name>
```

### Out of disk space
```bash
df -h                        # check disk usage
docker system df             # Docker-specific usage
docker image prune -f        # remove dangling images
docker builder prune -f      # clear build cache
```

### Out of memory / OOM kill
```bash
free -h                      # check available RAM
docker stats --no-stream     # per-container memory
# If RAM is maxed, restart the heaviest service:
docker compose restart research
```

### TLS cert not issuing
```bash
docker compose logs traefik | grep -i "acme\|cert\|error"
# Common causes:
# - DNS hasn't propagated yet (wait longer)
# - Port 80 blocked by UFW (check: sudo ufw status)
# - Wrong email in traefik.yml
```

### Database connection refused
```bash
docker compose ps postgres-app   # is it running?
docker compose logs postgres-app --tail=30
# If corrupted:
docker compose down
docker volume rm autoniix_postgres-data   # WARNING: data loss
docker compose up -d
make migrate && make seed
```

---

## Appendix: Monthly Cost at a Glance

| Item | Cost |
|------|------|
| Hostinger KVM 8 VPS | $25.99/mo |
| autoniix.com domain | ~$1/mo (amortized) |
| Hostinger Business Email | ~$1–2/mo |
| OpenAI API (dev usage) | ~$5–15/mo |
| Fish Audio TTS (dev) | ~$2–5/mo |
| **Total** | **~$35–50/mo** |

> In `ENVIRONMENT_MODE=test`, LLM and TTS costs are near $0 (mock providers used).
> Switch to `production` only when testing the real pipeline.
