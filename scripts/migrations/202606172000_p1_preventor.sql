-- 202606172000_p1_preventor.sql
-- AE-P1 / Agentic Foundation: Preventor Agent — pre-execution risk gate.
--
-- Sits in front of any expensive workflow (video production, scheduled
-- experiment, …). The workflow calls ``PreventorAgent.run(context)``
-- BEFORE doing the work. The Preventor combines current channel
-- signals (HALT status, budget remaining, recent failure rate) with
-- its own past decisions and returns one of:
--
--   ALLOW : proceed normally
--   WARN  : proceed but flag for human review
--   HOLD  : pause the planned action, mark needs_review
--   VETO  : refuse outright; the caller MUST abort
--
-- The Brain reacts AFTER the fact (see brain_decisions). The Preventor
-- catches predictable failures BEFORE money is spent. The two are
-- complementary — together they form the safety pair the architecture
-- review called out.
--
-- Pure additive DDL. Idempotent.

CREATE EXTENSION IF NOT EXISTS vector;


-- ─────────────────────────────────────────────────────────────────────────────
-- preventor_decisions
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS preventor_decisions (
    id                  BIGSERIAL     PRIMARY KEY,
    decision_type       VARCHAR(20)   NOT NULL,
    scope               VARCHAR(20)   NOT NULL,
    scope_id            VARCHAR(100)  NOT NULL,
    -- The action the Preventor was asked to gate. Free-form so future
    -- callers can pass new action names without a schema change.
    planned_action      VARCHAR(50)   NOT NULL,
    -- Directive emitted on BRAIN_PREVENTOR_RISK. Same envelope shape
    -- used by other agents (action, channel_id, content_id, reason, …).
    directive           JSONB         NOT NULL,
    reasoning           TEXT,
    confidence          DECIMAL(3,2),
    -- Snapshot of the risk signals at decision time. Lets reviewers
    -- replay the decision without joining N source tables.
    risk_signals        JSONB,
    -- Set when the predicted risk was either avoided (planned_action
    -- never re-attempted) or materialised (planned_action was retried
    -- and succeeded/failed). The OutcomeScorer can extend later.
    resolved_at         TIMESTAMPTZ,
    outcome             JSONB,
    outcome_score       DECIMAL(3,1),
    -- text-embedding-3-small returns 1536-dim vectors.
    embedding           vector(1536),
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT preventor_decisions_type_chk
        CHECK (decision_type IN ('ALLOW', 'WARN', 'HOLD', 'VETO'))
);

-- Hot path: dashboard "show me recent decisions for this channel".
CREATE INDEX IF NOT EXISTS preventor_decisions_scope_idx
    ON preventor_decisions(scope, scope_id, created_at DESC);

-- Filter: unresolved blocking decisions (HOLD/VETO).
CREATE INDEX IF NOT EXISTS preventor_decisions_unresolved_idx
    ON preventor_decisions(decision_type, resolved_at)
    WHERE resolved_at IS NULL
      AND decision_type IN ('HOLD', 'VETO');

-- Semantic recall over past Preventor decisions.
CREATE INDEX IF NOT EXISTS preventor_decisions_embedding_idx
    ON preventor_decisions USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);


-- ─────────────────────────────────────────────────────────────────────────────
-- rag_index_metadata: register preventor_decisions so semantic_search()
-- applies the standard relevance-decay window.
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO rag_index_metadata (table_name, relevance_decay_days) VALUES
    ('preventor_decisions', 180)
ON CONFLICT (table_name) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- Feature flags
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO feature_flags (key, enabled, description, payload) VALUES
    (
        'preventor.enabled',
        FALSE,
        'Master switch. When FALSE, PreventorAgent.run() returns None '
            || 'immediately and never publishes a directive or persists '
            || 'a row. Callers treat None as ALLOW so opt-in is purely '
            || 'additive.',
        '{}'::jsonb
    ),
    (
        'preventor.critic_review.enabled',
        FALSE,
        'Per-peer opt-in for Critic review of Preventor decisions. '
            || 'When TRUE (and critic.enabled is also TRUE) every '
            || 'PreventorAgent decision is reviewed by the Critic '
            || 'before act() fires.',
        '{}'::jsonb
    ),
    (
        'preventor.threshold.veto.consecutive_failures',
        TRUE,
        'Consecutive failure count at or above which the Preventor '
            || 'VETOs (refuses to proceed). Default 5 — conservative '
            || 'so this only fires on clearly broken channels.',
        '{"value": 5}'::jsonb
    ),
    (
        'preventor.threshold.hold.budget_pct_remaining',
        TRUE,
        'Fraction of daily budget below which the Preventor issues a '
            || 'HOLD instead of allowing. Default 0.05 (5%). Set to 0 '
            || 'to disable budget-based HOLDs.',
        '{"value": 0.05}'::jsonb
    ),
    (
        'preventor.threshold.warn.min_quality_score',
        TRUE,
        'Recent average composite score below which the Preventor '
            || 'issues a WARN (proceed but flag). Requires >= 3 '
            || 'recent videos. Default 6.5.',
        '{"value": 6.5}'::jsonb
    ),
    (
        'preventor.veto_when_channel_halted',
        TRUE,
        'When TRUE, the Preventor automatically VETOs any planned '
            || 'action on a channel that has an unresolved HALT in '
            || 'brain_decisions. Default TRUE — strong safety floor.',
        '{}'::jsonb
    )
ON CONFLICT (key) DO NOTHING;
