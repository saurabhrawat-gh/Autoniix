-- ============================================================
-- 202606161700_p1_brain_budget_columns.sql
-- AE-P1 / Brain Service — budget tracking schema
--
-- Adds:
--   • channels.daily_budget_limit  — optional per-channel spend cap (USD/day)
--   • api_usage table              — per-request cost ledger for all LLM/API calls
--
-- Both are referenced by the Brain analyser's _fetch_budget() to power the
-- HOLD-on-budget-exhaustion decision rule.
-- ============================================================

-- 1. Budget cap on channels (NULL = no cap; 0 = effectively no cap)
ALTER TABLE channels
    ADD COLUMN IF NOT EXISTS daily_budget_limit NUMERIC(12,4) DEFAULT NULL;

-- 2. api_usage — lightweight cost ledger
--    One row per LLM / external API call.
--    channel_id is nullable: some calls (e.g. RAG ingestion) aren't channel-scoped.
CREATE TABLE IF NOT EXISTS api_usage (
    id              BIGSERIAL       PRIMARY KEY,
    channel_id      VARCHAR(20)     REFERENCES channels(channel_id) ON DELETE SET NULL,
    service         VARCHAR(60)     NOT NULL DEFAULT 'unknown',
    model           VARCHAR(120),
    input_tokens    INTEGER         NOT NULL DEFAULT 0,
    output_tokens   INTEGER         NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(14,6)   NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_usage_channel_date_idx
    ON api_usage (channel_id, created_at DESC)
    WHERE channel_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS api_usage_created_idx
    ON api_usage (created_at DESC);
