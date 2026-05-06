# Production Setup Checklist

End-to-end checklist to take the system from local test mode to a real revenue-generating production deployment.

---

## 1. Environment Files

Two ready-to-use templates exist:

| File | Mode | Purpose |
|------|------|---------|
| `.env.test`    | `test`       | Mock providers, free APIs, no YouTube upload, ~$0/video |
| `.env.prod`    | `production` | Real paid APIs, full pipeline, YouTube upload enabled |
| `.env.example` | reference    | Master reference with documentation for every key |

The active config is always `.env`. Use Makefile shortcuts to switch:

```bash
make use-test    # Activates .env.test
make use-prod    # Activates .env.prod (requires typing 'production' to confirm)
make env-status  # Shows currently active mode
```

The current `.env` is auto-backed-up to `.env.backup.<timestamp>` on every switch.

> **Security**: `.env`, `.env.test`, `.env.prod`, and `.env.backup.*` are all `.gitignore`'d via `.env.*` pattern. Never commit them.

---

## 2. Required API Keys for Production

Edit `.env.prod` and replace every `CHANGE_ME` and `PROD-*-here` placeholder.

### Critical (pipeline fails without these)

| Key | Where to get | Cost |
|-----|--------------|------|
| `OPENAI_API_KEY`           | platform.openai.com/api-keys     | ~$0.50-1.50/video |
| `FISH_AUDIO_API_KEY`       | fish.audio                        | ~$0.02-0.05/video |
| `PIXABAY_API_KEY`          | pixabay.com/api/docs              | FREE |
| `PEXELS_API_KEY`           | pexels.com/api                    | FREE |
| `YOUTUBE_API_KEY`          | console.cloud.google.com          | FREE (10K quota/day) |
| `GOOGLE_OAUTH_CLIENT_ID`     | console.cloud.google.com (OAuth)  | FREE |
| `GOOGLE_OAUTH_CLIENT_SECRET` | same as above                     | FREE |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | OAuth Playground                  | FREE |

### Recommended (cost-optimized routing + quality)

| Key | Why | Cost |
|-----|-----|------|
| `ANTHROPIC_API_KEY`  | Better script writing (Claude Sonnet) | ~$0.30-1.00/video |
| `GOOGLE_AI_API_KEY`  | 20x cheaper than GPT-4o for research/QC | ~$0.01-0.05/video |
| `SERPAPI_KEY`        | Google web search for research | $50/mo |

### Optional

| Key | Why | Cost |
|-----|-----|------|
| `ELEVENLABS_API_KEY`   | Premium voice fidelity   | $5-22/mo |
| `ENVATO_API_KEY`       | Premium stock footage    | $16.50/mo |
| `FREESOUND_API_KEY`    | SFX & ambient audio      | FREE |
| `NEWS_API_KEY`         | Trending news in research | FREE (100/day) |
| `GOOGLE_SHEETS_*`      | Monitoring sync           | FREE |

---

## 3. Infrastructure Hardening

Before flipping `ENVIRONMENT_MODE=production`, replace **every** `CHANGE_ME` with strong random values:

```bash
# Generate strong secrets
openssl rand -base64 48   # → DB_PASSWORD
openssl rand -base64 48   # → TEMPORAL_DB_PASSWORD
openssl rand -base64 48   # → S3_ACCESS_KEY (or use UUID)
openssl rand -base64 48   # → S3_SECRET_KEY
openssl rand -base64 48   # → ADMIN_JWT_SECRET
openssl rand -base64 32   # → Redis password
```

### Redis AUTH

Production Redis must require a password. Update `REDIS_URL`:

```
REDIS_URL=redis://:YOUR_REDIS_PASSWORD@redis:6379
```

And configure Redis to require AUTH. In `docker-compose.yml`, the `redis` service should be set with `--requirepass` (verify before deploying).

### MinIO

Change from default `minioadmin`/`minioadmin` to strong credentials. After first start, remove any default buckets and recreate with the new credentials.

### Postgres

