-- AE-71 (#90): Provider Catalog Seeding Migration
-- 1. Extend provider_marketplace_catalog with config_schema, supported_models, etc.
-- 2. Add pipeline_mode column to provider_chains_v2 and provider_credentials
-- 3. Add rotation_hint column to provider_credentials
-- 4. Add asset_sources category seed
-- 5. Seed missing providers (serpapi, minio, kimi, glm) into catalog
-- 6. Seed config_schema + supported_models + docs_url + pricing_tier for all providers
-- 7. Rebuild pipeline_mode-aware indexes

-- ─── 1. Extend provider_marketplace_catalog ───────────────────────────────────

ALTER TABLE provider_marketplace_catalog
    ADD COLUMN IF NOT EXISTS config_schema      JSONB        NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS supported_models   JSONB        NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS is_platform_seeded BOOLEAN      NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS docs_url           TEXT,
    ADD COLUMN IF NOT EXISTS pricing_tier       VARCHAR(20)  NOT NULL DEFAULT 'paid';

-- ─── 2. pipeline_mode on provider_chains_v2 ───────────────────────────────────

ALTER TABLE provider_chains_v2
    ADD COLUMN IF NOT EXISTS pipeline_mode TEXT NOT NULL DEFAULT 'production';

CREATE INDEX IF NOT EXISTS chains_v2_pipeline_mode_idx
    ON provider_chains_v2(pipeline_mode, scope, scope_id, content_mode, category);

-- ─── 3. pipeline_mode + rotation_hint on provider_credentials ─────────────────

ALTER TABLE provider_credentials
    ADD COLUMN IF NOT EXISTS pipeline_mode TEXT NOT NULL DEFAULT 'production',
    ADD COLUMN IF NOT EXISTS rotation_hint TEXT;

CREATE INDEX IF NOT EXISTS provider_credentials_pipeline_mode_idx
    ON provider_credentials(category, pipeline_mode, enabled);

-- ─── 4. asset_sources category ────────────────────────────────────────────────

INSERT INTO provider_categories (name, label, kind, description)
VALUES ('asset_sources', 'Asset Sources', 'asset_source', 'Stock media and asset providers')
ON CONFLICT (name) DO UPDATE
    SET label       = EXCLUDED.label,
        kind        = EXCLUDED.kind,
        description = EXCLUDED.description;

-- ─── 5. Seed missing providers into catalog ───────────────────────────────────

INSERT INTO provider_marketplace_catalog
    (provider_key, display_name, category, description, mode, capabilities, cost_unit, has_free_tier, featured, sort_order)
VALUES
    ('serpapi',   'SerpAPI',             'search',  'Google SERP API — accurate, supports GL/HL locale.',           'byok', ARRAY['web-search','news-search','image-search'],  '$0.001/req',    false, true,  15),
    ('minio',     'MinIO (self-hosted)', 'storage', 'S3-compatible object storage, fully self-hosted.',             'byok', ARRAY['object-store','upload','presigned-url'],     'Free (self)',   true,  true,  10),
    ('kimi',      'Moonshot Kimi',       'llm',     'Long-context LLM from Moonshot AI (OpenAI-compatible).',      'byok', ARRAY['text-gen','function-call'],                   '$0.0012/1K tok',false, false, 55),
    ('glm',       'Zhipu GLM',           'llm',     'BigModel GLM-4 from Zhipu AI — OpenAI-compatible API.',       'byok', ARRAY['text-gen','function-call'],                   '$0.0007/1K tok',false, false, 60),
    ('custom_openai_compat', 'Custom (OpenAI-compatible)', 'llm', 'Any LLM with an OpenAI-compatible /v1/chat/completions endpoint.', 'byok', ARRAY['text-gen'], 'varies', true, false, 99)
ON CONFLICT (provider_key) DO UPDATE
    SET display_name  = EXCLUDED.display_name,
        description   = EXCLUDED.description,
        capabilities  = EXCLUDED.capabilities,
        cost_unit     = EXCLUDED.cost_unit,
        featured      = EXCLUDED.featured;

-- ─── 6. Seed config_schema, supported_models, docs_url, pricing_tier ──────────

-- openai
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Starts with sk-"},{"name":"model","type":"select","label":"Default Model","required":false,"options":["gpt-4o","gpt-4o-mini"]}]'::jsonb,
    supported_models = '["gpt-4o","gpt-4o-mini"]'::jsonb,
    docs_url         = 'https://platform.openai.com/docs/api-reference',
    pricing_tier     = 'paid'
WHERE provider_key = 'openai';

-- anthropic (claude)
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Starts with sk-ant-"},{"name":"model","type":"select","label":"Default Model","required":false,"options":["claude-sonnet-4-20250514","claude-3-5-sonnet-20241022","claude-3-5-haiku-20241022"]}]'::jsonb,
    supported_models = '["claude-sonnet-4-20250514","claude-3-5-sonnet-20241022","claude-3-5-haiku-20241022"]'::jsonb,
    docs_url         = 'https://docs.anthropic.com/en/api',
    pricing_tier     = 'paid'
WHERE provider_key = 'anthropic';

-- gemini
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true},{"name":"model","type":"select","label":"Default Model","required":false,"options":["gemini-2.0-flash","gemini-1.5-pro","gemini-1.5-flash"]}]'::jsonb,
    supported_models = '["gemini-2.0-flash","gemini-1.5-pro","gemini-1.5-flash"]'::jsonb,
    docs_url         = 'https://ai.google.dev/api',
    pricing_tier     = 'paid'
