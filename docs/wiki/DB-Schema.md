# Database Schema

## Source

- `scripts/init-db.sql` — master DDL run on first boot
- `scripts/migrations/*.sql` — numbered, additive
- pgvector extension is enabled in `init-db.sql`.

## Core

```sql
channels (
  id              TEXT PRIMARY KEY,
  workspace_id    BIGINT REFERENCES workspaces(id),
  name            TEXT,
  niche           TEXT,
  brand_id        TEXT,
  status          TEXT  -- active|disabled|archived
            CHECK (status IN ('active','disabled','archived')),
  auto_upload     BOOLEAN DEFAULT false,
  schedule_config JSONB,
  language        TEXT,
  voice_id        TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

videos (
  content_id      TEXT PRIMARY KEY,
  channel_id      TEXT REFERENCES channels(id),
  workspace_id    BIGINT,
  content_mode    TEXT,                -- long|short
  status          TEXT,                -- queued|running|paused|stopped|superseded|failed|completed
  checkpoint      TEXT,                -- current/last phase
  error_message   TEXT,
  title           TEXT,
  description     TEXT,
  tags            TEXT[],
  youtube_id      TEXT,
  environment     VARCHAR(10) NOT NULL DEFAULT 'test',
  retention_curve JSONB,
  retention_fetched_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT now(),
  delivered_at    TIMESTAMPTZ,
  CONSTRAINT env_check CHECK (environment IN ('test','production'))
);
CREATE INDEX videos_environment_idx ON videos (environment);
CREATE INDEX videos_status_idx       ON videos (status);

job_events (
  id              BIGSERIAL PRIMARY KEY,
  content_id      TEXT REFERENCES videos(content_id),
  channel_id      TEXT,
  phase           TEXT,
  state           TEXT,  -- started|completed|failed
  detail          JSONB,
  cost_usd        NUMERIC(10,4),
  environment     VARCHAR(10) NOT NULL DEFAULT 'test',
  created_at      TIMESTAMPTZ DEFAULT now()
);

audit_log (id, actor, action, target, detail JSONB, created_at);

system_config (
  config_key   TEXT PRIMARY KEY,
  config_value TEXT,
  description  TEXT,
  updated_at   TIMESTAMPTZ DEFAULT now()
);

prompt_registry (
  prompt_key   TEXT,
  version      INT,
  prompt_text  TEXT,
  active       BOOLEAN,
  PRIMARY KEY (prompt_key, version)
);
```

## Auth / multi-tenant

```sql
users (id, email UNIQUE, password_hash, name, mfa_secret,
       active_workspace_id BIGINT, created_at);
workspaces (id BIGSERIAL PK, name, owner_user_id, created_at);
workspace_members (workspace_id, user_id, role, joined_at, PK both);
workspace_invitations (id, workspace_id, email, role, token UNIQUE,
                       sent_at, accepted_at, resent_at);
```

## Research intelligence

```sql
competitor_channels (channel_id, niche, subscriber_count, avg_views, ...);
competitor_videos (video_id, competitor_channel_id, title, views,
                   published_at, is_outlier BOOLEAN);
trend_signals (niche, source, term, score, captured_at);
topic_embeddings (topic_id, embedding vector(384), simhash BIGINT);
CREATE INDEX topic_embed_ivfflat
       ON topic_embeddings USING ivfflat (embedding vector_cosine_ops);
research_features (content_id, features JSONB, predicted_score);
performance_outcomes (content_id, niche, ctr, retention, watch_time,
                      created_at);
ml_models (model_name, niche, version, blob BYTEA, metrics JSONB,
           trained_at, active BOOLEAN);
bandit_state (arm_name, niche, alpha, beta, updated_at);
phrase_bank (phrase, niche, novelty_score, sources TEXT[], created_at);
```

## Script intelligence

```sql
script_features  (content_id, features JSONB, intelligence_scores JSONB);
script_outcomes  (content_id, ctr, retention, watch_time);
script_models    (model_name, niche, blob, metrics, trained_at);
script_bandit_state (arm_name, niche, alpha, beta);
```

## Experiments / observability

```sql
experiments (name PK, status, variants JSONB, metric, created_at);
experiment_assignments (experiment_name, content_id, variant_key,
                        PK both);
experiment_outcomes (experiment_name, content_id, variant_key, value);
intelligence_metrics (service, decision_point, path_taken, cost_usd,
                      created_at);
model_health (model_name, niche, brier, psi, last_check, healthy);
```

## Library (DAM)

```sql
library_assets (id, mime_type, duration_s, width, height, license,
                source, description, tags TEXT[], embedding vector(384),
                storage_key TEXT, created_at);
```

## Related pages

- [[DB-Migrations]] · [[DB-Seed-Data]] · [[Architecture-Data-Layer]]
