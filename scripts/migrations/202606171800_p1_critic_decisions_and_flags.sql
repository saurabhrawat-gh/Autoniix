-- 202606171800_p1_critic_decisions_and_flags.sql
-- AE-P1 / Agentic Foundation: Critic Agent — independent safety reviewer
-- that vets every peer agent's decision before side-effects fire.
--
-- Two new artefacts:
--   1. ``critic_decisions`` — append-only log of every verdict (APPROVE,
--      VETO, MODIFY) so the audit trail is complete. Embedding column
--      mirrors brain_decisions so the Critic can recall its own past
--      verdicts via the existing AgentMemory / semantic_search path.
--   2. Two feature flags:
--        * ``critic.enabled``              — global kill switch
--        * ``brain.critic_review.enabled`` — opt-in for Brain decisions
--      Both default FALSE so existing behaviour is preserved. Adding a
--      new peer agent to critique is just one extra row here.
--
-- Pure additive DDL. No existing table is touched. All statements are
-- idempotent.

CREATE EXTENSION IF NOT EXISTS vector;


-- ─────────────────────────────────────────────────────────────────────────────
-- critic_decisions
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS critic_decisions (
    id                      BIGSERIAL     PRIMARY KEY,
    -- The peer decision being reviewed. Foreign key is intentionally
    -- soft (no FK constraint) because peers may live in different
    -- decision tables (brain_decisions today, preventor_decisions later).
    original_decision_id    BIGINT,
    -- Name of the peer agent (e.g. "brain"). Lets us aggregate VETO
    -- rates per agent for the dashboard.
    original_agent          VARCHAR(50)   NOT NULL,
    -- The peer's decision_type at review time — denormalised so analytics
    -- queries don't need to join across N peer tables.
    reviewed_decision_type  VARCHAR(20),
    -- APPROVE | VETO | MODIFY
    verdict                 VARCHAR(10)   NOT NULL,
    -- Free-form reasoning trace from the Critic.
    reasoning               TEXT,
    confidence              DECIMAL(3,2),
    -- Populated only when verdict = MODIFY. Same shape as the peer's
    -- directive jsonb so the consumer can swap them transparently.
    modified_directive      JSONB,
    modified_decision_type  VARCHAR(20),
    -- Scope mirror so we can index by channel/video without a join.
    scope                   VARCHAR(20),
    scope_id                VARCHAR(50),
    -- Did the Critic use the LLM path or the rule-based fallback?
    reasoning_path          VARCHAR(20),
    -- text-embedding-3-small returns 1536-dim vectors
    embedding               vector(1536),
    created_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT critic_decisions_verdict_chk
        CHECK (verdict IN ('APPROVE', 'VETO', 'MODIFY'))
);

-- Hot path: read recent verdicts for one agent (dashboard VETO rate).
CREATE INDEX IF NOT EXISTS critic_decisions_agent_idx
    ON critic_decisions(original_agent, created_at DESC);

-- Filter: lookup by reviewed decision id (debug, drill-down).
CREATE INDEX IF NOT EXISTS critic_decisions_original_idx
    ON critic_decisions(original_decision_id)
    WHERE original_decision_id IS NOT NULL;

-- Semantic recall over past verdicts. Same ivfflat / 100 lists convention
-- as brain_decisions for consistent tuning behaviour.
CREATE INDEX IF NOT EXISTS critic_decisions_embedding_idx
    ON critic_decisions USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);


-- ─────────────────────────────────────────────────────────────────────────────
-- rag_index_metadata: register critic_decisions as an indexed table so
-- semantic_search() applies the standard relevance-decay window.
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO rag_index_metadata (table_name, relevance_decay_days) VALUES
    ('critic_decisions', 365)
ON CONFLICT (table_name) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- Feature flags
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO feature_flags (key, enabled, description, payload) VALUES
    (
        'critic.enabled',
        FALSE,
        'Global kill switch for the Critic Agent. When FALSE, the '
            || 'critique phase in BaseAgent.run() is skipped entirely '
            || 'regardless of any per-agent flag. Flip this ON first, '
            || 'then turn on per-agent critic_review flags individually.',
        '{}'::jsonb
    ),
    (
        'brain.critic_review.enabled',
        FALSE,
        'Per-agent opt-in: when TRUE (and critic.enabled is also TRUE), '
            || 'every BrainAgent decision is reviewed by the Critic '
            || 'between decide() and act(). VETO drops the decision and '
            || 'dead-letters it; MODIFY substitutes the Critic''s '
            || 'replacement directive; APPROVE passes through unchanged.',
        '{}'::jsonb
    ),
    (
        'critic.llm_reasoning.enabled',
        FALSE,
        'When TRUE, CriticAgent uses the LLM router for verdicts. '
            || 'Falls back to deterministic rules on any LLM failure '
            || '(parse error, schema mismatch, providers exhausted, '
            || 'budget cap), so the critique phase never stalls.',
        '{}'::jsonb
    ),
    (
        'critic.memory_recall.enabled',
        FALSE,
        'When TRUE, CriticAgent semantic-searches past critic_decisions '
            || 'for similar peer decisions and weaves precedent into '
            || 'its reasoning before voting. Off by default; enable per '
            || 'environment after seed verdicts accumulate.',
        '{}'::jsonb
    )
ON CONFLICT (key) DO NOTHING;