WHERE provider_key = 'gemini';

-- groq
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true},{"name":"model","type":"select","label":"Default Model","required":false,"options":["llama-3.3-70b-versatile","llama-3.1-8b-instant","mixtral-8x7b-32768"]}]'::jsonb,
    supported_models = '["llama-3.3-70b-versatile","llama-3.1-8b-instant","mixtral-8x7b-32768"]'::jsonb,
    docs_url         = 'https://console.groq.com/docs/openai',
    pricing_tier     = 'paid'
WHERE provider_key = 'groq';

-- ollama (local, no API key)
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"base_url","type":"text","label":"Base URL","required":true,"placeholder":"http://localhost:11434"},{"name":"model","type":"text","label":"Model Name","required":true,"placeholder":"llama3.2"}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://ollama.com/library',
    pricing_tier     = 'free'
WHERE provider_key = 'ollama';

-- kimi (Moonshot)
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Get from platform.moonshot.cn"},{"name":"model","type":"select","label":"Default Model","required":false,"options":["moonshot-v1-8k","moonshot-v1-32k","moonshot-v1-128k"]}]'::jsonb,
    supported_models = '["moonshot-v1-8k","moonshot-v1-32k","moonshot-v1-128k"]'::jsonb,
    docs_url         = 'https://platform.moonshot.cn/docs/api',
    pricing_tier     = 'paid'
WHERE provider_key = 'kimi';

-- glm (Zhipu)
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Get from open.bigmodel.cn"},{"name":"model","type":"select","label":"Default Model","required":false,"options":["glm-4-flash","glm-4","glm-4-air"]}]'::jsonb,
    supported_models = '["glm-4-flash","glm-4","glm-4-air"]'::jsonb,
    docs_url         = 'https://open.bigmodel.cn/dev/api',
    pricing_tier     = 'paid'
WHERE provider_key = 'glm';

-- fishaudio (Fish Audio TTS)
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true},{"name":"voice_id","type":"text","label":"Voice ID","required":true,"placeholder":"Fish Audio voice ID or reference audio ID"}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://fish.audio/en/docs',
    pricing_tier     = 'paid'
WHERE provider_key = 'fishaudio';

-- elevenlabs
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true},{"name":"voice_id","type":"text","label":"Voice ID","required":false,"placeholder":"Leave blank for default (Rachel)"},{"name":"model_id","type":"select","label":"Model","required":false,"options":["eleven_multilingual_v2","eleven_turbo_v2_5","eleven_turbo_v2"]}]'::jsonb,
    supported_models = '["eleven_multilingual_v2","eleven_turbo_v2_5","eleven_turbo_v2"]'::jsonb,
    docs_url         = 'https://elevenlabs.io/docs/api-reference',
    pricing_tier     = 'paid'
WHERE provider_key = 'elevenlabs';

-- edge_tts (free — no API key)
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"voice","type":"text","label":"Voice Name","required":false,"placeholder":"en-US-AriaNeural","hint":"See https://learn.microsoft.com/azure/ai-services/speech-service/language-support"}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://learn.microsoft.com/azure/ai-services/speech-service/language-support',
    pricing_tier     = 'free'
WHERE provider_key = 'edge_tts';

-- openai_dalle (DALL-E 3)
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Same OpenAI key as LLM"},{"name":"size","type":"select","label":"Image Size","required":false,"options":["1024x1024","1792x1024","1024x1792"]},{"name":"quality","type":"select","label":"Quality","required":false,"options":["standard","hd"]}]'::jsonb,
    supported_models = '["dall-e-3"]'::jsonb,
    docs_url         = 'https://platform.openai.com/docs/api-reference/images',
    pricing_tier     = 'paid'
