-- Migration 202606020002: User-editable provider taxonomy (sections / categories / providers)
--
-- Enables non-technical creators to plug-in / plug-out their own providers:
--   1. provider_kinds       — first-class "sections" (LLM, Image, Avatar, ...)
--                             so users can add/remove whole sections with a
--                             label + icon instead of relying on a hardcoded map.
--   2. is_user_defined flags — distinguish built-in taxonomy from anything the
--                             user created, so the UI can guard built-in deletes.
--   3. is_callable flag      — a user-added marketplace provider is stored and
--                             selectable, but the runtime cannot call it until an
--                             adapter class ships. UI shows a "wiring required" hint.
--   4. seed_builtin_provider_taxonomy() — idempotent re-seed used by the
--                             "Restore defaults" action to recover built-in
--                             sections + categories after an accidental delete.
--
-- All statements idempotent (safe to re-run). Related: Providers UX overhaul.

-- ─── 1. provider_kinds (sections) ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS provider_kinds (
    kind            VARCHAR(20)   PRIMARY KEY,
    label           VARCHAR(120)  NOT NULL,
    icon            VARCHAR(16),                       -- emoji shown in the UI
    description     TEXT,
    is_user_defined BOOLEAN       NOT NULL DEFAULT FALSE,
    sort_order      SMALLINT      NOT NULL DEFAULT 100,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ─── 2. is_user_defined on provider_categories ────────────────────────────────

ALTER TABLE provider_categories
    ADD COLUMN IF NOT EXISTS is_user_defined BOOLEAN NOT NULL DEFAULT FALSE;

-- ─── 3. is_user_defined + is_callable on the marketplace catalog ───────────────

ALTER TABLE provider_marketplace_catalog
    ADD COLUMN IF NOT EXISTS is_user_defined BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_callable     BOOLEAN NOT NULL DEFAULT TRUE;

-- Anything seeded by the platform across earlier migrations is callable and
-- not user-defined; make that explicit for rows created before these columns.
UPDATE provider_marketplace_catalog
   SET is_callable = TRUE, is_user_defined = FALSE
 WHERE is_platform_seeded = TRUE;

-- ─── 4. Idempotent built-in taxonomy seed (used by "Restore defaults") ─────────

CREATE OR REPLACE FUNCTION seed_builtin_provider_taxonomy() RETURNS void AS $$
BEGIN
    -- Built-in sections (kinds). Icons mirror the dashboard's KIND_META.
    INSERT INTO provider_kinds (kind, label, icon, description, is_user_defined, sort_order) VALUES
        ('llm',           'LLM',            '🧠', 'LLMs for script, research & critique', FALSE, 10),
        ('tts',           'Text-to-Speech', '🎙️', 'Voice synthesis (TTS)',                FALSE, 20),
        ('image',         'Image',          '🖼️', 'Image generation for thumbnails & assets', FALSE, 30),
        ('search',        'Search',         '🔍', 'Web search & trend data',              FALSE, 40),
        ('stock_footage', 'Stock Footage',  '🎬', 'Stock footage & video clips',          FALSE, 50),
        ('storage',       'Storage',        '💾', 'Object storage for media files',       FALSE, 60),
        ('asset_source',  'Asset Source',   '📦', 'Stock media and asset providers',      FALSE, 70),
        ('music',         'Music',          '🎵', 'Background music & audio',             FALSE, 80),
        ('lut',           'LUTs',           '🎨', 'Color grading LUTs',                   FALSE, 90),
        ('sfx',           'SFX',            '🔊', 'Sound effects library',                FALSE, 95)
    ON CONFLICT (kind) DO UPDATE
        SET label = EXCLUDED.label,
            icon  = EXCLUDED.icon,
            description = EXCLUDED.description,
            is_user_defined = FALSE;

    -- Built-in categories (slots). Mirrors the init seed so a deleted built-in
    -- category can be recovered. Does NOT recover credentials (secrets are gone).
    INSERT INTO provider_categories (name, label, kind, description, is_user_defined) VALUES
        ('llm',           'LLM (general)',          'llm',           'Default LLM for general tasks', FALSE),
        ('llm.research',  'LLM — Research',         'llm',           'Research / fact-finding',       FALSE),
        ('llm.script',    'LLM — Script',           'llm',           'Script generation / rewrites',  FALSE),
        ('llm.factcheck', 'LLM — Fact-check',       'llm',           'Fact verification',             FALSE),
        ('llm.qc',        'LLM — Quality Critique', 'llm',           'Output critique / scoring',     FALSE),
        ('llm.vision',    'LLM — Vision',           'llm',           'Image analysis (CTR / scene)',  FALSE),
        ('llm.ideation',  'LLM — Ideation',         'llm',           'Topic + hook ideation',         FALSE),
        ('llm.hook',      'LLM — Hook',             'llm',           'Hook writer',                   FALSE),
        ('llm.direction', 'LLM — Direction',        'llm',           'Visual direction generation',   FALSE),
        ('llm.emotion',   'LLM — Emotion',          'llm',           'Emotion mapping for TTS',       FALSE),
        ('tts',           'Text-to-Speech',         'tts',           'Voice synthesis',               FALSE),
        ('image',         'Image generation',       'image',         'AI image generation',           FALSE),
        ('search',        'Web search',             'search',        'Real-time web search',          FALSE),
        ('storage',       'Object storage',         'storage',       'Render artifacts + assets',     FALSE),
        ('stock_footage', 'Stock footage',          'stock_footage', 'Stock video clips',             FALSE),
        ('asset_sources', 'Asset Sources',          'asset_source',  'Stock media and asset providers', FALSE),
        ('music',         'Background music',       'music',         'Production music',              FALSE),
        ('lut',           'Color grading LUTs',     'lut',           'LUTs library',                  FALSE),
        ('sfx',           'Sound effects',          'sfx',           'SFX library',                   FALSE)
    ON CONFLICT (name) DO UPDATE
        SET label = EXCLUDED.label, kind = EXCLUDED.kind;
END;
$$ LANGUAGE plpgsql;

-- Run once now so existing databases get the provider_kinds rows populated.
SELECT seed_builtin_provider_taxonomy();
