-- 202606171500_p1_brain_llm_reasoning_flag.sql
-- AE-P1 / Agentic Foundation: enable LLM-driven reasoning in BrainAgent.decide().
--
-- When TRUE, BrainAgent calls an LLM (via the existing router) with the
-- channel signals + precedent and asks it to return a structured JSON
-- decision. On any LLM failure (timeout, schema violation, budget cap,
-- providers exhausted) the agent automatically falls back to the
-- deterministic rule-based engine, so this is safe to enable per-channel
-- with no risk of pipeline stall.
--
-- Default FALSE: the legacy rule-based path keeps running unchanged.
-- Flip ON to start exercising the LLM path on a channel.

INSERT INTO feature_flags (key, enabled, description, payload) VALUES
    (
        'brain.llm_reasoning.enabled',
        FALSE,
        'When TRUE, BrainAgent.decide() uses the LLM router to produce a '
            || 'JSON-mode decision. Falls back to the rule engine on any '
            || 'failure (parse error, schema mismatch, provider down, '
            || 'budget exceeded). Decision cost is logged to api_usage like '
            || 'every other LLM call.',
        '{}'::jsonb
    )
ON CONFLICT (key) DO NOTHING;
