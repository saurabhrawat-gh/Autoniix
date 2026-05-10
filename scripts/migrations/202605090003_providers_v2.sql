-- 202605090003_providers_v2.sql
-- Phase 2 (S3): Provider/API management.
-- Secrets themselves live in Vault/Infisical; only references are in DB.

CREATE TABLE IF NOT EXISTS provider_categories (
    name        VARCHAR(40)   PRIMARY KEY,
    label       VARCHAR(120)  NOT NULL,
    kind        VARCHAR(20)   NOT NULL,  -- llm|tts|image|search|stock_footage|music|lut|sfx|storage
    description TEXT,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

INSERT INTO provider_categories (name, label, kind, description) VALUES
    ('llm',           'LLM (general)',              'llm',           'Default LLM for general tasks'),
    ('llm.research',  'LLM — Research',             'llm',           'Research / fact-finding'),
    ('llm.script',    'LLM — Script',               'llm',           'Script generation / rewrites'),
    ('llm.factcheck', 'LLM — Fact-check',           'llm',           'Fact verification'),
    ('llm.qc',        'LLM — Quality Critique',     'llm',           'Output critique / scoring'),
    ('llm.vision',    'LLM — Vision',               'llm',           'Image analysis (CTR / scene)'),
    ('llm.ideation',  'LLM — Ideation',             'llm',           'Topic + hook ideation'),
    ('llm.hook',      'LLM — Hook',                 'llm',           'Hook writer'),
    ('llm.direction', 'LLM — Direction',            'llm',           'Visual direction generation'),
    ('llm.emotion',   'LLM — Emotion',              'llm',           'Emotion mapping for TTS'),
    ('tts',           'Text-to-Speech',             'tts',           'Voice synthesis'),
    ('image',         'Image generation',           'image',         'AI image generation'),
    ('search',        'Web search',                 'search',        'Real-time web search'),
    ('storage',       'Object storage',             'storage',       'Render artifacts + assets'),
    ('stock_footage', 'Stock footage',              'stock_footage', 'Stock video clips'),
    ('music',         'Background music',           'music',         'Production music'),
    ('lut',           'Color grading LUTs',         'lut',           'LUTs library'),
    ('sfx',           'Sound effects',              'sfx',           'SFX library')
ON CONFLICT (name) DO UPDATE SET label = EXCLUDED.label, kind = EXCLUDED.kind;

CREATE TABLE IF NOT EXISTS provider_credentials (
    id              BIGSERIAL     PRIMARY KEY,
    category        VARCHAR(40)   NOT NULL REFERENCES provider_categories(name),
    provider_name   VARCHAR(60)   NOT NULL,    -- e.g. 'openai','elevenlabs','pexels'
    label           VARCHAR(120)  NOT NULL,    -- user-friendly name ("Personal OpenAI key")
    vault_path      TEXT          NOT NULL,    -- e.g. 'kv/data/providers/llm/openai/abc123'
    extra_config    JSONB         NOT NULL DEFAULT '{}'::jsonb,  -- non-secret config
    enabled         BOOLEAN       NOT NULL DEFAULT TRUE,
    rotation_due_at TIMESTAMPTZ,
    last_health_ok  BOOLEAN,
    last_health_at  TIMESTAMPTZ,
    last_latency_ms INTEGER,
    created_by      INTEGER,
    rotated_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (category, label)
);
CREATE INDEX IF NOT EXISTS provider_credentials_cat_idx
    ON provider_credentials(category, enabled);

CREATE TABLE IF NOT EXISTS provider_priority_chains (
    id                BIGSERIAL    PRIMARY KEY,
    category          VARCHAR(40)  NOT NULL REFERENCES provider_categories(name),
    position          SMALLINT     NOT NULL,
    credential_id     BIGINT       NOT NULL REFERENCES provider_credentials(id) ON DELETE CASCADE,
    fallback_strategy VARCHAR(20)  NOT NULL DEFAULT 'on_error',
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (category, position),
    CONSTRAINT chain_strategy_chk CHECK (fallback_strategy IN
        ('on_error','on_rate_limit','on_timeout','always','manual'))
);
CREATE INDEX IF NOT EXISTS provider_chains_cat_idx
    ON provider_priority_chains(category, position);

CREATE TABLE IF NOT EXISTS provider_health_log (
    id            BIGSERIAL    PRIMARY KEY,
    credential_id BIGINT       NOT NULL REFERENCES provider_credentials(id) ON DELETE CASCADE,
    ok            BOOLEAN      NOT NULL,
    latency_ms    INTEGER,
    error         TEXT,
    checked_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS provider_health_credential_idx
    ON provider_health_log(credential_id, checked_at DESC);
