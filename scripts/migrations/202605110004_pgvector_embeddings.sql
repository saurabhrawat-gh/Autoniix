-- Wave 3: pgvector — semantic search embeddings for DAM assets
-- Requires pgvector extension (already enabled via research service migration,
-- but CREATE EXTENSION IF NOT EXISTS is idempotent).

CREATE EXTENSION IF NOT EXISTS vector;

-- dam_asset_embeddings
-- Stores CLIP/SBERT/Whisper embeddings per asset per model+modality.
-- Dimension 768 covers both CLIP-L/14 and all-MiniLM-L6-v2 (padded if smaller).
CREATE TABLE IF NOT EXISTS dam_asset_embeddings (
    asset_id    BIGINT        NOT NULL REFERENCES dam_assets(id) ON DELETE CASCADE,
    model       VARCHAR(100)  NOT NULL,  -- e.g. clip-vit-l-14, all-minilm-l6-v2
    modality    VARCHAR(20)   NOT NULL DEFAULT 'visual'
                CHECK (modality IN ('visual','text','audio')),
    embedding   vector(768),
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (asset_id, model, modality)
);

-- IVFFlat index for ANN cosine similarity (100 lists ≈ good for up to ~500k rows)
CREATE INDEX IF NOT EXISTS idx_dam_embeddings_ivfflat
    ON dam_asset_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
