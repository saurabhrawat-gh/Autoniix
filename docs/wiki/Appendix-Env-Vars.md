# Appendix: Environment Variables

Every env var read by the stack. Source of truth: `.env.example`,
`.env.production.example`, `src/config.py`, and per-service `env_file: .env`.

## Application

| Var | Default | Read by |
|---|---|---|
| `ENVIRONMENT_MODE` | `test` | `src/environment.py` |
| `DB_HOST` | `postgres-app` | all |
| `DB_PORT` | `5432` | all |
| `DB_NAME` | `autoniix` | all |
| `DB_USER` | `app` | all |
| `DB_PASSWORD` | `change_me_strong_random_64` | all |
| `REDIS_URL` | `redis://redis:6379` | all |
| `S3_ENDPOINT` | `http://minio:9000` | storage |
| `S3_ACCESS_KEY` | `minioadmin` | storage, remotion |
| `S3_SECRET_KEY` | `minioadmin` | storage, remotion |
| `S3_BUCKET` | `autoniix` | storage, remotion |
| `S3_PUBLIC_BASE_URL` | `` | storage |
| `S3_FORCE_PATH_STYLE` | `true` | storage |

## LLM / TTS / Image / Search

| Var | Used by |
|---|---|
| `OPENAI_API_KEY` | openai_provider |
| `ANTHROPIC_API_KEY` | claude_provider |
| `GOOGLE_AI_API_KEY` | gemini_provider |
| `FISH_AUDIO_API_KEY` | fish_audio TTS |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_MODEL_ID` | elevenlabs TTS |
| `TTS_PROVIDER` | TTS registry |
| `SERPAPI_KEY` | serpapi_provider |
| `NEWS_API_KEY` | research |
| `SEARCH_PROVIDER` | search registry |
| `PIXABAY_API_KEY` / `PEXELS_API_KEY` / `FREESOUND_API_KEY` | assets |
| `IMAGE_PROVIDER` | image registry |
| `LLM_*_PROVIDER` (10 keys) | LLM router |
| `LLM_OPENAI_MODEL`, `LLM_CLAUDE_MODEL`, `LLM_GEMINI_MODEL` | model overrides |

## YouTube / Google OAuth

| Var | Notes |
|---|---|
| `YOUTUBE_API_KEY` | delivery, retention |
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth client |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth client |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | uploads + analytics |
| `GOOGLE_SHEETS_ID` | sheets-sync |
| `GOOGLE_SHEETS_CREDENTIALS_JSON` | sheets-sync |

## Temporal

| Var | Default | Notes |
|---|---|---|
| `TEMPORAL_HOST` | `temporal:7233` | |
| `TEMPORAL_NAMESPACE` | `default` | |
| `TEMPORAL_PRODUCTION_MAX_ACTIVITIES` | 5 | concurrency knob |
| `TEMPORAL_PRODUCTION_MAX_WORKFLOW_TASKS` | 10 | |
| `TEMPORAL_SCHEDULER_MAX_ACTIVITIES` | 3 | |
| `TEMPORAL_DEFAULT_ACTIVITY_START_TO_CLOSE_S` | 1800 | |
| `TEMPORAL_DEFAULT_ACTIVITY_HEARTBEAT_S` | 60 | |
| `TEMPORAL_DB_PASSWORD` | `change_me_temporal_64` | Temporal’s own DB |

## Auth / secrets

| Var | Required in production |
|---|---|
| `ADMIN_JWT_SECRET` | yes |
| `AUTH_JWT_SECRET` | yes |
| `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` | yes |
| `SECRETS_BACKEND` | optional (`env`/`infisical`) |
| `INFISICAL_ENCRYPTION_KEY` / `INFISICAL_AUTH_SECRET` | with `secrets` profile |

## TLS / Traefik

| Var | Notes |
|---|---|
| `DOMAIN` | base domain |
| `DASH_DOMAIN`, `API_DOMAIN`, `GRAFANA_DOMAIN`, `PROMETHEUS_DOMAIN`, `ALERTS_DOMAIN`, `TEMPORAL_DOMAIN` | split-host subdomains |
| `ACME_EMAIL` | Let’s Encrypt |
| `TRAEFIK_BASIC_AUTH` | htpasswd, `$$`-escaped |

## Observability

| Var | Notes |
|---|---|
| `SLACK_WEBHOOK_URL` | Alertmanager |
| `SENTRY_DSN` | optional, read by `src/observability/sentry.py` |

## Remotion

| Var | Notes |
|---|---|
| `REMOTION_BASE_URL` | `http://remotion-api:4000` |
| `RENDER_CONCURRENCY` | per worker |
| `DIFF_CACHE_ENABLED` | vision profile |
| `S3_KEY_PREFIX` | propagated from `ENVIRONMENT_MODE` |

## Related pages

- [[Providers-Secrets]] · [[Operations-Runbook]] · [[CI-CD]]
