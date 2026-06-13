-- 202606131831_p0_brain_feature_flags.sql
-- AE-510 / P0 — Agentic Foundation: seed the three feature flags every later
-- phase reads.
--
-- All flags are SAFETY-ON by default so adding them changes no existing
-- behaviour. They become meaningful only when the Brain (P2) and later
-- agentic services start writing decisions / events.
--
-- The integer ``temporal.signal_check_interval_seconds`` is stored inside the
-- ``payload`` JSONB column (``{"value": 30}``) because ``feature_flags`` is a
-- boolean-first table; we re-use it instead of introducing a parallel
-- config table.

INSERT INTO feature_flags (key, enabled, description, payload) VALUES
    (
        'brain.advisory_mode',
        TRUE,
        'Brain decisions are advisory recommendations requiring human approval. '
            || 'Safety-on default for the first 90 days; flip to FALSE only when '
            || 'the Brain has demonstrated decision quality.',
        '{}'::jsonb
    ),
    (
        'rag.relevance_decay.enabled',
        FALSE,
        'When TRUE, semantic_search applies time-decay scoring '
            || '(score = cos_sim * exp(-age_days / relevance_decay_days)) per '
            || 'rag_index_metadata.',
        '{}'::jsonb
    ),
    (
        'temporal.signal_check_interval_seconds',
        TRUE,
        'How often VideoProductionWorkflow polls brain_decisions for new '
            || 'directives. Value carried in payload.value (integer seconds).',
        '{"value": 30}'::jsonb
    )
ON CONFLICT (key) DO NOTHING;