WHERE provider_key = 'openai_dalle';

-- stability AI
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true}]'::jsonb,
    supported_models = '["stable-diffusion-3","stable-image-ultra","stable-image-core"]'::jsonb,
    docs_url         = 'https://platform.stability.ai/docs/api-reference',
    pricing_tier     = 'paid'
WHERE provider_key = 'stability';

-- fal.ai
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Format: KEY_ID:KEY_SECRET"}]'::jsonb,
    supported_models = '["fal-ai/flux","fal-ai/flux/dev","fal-ai/stable-diffusion-v3-medium"]'::jsonb,
    docs_url         = 'https://fal.ai/docs',
    pricing_tier     = 'paid'
WHERE provider_key = 'fal_ai';

-- serpapi
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true},{"name":"gl","type":"text","label":"Country Code","required":false,"placeholder":"us"},{"name":"hl","type":"text","label":"Language","required":false,"placeholder":"en"}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://serpapi.com/search-api',
    pricing_tier     = 'paid'
WHERE provider_key = 'serpapi';

-- perplexity
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true},{"name":"model","type":"select","label":"Model","required":false,"options":["sonar","sonar-pro","sonar-deep-research"]}]'::jsonb,
    supported_models = '["sonar","sonar-pro","sonar-deep-research"]'::jsonb,
    docs_url         = 'https://docs.perplexity.ai',
    pricing_tier     = 'paid'
WHERE provider_key = 'perplexity';

-- serper
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://serper.dev/api',
    pricing_tier     = 'paid'
WHERE provider_key = 'serper';

-- tavily
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://docs.tavily.com',
    pricing_tier     = 'paid'
WHERE provider_key = 'tavily';

-- minio (storage)
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"endpoint_url","type":"text","label":"Endpoint URL","required":true,"placeholder":"http://minio:9000"},{"name":"access_key","type":"text","label":"Access Key","required":true},{"name":"secret_key","type":"password","label":"Secret Key","required":true},{"name":"bucket","type":"text","label":"Bucket Name","required":true},{"name":"region","type":"text","label":"Region","required":false,"placeholder":"us-east-1"},{"name":"use_ssl","type":"boolean","label":"Use SSL","required":false}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://min.io/docs/minio/linux/developers/python',
    pricing_tier     = 'free'
WHERE provider_key = 'minio';

-- pexels
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://www.pexels.com/api/documentation',
    pricing_tier     = 'free'
WHERE provider_key = 'pexels';

-- pixabay
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://pixabay.com/api/docs',
    pricing_tier     = 'free'
WHERE provider_key = 'pixabay';

-- envato
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://build.envato.com/api',
    pricing_tier     = 'paid'
WHERE provider_key = 'envato';

-- custom_openai_compat
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"base_url","type":"text","label":"Base URL","required":true,"placeholder":"http://localhost:8000"},{"name":"api_key","type":"password","label":"API Key","required":false,"hint":"Leave blank for no-auth endpoints"},{"name":"model","type":"text","label":"Model Name","required":false,"placeholder":"mistral-7b-instruct"}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://platform.openai.com/docs/api-reference/chat',
    pricing_tier     = 'free'
WHERE provider_key = 'custom_openai_compat';

-- ─── 7. Rebuild pipeline_mode-aware unique indexes on provider_chains_v2 ──────
-- Drop old indexes that don't include pipeline_mode; recreate inclusive ones.

DROP INDEX IF EXISTS chains_v2_unique_member;
CREATE UNIQUE INDEX IF NOT EXISTS chains_v2_unique_member
    ON provider_chains_v2 (
        scope,
        COALESCE(scope_id, ''),
        COALESCE(content_mode, ''),
        COALESCE(pipeline_mode, 'production'),
        category,
        credential_id
    );

DROP INDEX IF EXISTS chains_v2_unique_position;
CREATE UNIQUE INDEX IF NOT EXISTS chains_v2_unique_position
    ON provider_chains_v2 (
        scope,
        COALESCE(scope_id, ''),
        COALESCE(content_mode, ''),
        COALESCE(pipeline_mode, 'production'),
        category,
        position
    );

DROP INDEX IF EXISTS chains_v2_resolve_idx;
CREATE INDEX IF NOT EXISTS chains_v2_resolve_idx
    ON provider_chains_v2 (scope, scope_id, content_mode, pipeline_mode, category, position);
