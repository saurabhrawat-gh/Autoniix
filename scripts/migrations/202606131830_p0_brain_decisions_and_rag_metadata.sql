-- 202606131830_p0_brain_decisions_and_rag_metadata.sql
-- AE-507 / P0 — Agentic Foundation: persistence for Brain decisions + RAG metadata.
--
-- Pure additive DDL. Two new tables, no existing table is touched.
--
--   brain_decisions    — every Brain decision logged with embedding, reasoning,
--                        directive payload, and (eventually) outcome score.
--                        Consumed by every later agentic phase epic (P1-P9).
--   rag_index_metadata — per-table archive policy + relevance-decay window
--                        used by src/llm/embeddings.semantic_search (AE-508).
--
-- All statements are idempotent.

-- pgvector is already enabled by init-db.sql / 202605110004; CREATE EXTENSION
-- IF NOT EXISTS is idempotent and safe to re-run.
CREATE EXTENSION IF NOT EXISTS vector;


-- ─────────────────────────────────────────────────────────────────────────────
-- brain_decisions
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS brain_decisions (
    id              BIGSERIAL     PRIMARY KEY,
    -- HALT | HOLD | RESUME | NUDGE | ADVISE — short opcode for routing decisions
    decision_type   VARCHAR(20)   NOT NULL,
    -- channel | video | global — same vocabulary as the Redis event envelope
    scope           VARCHAR(20)   NOT NULL,
    scope_id        VARCHAR(50),
    -- Which upstream service requested / produced the decision
    trigger_source  VARCHAR(50),
    -- Human-readable context summary the Brain assembled when reasoning
    context_summary TEXT,
    -- Free-form reasoning trace (LLM output, audit-only)
    reasoning       TEXT,
    -- Structured action payload that consumers (Temporal activities, services)
    -- can read without parsing prose. Shape is decision_type-specific.
    directive       JSONB,
    -- Populated retroactively once the decision's effect is measurable
    outcome         JSONB,
    outcome_score   SMALLINT,
    confidence      DECIMAL(3,2),
    -- text-embedding-3-small returns 1536-dim vectors
    embedding       vector(1536),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    -- NULL until the decision's effect has been verified/closed
    resolved_at     TIMESTAMPTZ
);

-- Hot path: read the latest decision for a scope
CREATE INDEX IF NOT EXISTS brain_decisions_scope_idx
    ON brain_decisions(scope, scope_id, created_at DESC);

-- Filter: open vs resolved decisions
CREATE INDEX IF NOT EXISTS brain_decisions_unresolved_idx
    ON brain_decisions(created_at DESC)
    WHERE resolved_at IS NULL;

-- Semantic recall over past decisions. ivfflat with 100 lists matches the
-- existing dam_asset_embeddings convention and is appropriate for up to
-- ~500k rows; tune later if/when we approach that scale.
CREATE INDEX IF NOT EXISTS brain_decisions_embedding_idx
    ON brain_decisions USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);


-- ─────────────────────────────────────────────────────────────────────────────
-- rag_index_metadata
-- ─────────────────────────────────────────────────────────────────────────────
-- One row per table that participates in RAG, declaring the relevance-decay
-- window and tracking the last archive job. semantic_search() reads this so a
-- single table can change its decay window without touching call-sites.

CREATE TABLE IF NOT EXISTS rag_index_metadata (
    table_name              VARCHAR(64)   PRIMARY KEY,
    -- Last time an archive job ran for this table (NULL = never)
    last_archived_at        TIMESTAMPTZ,
    -- Decay window in days; semantic_search applies exp(-age/decay) when the
    -- rag.relevance_decay.enabled feature flag is TRUE.
    relevance_decay_days    INTEGER       NOT NULL DEFAULT 365,
    -- Cached row count, refreshed by the archive job
    record_count            BIGINT        NOT NULL DEFAULT 0,
    updated_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- Seed the rows we already know we'll index. Idempotent.
INSERT INTO rag_index_metadata (table_name, relevance_decay_days) VALUES
    ('brain_decisions',     365),
    ('topic_embeddings',    180),
    ('dam_asset_embeddings', 730)
ON CONFLICT (table_name) DO NOTHING;
