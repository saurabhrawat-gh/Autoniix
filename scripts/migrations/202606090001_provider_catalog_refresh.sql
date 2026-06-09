-- Migration 202606090001: Provider catalog refresh
--
-- Changes:
--   1. Update LLM model lists to match expanded PRICING dicts in provider adapters
--   2. Insert missing providers: deepseek, cartesia, unsplash, kling
--   3. Remove stale / unused providers: kimi, glm, groq, ollama, perplexity, serper, tavily,
--      fal_ai, envato, custom_openai_compat — marked is_callable=FALSE so keys can still
--      be saved but the pipeline will never call them.
--
-- All statements idempotent (safe to re-run).

-- ─── 1. Update LLM model lists ────────────────────────────────────────────────

-- openai — expanded model list
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Starts with sk-"},{"name":"model","type":"select","label":"Default Model","required":false,"options":["gpt-4o","gpt-4o-mini","gpt-4-turbo","gpt-4-turbo-preview","gpt-3.5-turbo","gpt-3.5-turbo-16k","o1-preview","o1-mini"]}]'::jsonb,
    supported_models = '["gpt-4o","gpt-4o-mini","gpt-4-turbo","gpt-4-turbo-preview","gpt-3.5-turbo","gpt-3.5-turbo-16k","o1-preview","o1-mini"]'::jsonb,
    docs_url         = 'https://platform.openai.com/docs/api-reference',
    pricing_tier     = 'paid'
WHERE provider_key = 'openai';

-- anthropic (claude) — expanded model list, removed claude-sonnet-4 (non-standard name)
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Starts with sk-ant-"},{"name":"model","type":"select","label":"Default Model","required":false,"options":["claude-3-5-sonnet-20241022","claude-3-5-sonnet-20240620","claude-3-5-haiku-20241022","claude-3-opus-20240229","claude-3-sonnet-20240229","claude-3-haiku-20240307"]}]'::jsonb,
    supported_models = '["claude-3-5-sonnet-20241022","claude-3-5-sonnet-20240620","claude-3-5-haiku-20241022","claude-3-opus-20240229","claude-3-sonnet-20240229","claude-3-haiku-20240307"]'::jsonb,
    docs_url         = 'https://docs.anthropic.com/en/api',
    pricing_tier     = 'paid'
WHERE provider_key IN ('anthropic', 'claude');

-- gemini — expanded model list
UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true},{"name":"model","type":"select","label":"Default Model","required":false,"options":["gemini-2.5-flash","gemini-2.5-flash-exp","gemini-2.0-flash","gemini-2.0-flash-exp","gemini-1.5-pro","gemini-1.5-pro-002","gemini-1.5-flash","gemini-1.5-flash-002"]}]'::jsonb,
    supported_models = '["gemini-2.5-flash","gemini-2.5-flash-exp","gemini-2.0-flash","gemini-2.0-flash-exp","gemini-1.5-pro","gemini-1.5-pro-002","gemini-1.5-flash","gemini-1.5-flash-002"]'::jsonb,
    docs_url         = 'https://ai.google.dev/api',
    pricing_tier     = 'paid'
WHERE provider_key = 'gemini';

-- ─── 2. Insert + update missing providers ─────────────────────────────────────

-- deepseek
INSERT INTO provider_marketplace_catalog
    (provider_key, display_name, category, description, mode, capabilities, cost_unit, has_free_tier, featured, sort_order)
VALUES
    ('deepseek', 'DeepSeek', 'llm', 'DeepSeek V3 (deepseek-chat) and R1 reasoning model — cheapest general-purpose LLM.', 'byok', ARRAY['text-gen','function-call','reasoning'], '$0.27/1M input', false, true, 45)
ON CONFLICT (provider_key) DO NOTHING;

UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Get from platform.deepseek.com"},{"name":"model","type":"select","label":"Default Model","required":false,"options":["deepseek-chat","deepseek-reasoner"]}]'::jsonb,
    supported_models = '["deepseek-chat","deepseek-reasoner"]'::jsonb,
    docs_url         = 'https://platform.deepseek.com/api-docs',
    pricing_tier     = 'paid',
    is_callable      = TRUE
WHERE provider_key = 'deepseek';

-- cartesia
INSERT INTO provider_marketplace_catalog
    (provider_key, display_name, category, description, mode, capabilities, cost_unit, has_free_tier, featured, sort_order)
VALUES
    ('cartesia', 'Cartesia', 'tts', 'Cartesia Sonic — ultra-low latency TTS with voice cloning support.', 'byok', ARRAY['speech-synthesis','voice-clone','streaming'], '$0.25/1K chars', false, true, 25)
ON CONFLICT (provider_key) DO NOTHING;

UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true},{"name":"voice_id","type":"text","label":"Voice ID","required":false,"placeholder":"Leave blank for default voice"}]'::jsonb,
    supported_models = '["sonic-english","sonic-multilingual"]'::jsonb,
    docs_url         = 'https://docs.cartesia.ai',
    pricing_tier     = 'paid',
    is_callable      = TRUE
WHERE provider_key = 'cartesia';

-- unsplash
INSERT INTO provider_marketplace_catalog
    (provider_key, display_name, category, description, mode, capabilities, cost_unit, has_free_tier, featured, sort_order)
VALUES
    ('unsplash', 'Unsplash', 'stock_footage', 'High-quality free stock photos from Unsplash.', 'byok', ARRAY['image-search','stock-images'], 'Free (50 req/hr)', true, true, 20)
ON CONFLICT (provider_key) DO NOTHING;

UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"Access Key","required":true,"hint":"Get from unsplash.com/developers"}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://unsplash.com/documentation',
    pricing_tier     = 'free',
    is_callable      = TRUE
WHERE provider_key = 'unsplash';

-- kling AI
INSERT INTO provider_marketplace_catalog
    (provider_key, display_name, category, description, mode, capabilities, cost_unit, has_free_tier, featured, sort_order)
VALUES
    ('kling', 'Kling AI', 'stock_footage', 'AI-generated video clips from Kling AI — text-to-video generation.', 'byok', ARRAY['video-generation','text-to-video'], '~$0.05/video', false, true, 40)
ON CONFLICT (provider_key) DO NOTHING;

UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Get from klingai.com"}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://klingai.com/docs',
    pricing_tier     = 'paid',
    is_callable      = TRUE
WHERE provider_key = 'kling';

-- stability AI catalog entry (already has UPDATE above but may be missing the INSERT)
INSERT INTO provider_marketplace_catalog
    (provider_key, display_name, category, description, mode, capabilities, cost_unit, has_free_tier, featured, sort_order)
VALUES
    ('stability', 'Stability AI', 'image', 'Stable Diffusion XL image generation — high quality, cost-effective.', 'byok', ARRAY['image-gen','text-to-image'], '$0.04/image', false, true, 20)
ON CONFLICT (provider_key) DO NOTHING;

UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Get from platform.stability.ai"},{"name":"size","type":"select","label":"Image Size","required":false,"options":["1024x1024","1152x896","896x1152","1216x832","832x1216"]}]'::jsonb,
    supported_models = '["stable-diffusion-xl-1024-v1-0","stable-diffusion-3","stable-image-ultra"]'::jsonb,
    docs_url         = 'https://platform.stability.ai/docs/api-reference',
    pricing_tier     = 'paid',
    is_callable      = TRUE
WHERE provider_key = 'stability';

-- ─── 3. Remove stale / unused providers (mark is_callable=FALSE) ─────────────

UPDATE provider_marketplace_catalog
   SET is_callable = FALSE
 WHERE provider_key IN ('kimi', 'glm', 'groq', 'ollama', 'perplexity', 'serper', 'tavily',
                         'fal_ai', 'envato', 'custom_openai_compat');
