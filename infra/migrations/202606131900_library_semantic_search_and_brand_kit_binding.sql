-- 202606131900_library_semantic_search_and_brand_kit_binding.sql
-- Library Sprint: AE-356 (semantic search) + AE-357 (brand kit binding).
--
-- AE-356:
--   dam_text_embeddings  — vector(1536) computed by the media_jobs `embed`
--     handler from src/llm/embeddings.py. Separate from dam_asset_embeddings
--     (vector(768) — reserved for future CLIP/SBERT pipelines so the two
--     dimensionalities don't collide on a single column).
--
-- AE-357:
--   channels.brand_kit_id — optional FK to the brand kit a channel's
--     production pipeline should pull logo/palette/fonts from. NULL means
--     "fall back to channel.brand_config" (legacy path), preserving current
--     behaviour for every existing channel until an operator explicitly
--     binds a kit.
--
-- All statements idempotent. No existing table is altered destructively.

CREATE EXTENSION IF NOT EXISTS vector;


-- ─────────────────────────────────────────────────────────────────────────────
-- AE-356: dam_text_embeddings
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dam_text_embeddings (
    asset_id    BIGINT       PRIMARY KEY REFERENCES dam_assets(id) ON DELETE CASCADE,
    embedding   vector(1536) NOT NULL,
    source_text TEXT,
    model       VARCHAR(100) NOT NULL DEFAULT 'text-embedding-3-small',
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dam_text_embeddings_ivfflat
    ON dam_text_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);


-- ─────────────────────────────────────────────────────────────────────────────
-- AE-357: channels.brand_kit_id
-- ─────────────────────────────────────────────────────────────────────────────
-- ALTER TABLE … ADD COLUMN IF NOT EXISTS is idempotent and never rewrites
-- existing rows (the column starts NULL on every existing row, which is
-- precisely the legacy fall-back semantic we want).

ALTER TABLE channels
    ADD COLUMN IF NOT EXISTS brand_kit_id BIGINT REFERENCES dam_brand_kits(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_channels_brand_kit
    ON channels(brand_kit_id) WHERE brand_kit_id IS NOT NULL;
