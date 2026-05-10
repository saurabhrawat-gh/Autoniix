# 14 — v2 Revamp Runbook

How to bring the new dashboard online without breaking anything.

## 1. Apply DB migrations

All migrations are additive — no destructive ops on existing tables.

```bash
python -m scripts.run_migrations --status   # see what's pending
python -m scripts.run_migrations             # apply
python -m scripts.backfill_channel_profiles # seed profiles for the 10 existing channels
```

Applied migrations are tracked in `schema_migrations`. Re-running is safe.

## 2. Install new Python deps

```bash
pip install -r requirements.txt
```

New: `sentry-sdk[fastapi]`, `argon2-cffi`, `pyotp`, `PyJWT`, `authlib`,
`email-validator`, `hvac`. Infisical SDK stays optional.

## 3. Restart services

```bash
docker compose build dashboard-bff dashboard-ui worker-production worker-scheduler
docker compose up -d
```

Existing endpoints under `/api/*` keep working unchanged. The new
surface lives at `/api/v2/*` and `/dashboard/v2/*`.

## 4. Turn on the v2 UI

By default `ui.v2.enabled` is **off** so the new pages don't surprise
existing users. Toggle it from the legacy dashboard:

```sql
UPDATE feature_flags SET enabled = TRUE WHERE key = 'ui.v2.enabled';
```

…or via the v2 settings page (after one auth toggle below).

## 5. Optional: enable real auth

```sql
UPDATE feature_flags SET enabled = TRUE  WHERE key = 'auth.v2.enabled';
UPDATE feature_flags SET enabled = FALSE WHERE key = 'auth.legacy.enabled';
```

First registration auto-promotes to `owner`. Visit `/register`.

## 6. Optional: enable Vault/Infisical

```bash
docker compose --profile secrets up -d infisical
# point your services at it
export SECRETS_BACKEND=infisical
export INFISICAL_CLIENT_ID=...
export INFISICAL_CLIENT_SECRET=...
```

`SECRETS_FALLBACK=env` keeps the env-based path alive as a safety net.

## 7. Optional: enable provider DB-chain

Once at least one credential is added in `/dashboard/v2/providers/<category>`:

```sql
UPDATE feature_flags SET enabled = TRUE WHERE key = 'providers.db_chain.enabled';
```

`ProviderRegistry.get(...)` will now consult the DB chain first and fall
back to env vars if no chain is configured for that category. No worker
restart required (chain cache resets on credential rotate / chain change).

## 8. Optional: Slack alerts

1. Add a credential at `/dashboard/v2/providers` for category
   ``notifications`` (or set `SLACK_WEBHOOK_URL` in env as a fallback).
2. In `/dashboard/v2/notifications` → **Routes**, enable
   "Critical to Slack" and "Errors to Slack".
3. Test with:
   ```sh
   curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"event_type":"pipeline.test","severity":"critical","title":"Hello from yt-automation"}' \
     http://localhost:8020/api/v2/notifications
   ```

## 9. Optional: Sentry

Set `SENTRY_DSN` in `.env`. Every FastAPI service + Temporal worker
auto-initializes when the env var is present. Init is a no-op otherwise.

## 10. Smoke test

```bash
python -m pytest tests/test_v2_secrets_and_registry.py -q
```

Should print `4 passed`. Hit `/api/v2/flags` with your token to confirm
the v2 router is mounted.

## What still works exactly as before

- All `/api/*` legacy endpoints (snapshot-tested in CI).
- All Temporal workflows + activities.
- All existing service-to-service contracts.
- Env-based provider config (`LLM_PROVIDER=…` etc.) when the DB chain
  is empty or the flag is off.
- The legacy dashboard at `/dashboard/*`.
