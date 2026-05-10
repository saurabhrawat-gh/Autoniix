-- 202605110005_provider_routing.sql
-- Wave 2: provider_routes, provider_quotas, provider_marketplace_catalog, provider_sandbox_runs
-- Additive only — no destructive changes to existing tables.

-- ── Provider marketplace catalog ──────────────────────────────────────────────
-- Static registry of all known providers (connected or not).
CREATE TABLE IF NOT EXISTS provider_marketplace_catalog (
    id              BIGSERIAL     PRIMARY KEY,
    provider_key    VARCHAR(60)   NOT NULL UNIQUE,  -- e.g. 'openai', 'elevenlabs', 'pexels'
    display_name    VARCHAR(120)  NOT NULL,
    category        VARCHAR(40)   NOT NULL REFERENCES provider_categories(name),
    description     TEXT,
    logo_url        TEXT,
    website_url     TEXT,
    mode            VARCHAR(20)   NOT NULL DEFAULT 'byok',  -- byok|system|marketplace|internal
    capabilities    TEXT[]        NOT NULL DEFAULT '{}',     -- e.g. ['text-gen','vision','function-call']
    pricing_notes   TEXT,
    cost_unit       VARCHAR(60),   -- e.g. '$0.002 / 1K tokens'
    regions         TEXT[]        NOT NULL DEFAULT '{}',
    has_free_tier   BOOLEAN       NOT NULL DEFAULT FALSE,
    featured        BOOLEAN       NOT NULL DEFAULT FALSE,
    sort_order      SMALLINT      NOT NULL DEFAULT 100,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS pmcat_category_idx ON provider_marketplace_catalog(category);
CREATE INDEX IF NOT EXISTS pmcat_mode_idx ON provider_marketplace_catalog(mode);

-- Seed the catalog with known providers
INSERT INTO provider_marketplace_catalog
    (provider_key, display_name, category, description, mode, capabilities, cost_unit, has_free_tier, featured, sort_order)
VALUES
    -- LLM
    ('openai',        'OpenAI (GPT-4o)',       'llm',   'State-of-the-art general purpose LLM with vision.',         'byok',     ARRAY['text-gen','function-call','vision','json-mode'], '$0.002/1K tok',  false, true,  10),
    ('anthropic',     'Anthropic (Claude)',    'llm',   'Constitutional AI — strong reasoning, 200K context.',       'byok',     ARRAY['text-gen','function-call','vision'],              '$0.003/1K tok',  false, true,  20),
    ('gemini',        'Google Gemini',         'llm',   'Multimodal flagship model from Google DeepMind.',           'byok',     ARRAY['text-gen','vision','function-call'],              '$0.001/1K tok',  false, false, 30),
    ('groq',          'Groq (Llama-3)',        'llm',   'Ultra-fast inference on open-source models.',               'byok',     ARRAY['text-gen'],                                      '$0.0001/1K tok', true,  false, 40),
    ('ollama',        'Ollama (local)',        'llm',   'Run open-source models locally — zero marginal cost.',      'internal', ARRAY['text-gen'],                                      '$0.00 (local)',  true,  false, 50),
    -- TTS
    ('fishaudio',     'Fish Audio',            'tts',   'Expressive PAYG TTS with emotion parameter control.',       'byok',     ARRAY['tts-standard','tts-emotion','tts-clone'],        '$0.001/char',    false, true,  10),
    ('elevenlabs',    'ElevenLabs',            'tts',   'Industry-leading TTS with voice cloning and emotion.',      'byok',     ARRAY['tts-standard','tts-emotion','tts-clone'],        '$0.0003/char',   true,  true,  20),
    ('edge_tts',      'Edge TTS (free)',       'tts',   'Microsoft Edge TTS — free tier, good quality.',             'system',   ARRAY['tts-standard'],                                  'Free',           true,  false, 30),
    -- Image
    ('openai_dalle',  'DALL-E 3',              'image', 'High-quality image generation from OpenAI.',               'byok',     ARRAY['image-gen','image-edit'],                         '$0.04/image',    false, true,  10),
    ('stability',     'Stability AI',          'image', 'Stable Diffusion API — flexible and low cost.',             'byok',     ARRAY['image-gen','image-edit','upscale'],               '$0.002/image',   false, false, 20),
    ('fal_ai',        'fal.ai',                'image', 'Fast image models including Flux and SDXL.',                'byok',     ARRAY['image-gen'],                                     '$0.003/image',   true,  false, 30),
    -- Search
    ('perplexity',    'Perplexity',            'search','Real-time web search with cited sources.',                  'byok',     ARRAY['web-search','news-search'],                      '$5/1K req',      false, true,  10),
    ('serper',        'Serper',                'search','Google SERP API — fast, cheap, accurate.',                  'byok',     ARRAY['web-search','news-search','image-search'],        '$0.001/req',     true,  true,  20),
    ('tavily',        'Tavily',                'search','AI-optimized search API with structured output.',           'byok',     ARRAY['web-search'],                                    '$0.002/req',     true,  false, 30),
    -- Stock footage
    ('pexels',        'Pexels',                'stock_footage', 'Free stock photos and videos.',                     'byok',     ARRAY['stock-video','stock-image'],                     'Free',           true,  true,  10),
    ('pixabay',       'Pixabay',               'stock_footage', 'Free-to-use media library.',                        'byok',     ARRAY['stock-video','stock-image'],                     'Free',           true,  false, 20),
    ('envato',        'Envato Elements',       'stock_footage', 'Premium stock footage library.',                    'byok',     ARRAY['stock-video','stock-image','music'],              '$16.50/mo',      false, false, 30)
ON CONFLICT (provider_key) DO UPDATE
    SET display_name  = EXCLUDED.display_name,
        capabilities  = EXCLUDED.capabilities,
        cost_unit     = EXCLUDED.cost_unit,
        featured      = EXCLUDED.featured;


-- ── Provider routing policies (scope-aware) ───────────────────────────────────
-- Each row says: for capability X at scope Y, route using policy Z with these constraints.
CREATE TABLE IF NOT EXISTS provider_routes (
    id              BIGSERIAL     PRIMARY KEY,
    scope           VARCHAR(20)   NOT NULL DEFAULT 'workspace',  -- system|workspace|brand|channel|project
    scope_id        VARCHAR(120),  -- NULL = system-wide
    category        VARCHAR(40)   NOT NULL REFERENCES provider_categories(name),
    policy          VARCHAR(20)   NOT NULL DEFAULT 'balanced',   -- cheapest|fastest|highest_quality|balanced|custom
    custom_rules    JSONB         NOT NULL DEFAULT '{}'::jsonb,  -- JSON-Logic expression (for 'custom' policy)
    primary_credential_id  BIGINT REFERENCES provider_credentials(id) ON DELETE SET NULL,
    fallback_chain  BIGINT[]      NOT NULL DEFAULT '{}',         -- ordered credential_ids
    enabled         BOOLEAN       NOT NULL DEFAULT TRUE,
    created_by      INTEGER,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT route_policy_chk CHECK (policy IN ('cheapest','fastest','highest_quality','balanced','custom')),
    CONSTRAINT route_scope_chk  CHECK (scope   IN ('system','workspace','brand','channel','project')),
    UNIQUE (scope, scope_id, category)
);
CREATE INDEX IF NOT EXISTS provider_routes_scope_idx ON provider_routes(scope, scope_id);
CREATE INDEX IF NOT EXISTS provider_routes_category_idx ON provider_routes(category);


-- ── Provider quotas ───────────────────────────────────────────────────────────
-- Monthly spend caps per scope. On INSERT/UPDATE the period resets each calendar month.
CREATE TABLE IF NOT EXISTS provider_quotas (
    id              BIGSERIAL     PRIMARY KEY,
    scope           VARCHAR(20)   NOT NULL DEFAULT 'workspace',
    scope_id        VARCHAR(120),
    category        VARCHAR(40)   REFERENCES provider_categories(name),  -- NULL = all categories
    monthly_cap_usd NUMERIC(10,4) NOT NULL DEFAULT 50.0,
    current_spend   NUMERIC(10,4) NOT NULL DEFAULT 0.0,
    period_start    DATE          NOT NULL DEFAULT DATE_TRUNC('month', NOW()),
    alert_pct       SMALLINT      NOT NULL DEFAULT 80,  -- send alert when spend > alert_pct% of cap
    hard_limit      BOOLEAN       NOT NULL DEFAULT FALSE, -- if TRUE: reject requests when capped
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT quota_scope_chk CHECK (scope IN ('system','workspace','brand','channel','project')),
    UNIQUE (scope, scope_id, category)
);

-- ── Sandbox run log ───────────────────────────────────────────────────────────
-- Stores test inference outputs for the sandbox runner UI.
CREATE TABLE IF NOT EXISTS provider_sandbox_runs (
    id              BIGSERIAL     PRIMARY KEY,
    credential_id   BIGINT        NOT NULL REFERENCES provider_credentials(id) ON DELETE CASCADE,
    run_by          INTEGER,
    capability      VARCHAR(40)   NOT NULL,  -- 'text-gen','tts-standard','image-gen'
    input_payload   JSONB         NOT NULL DEFAULT '{}'::jsonb,
    output_payload  JSONB         NOT NULL DEFAULT '{}'::jsonb,
    ok              BOOLEAN       NOT NULL DEFAULT FALSE,
    latency_ms      INTEGER,
    cost_usd        NUMERIC(10,6),
    error           TEXT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS psandbox_credential_idx ON provider_sandbox_runs(credential_id, created_at DESC);
CREATE INDEX IF NOT EXISTS psandbox_run_by_idx ON provider_sandbox_runs(run_by, created_at DESC);
