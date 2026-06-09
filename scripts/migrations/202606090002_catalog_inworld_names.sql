-- Migration 202606090002: Inworld AI + provider display name cleanup
--
-- Changes:
--   1. Insert Inworld AI into the tts category
--   2. Clean up display names that embed model names (e.g. "OpenAI (GPT-4o)" → "OpenAI")
--
-- All statements idempotent (safe to re-run).

-- ─── 1. Inworld AI (TTS) ──────────────────────────────────────────────────────

INSERT INTO provider_marketplace_catalog
    (provider_key, display_name, category, description, mode, capabilities, cost_unit, has_free_tier, featured, sort_order)
VALUES
    ('inworld', 'Inworld AI', 'tts',
     'Inworld AI — high-quality TTS with character voices and voice cloning.',
     'byok', ARRAY['tts-standard','voice-clone'], '$0.001/char', false, true, 35)
ON CONFLICT (provider_key) DO NOTHING;

UPDATE provider_marketplace_catalog SET
    config_schema    = '[{"name":"api_key","type":"password","label":"API Key","required":true,"hint":"Get from inworld.ai developer portal"},{"name":"voice_name","type":"text","label":"Voice Name","required":false,"placeholder":"Leave blank for default voice"}]'::jsonb,
    supported_models = '[]'::jsonb,
    docs_url         = 'https://docs.inworld.ai/docs/tutorial-api/overview',
    pricing_tier     = 'paid',
    is_callable      = TRUE
WHERE provider_key = 'inworld';

-- ─── 2. Display name cleanup ──────────────────────────────────────────────────
-- Remove embedded model/qualifier suffixes so the marketplace shows clean brand names.

UPDATE provider_marketplace_catalog SET display_name = 'OpenAI'    WHERE provider_key = 'openai'    AND display_name = 'OpenAI (GPT-4o)';
UPDATE provider_marketplace_catalog SET display_name = 'Anthropic'  WHERE provider_key = 'anthropic'  AND display_name = 'Anthropic (Claude)';
UPDATE provider_marketplace_catalog SET display_name = 'Groq'       WHERE provider_key = 'groq'       AND display_name = 'Groq (Llama-3)';
UPDATE provider_marketplace_catalog SET display_name = 'Ollama'     WHERE provider_key = 'ollama'     AND display_name = 'Ollama (local)';