- The Docker image stores data in the `pg_app_data` named volume — back this up.
- Set up `pg_dump` cron for daily backups:
  ```bash
  0 2 * * * docker compose exec -T postgres-app pg_dump -U app yt_automation | gzip > /backup/yt_$(date +\%F).sql.gz
  ```

---

## 4. YouTube OAuth Setup (one-time, ~20 min)

1. **Google Cloud Console** → APIs & Services → enable **YouTube Data API v3**
2. **Credentials** → Create **API Key** → paste into `YOUTUBE_API_KEY`
3. **Credentials** → Create **OAuth 2.0 Client ID** (type: Web Application)
   - Authorized redirect URIs: `https://developers.google.com/oauthplayground`
   - Copy Client ID + Client Secret into `.env.prod`
4. **Get refresh token**:
   - Go to https://developers.google.com/oauthplayground
   - Settings (gear icon) → "Use your own OAuth credentials" → paste Client ID/Secret
   - In Step 1, scope: `https://www.googleapis.com/auth/youtube.upload`
   - Authorize → exchange auth code for tokens → copy `refresh_token`
   - Paste into `GOOGLE_OAUTH_REFRESH_TOKEN`
5. **For >100 users**: submit OAuth consent screen for Google verification (days-weeks)

---

## 5. Domain & TLS

If exposing the dashboard publicly:

```env
DOMAIN=yourdomain.com
ACME_EMAIL=admin@yourdomain.com
S3_PUBLIC_BASE_URL=https://cdn.yourdomain.com/yt-automation
```

Traefik (in `docker-compose.yml`) will auto-provision Let's Encrypt certificates.

---

## 6. First Production Deploy

```bash
# 1. Edit .env.prod, fill in all keys
nano .env.prod

# 2. Activate prod mode (will check for CHANGE_ME placeholders, abort if found)
make use-prod

# 3. Start the stack
make up

# 4. Verify health
make health

# 5. Watch dashboard for env pill — should show red "PRODUCTION"
open http://yourdomain.com
```

---

## 7. Cost Monitoring

Production budget guardrails are in `system_config`:

| Key | Default | Purpose |
|-----|---------|---------|
| `daily_budget_limit_usd`     | 50.00 | Hard cap; production stops above this |
| `max_videos_per_day`         | 30    | Hard cap on production runs |
| `test_daily_budget_limit`    | 5.00  | Test-mode ceiling (defensive) |
| `test_max_videos_per_day`    | 10    | Test-mode video ceiling |

Adjust via the Admin dashboard `/dashboard/settings`.

The `intelligence/savings` admin endpoint reports cumulative cost saved by the local-first intelligence layer (vs. always-LLM baseline).

---

## 8. Estimated Monthly Cost (30 videos/month, all-paid)

| Service | Cost |
|---------|------|
| OpenAI (GPT-4o + DALL-E 3)        | $50-100 |
| Anthropic (Claude Sonnet, scripts)| $10-30 |
| Google AI (Gemini Flash, research/QC) | $1-5 |
| Fish Audio TTS                    | $2-5 |
| SerpAPI                           | $50 |
| ElevenLabs (optional)             | $5-22 |
| Envato Elements (optional)        | $16.50 |
| Pixabay / Pexels / YouTube        | FREE |
| Self-hosted infra (your hardware) | $0 |
| **Total**                         | **~$135-230/mo** |

---

## 9. Rollback to Test Mode

If something goes wrong in production:

```bash
make use-test     # instantly switches back to mock providers
make restart-app  # rebuild + restart app containers
```

The DB and MinIO retain prod data (storage is keyed by `prod/` vs `test/` prefix), so no data is lost.

---

## 10. Switching Stories

### Story: "I want to test a new prompt without burning real money"
```bash
make use-test
make restart-app
# Trigger a video — uses MockLLM with cached fixtures, $0 cost
```

### Story: "I want to ship the 50th real video this month"
```bash
make env-status   # confirm 🔴 PRODUCTION is active
# Trigger from dashboard, watch Temporal UI at :8080
```

### Story: "I edited .env.prod and need to apply changes"
```bash
make use-prod      # re-activates with confirmation
make restart-app   # picks up new env vars
```
