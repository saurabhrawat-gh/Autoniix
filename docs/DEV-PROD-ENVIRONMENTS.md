# Dev / Prod Environment Strategy

## Short Answer

**Yes — you should have two completely separate environments with separate databases.**

This is standard practice for any system that touches real money, real APIs, and real YouTube accounts.

---

## The Two-Branch Model

```
main  ──── production server  ──── real YouTube accounts, real API keys, real $$$
  ↑
 PR
  ↑
develop ── staging/dev server ──── test YouTube accounts (or no upload), test keys
```

| | `develop` branch | `main` branch |
|---|---|---|
| **Deploys to** | Dev/Staging server | Production server |
| **Database** | Separate dev Postgres | Separate prod Postgres |
| **MinIO / S3** | Separate dev bucket | Separate prod bucket |
| **API keys** | Your personal test keys | Production keys (real spend) |
| **YouTube** | No upload (test mode) | Real channel upload |
| **Autoniix env mode** | `ENVIRONMENT_MODE=test` | `ENVIRONMENT_MODE=production` |
| **Who can merge** | You (free to push) | Only after testing on dev |

---

## GitHub Branches

```bash
git checkout -b develop    # create develop branch from current main
git push -u origin develop
```

Set `develop` as the **default branch** in GitHub settings so all feature work goes there first.

Merge flow:
```
feature/my-feature → develop → (tested) → main
```

Never push directly to `main`. Always go through `develop`.

---

## Server Setup

You need **two separate VPS/servers** (or two Docker Compose stacks on the same machine with different ports):

### Option A: Two separate VPS (recommended)
- **Dev server**: Small VPS (e.g. Hetzner CX21, $5–8/month). Just for your testing.
- **Prod server**: Your current production server.

### Option B: Two stacks on one machine (ports separated)
```
Dev stack:  ports 3001, 8001, 5433 (postgres), etc.
Prod stack: ports 3000, 8000, 5432 (postgres), etc.
```
Use a second `docker-compose.dev.yml` and a `.env.dev` for this.

---

## Environment Files

### `.env.dev` (dev server, never commit)
```env
ENVIRONMENT_MODE=test
DB_HOST=localhost
DB_PORT=5433
DB_NAME=autoniix_dev
DB_USER=autoniix_dev
DB_PASSWORD=dev_password_here

OPENAI_API_KEY=sk-...your-personal-test-key...
ELEVENLABS_API_KEY=...
FISH_AUDIO_API_KEY=...

AUTH_JWT_SECRET=dev-secret-change-for-prod
DASHBOARD_JWT_SECRET=dev-secret-change-for-prod

S3_ENDPOINT=http://localhost:9001
S3_ACCESS_KEY=devminio
S3_SECRET_KEY=devminio123
S3_BUCKET=autoniix-dev

TEMPORAL_HOST=localhost:7233
```

### `.env.prod` (production server, never commit)
```env
ENVIRONMENT_MODE=production
DB_HOST=localhost
DB_PORT=5432
DB_NAME=autoniix
DB_USER=autoniix
DB_PASSWORD=<strong-random-password>

OPENAI_API_KEY=sk-...your-real-production-key...
ELEVENLABS_API_KEY=...
FISH_AUDIO_API_KEY=...

AUTH_JWT_SECRET=<openssl rand -base64 48>
DASHBOARD_JWT_SECRET=<openssl rand -base64 48>

S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=<real-minio-key>
S3_SECRET_KEY=<real-minio-secret>
S3_BUCKET=autoniix

TEMPORAL_HOST=localhost:7233
```

**Both files must be in `.gitignore`.** Never commit real secrets.

---

## Separate Databases

On first setup of the dev server:

```bash
# Create dev database
createdb autoniix_dev

# Run migrations
psql autoniix_dev < scripts/init-db.sql
psql autoniix_dev < scripts/seed-data.sql
for f in scripts/migrations/*.sql; do psql autoniix_dev < "$f"; done

# Register first user (owner) via the dashboard
# → http://dev-server:3001/login → register
```

On the prod server, do the same but with `autoniix` database name and real credentials.

**The two databases are completely isolated.** Dev data never touches prod.

