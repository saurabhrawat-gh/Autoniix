-- 202606171000_p1_agentic_framework_flags.sql
-- AE-P1 / Agentic Foundation: feature flags for the BaseAgent framework.
--
-- One flag per agent enables RAG-style memory recall before deciding.
-- Default FALSE everywhere so existing pipelines see zero behavioural
-- change; flip ON per-agent once you've validated recall quality.
--
-- Convention: every agent registered with AgentRegistry reads
-- ``<agent.name>.memory_recall.enabled``. Adding a new agent (e.g.
-- preventor, compliance) only needs ONE new row here.

INSERT INTO feature_flags (key, enabled, description, payload) VALUES
    (
        'brain.memory_recall.enabled',
        FALSE,
        'When TRUE, BrainAgent.recall() semantic-searches past brain_decisions '
            || 'for the same channel and weaves precedent into the reasoning '
            || 'field. Off by default; turn on per-channel by flipping the flag.',
        '{}'::jsonb
    ),
    (
        'preventor.memory_recall.enabled',
        FALSE,
        'Placeholder for the future Preventor agent (pre-execution risk check). '
            || 'Will read past preventor_decisions once that agent is built.',
        '{}'::jsonb
    ),
    (
        'compliance.memory_recall.enabled',
        FALSE,
        'Placeholder for the future Compliance agent (post-execution policy '
            || 'review). Will read past compliance_decisions once that agent is built.',
        '{}'::jsonb
    )
ON CONFLICT (key) DO NOTHING;