---

## CI/CD with GitHub Actions

Create `.github/workflows/deploy-dev.yml` and `.github/workflows/deploy-prod.yml`:

### Dev deploy (triggers on push to `develop`)

```yaml
# .github/workflows/deploy-dev.yml
name: Deploy → Dev

on:
  push:
    branches: [develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run unit tests
        run: |
          pip install -r requirements.txt
          pytest tests/ -x --ignore=tests/integration -q

      - name: Deploy to dev server via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEV_SERVER_HOST }}
          username: ${{ secrets.DEV_SERVER_USER }}
          key: ${{ secrets.DEV_SERVER_SSH_KEY }}
          script: |
            cd /home/autoniix/app
            git pull origin develop
            cp .env.dev .env
            docker compose pull
            docker compose up -d --build
            docker compose exec -T dashboard-bff python -m scripts.run_migrations
```

### Prod deploy (triggers on push/merge to `main`)

```yaml
# .github/workflows/deploy-prod.yml
name: Deploy → Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run full test suite
        run: |
          pip install -r requirements.txt
          pytest tests/ -x -q

      - name: Pre-flight check
        run: make deploy-check

      - name: Deploy to production via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.PROD_SERVER_HOST }}
          username: ${{ secrets.PROD_SERVER_USER }}
          key: ${{ secrets.PROD_SERVER_SSH_KEY }}
          script: |
            cd /home/autoniix/app
            git pull origin main
            cp .env.prod .env
            docker compose pull
            docker compose up -d --build
            docker compose exec -T dashboard-bff python -m scripts.run_migrations
```

### Required GitHub Secrets

Go to: `GitHub repo → Settings → Secrets and Variables → Actions`

Add:
```
DEV_SERVER_HOST       = ip-of-dev-server
DEV_SERVER_USER       = ubuntu (or your SSH user)
DEV_SERVER_SSH_KEY    = (private key content, paste full key)

PROD_SERVER_HOST      = ip-of-prod-server
PROD_SERVER_USER      = ubuntu
PROD_SERVER_SSH_KEY   = (private key content)
```

---

## Branch Protection Rules (Important)

Go to: `GitHub repo → Settings → Branches → Add rule`

For `main`:
- ✅ Require pull request before merging
- ✅ Require status checks to pass (the CI tests)
- ✅ Require at least 1 approval (even if it's just yourself via a PR)
- ❌ Allow direct pushes → OFF

This prevents accidental pushes to production.

---

## Do You Need a Separate Database for Dev?

**Yes, 100%.** Here's why:

1. **Dev migrations can break prod data** — Running a new migration on prod without testing it on dev first is dangerous.
2. **Seed data confusion** — Dev has test channels and dummy data. Prod should only have real channels.
3. **API cost isolation** — If your dev pipeline accidentally triggers, it only burns dev API keys, not prod budget.
4. **YouTube account safety** — You don't want a debug video uploaded to your real YouTube channel.
5. **Rollback safety** — You can wipe and re-seed dev without any consequence. You cannot do that with prod.

---

## Workflow: Day-to-Day

```
1. Create feature branch:       git checkout -b feature/my-feature develop
2. Write code + test locally
3. Push and open PR to develop: git push origin feature/my-feature
4. GitHub Actions runs tests automatically
5. Merge PR to develop → auto-deploys to dev server
6. Test the feature on dev server end-to-end
7. Open PR from develop → main
8. Review, approve, merge → auto-deploys to production
```

---

## Quick Answer to Your Specific Questions

| Question | Answer |
|---|---|
| **Should I create a separate database for dev?** | Yes. Completely separate DB, never shared. |
| **Separate environment for dev?** | Yes. Separate server (or separate Docker stack with different ports). |
| **Two branches: main + develop?** | Yes. This is the standard `git-flow` lite pattern. |
| **Auto-deploy develop → dev env?** | Yes. GitHub Actions on push to `develop`. |
| **Auto-deploy main → prod?** | Yes. GitHub Actions on push/merge to `main`. |
| **Do I need a PR to merge to main?** | Yes. Set branch protection. Never direct-push to `main`. |
