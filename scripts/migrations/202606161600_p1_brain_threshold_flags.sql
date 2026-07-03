-- 202606161600_p1_brain_threshold_flags.sql
-- AE-P1 / Brain Service: seed threshold + resolver feature flags.
--
-- All thresholds are SAFETY-ON defaults — conservative values that will
-- only fire on clearly broken channels. Operators can tune via the
-- feature_flags table without deploying.
--
-- Idempotent: ON CONFLICT DO NOTHING.

INSERT INTO feature_flags (key, enabled, description, payload) VALUES

    -- ── Halt thresholds ───────────────────────────────────────────────────
    (
        'brain.threshold.halt.consecutive_failures',
        TRUE,
        'Number of consecutive failed videos that triggers a HALT decision. '
            || 'Default 3 — conservative to avoid false positives on new channels.',
        '{"value": 3}'::jsonb
    ),
    (
        'brain.threshold.halt.min_quality_score',
        TRUE,
        'Average composite score below which the Brain issues a HALT. '
            || 'Requires >= 3 recent videos. Default 5.0 (out of 10).',
        '{"value": 5.0}'::jsonb
    ),

    -- ── Hold thresholds ───────────────────────────────────────────────────
    (
        'brain.threshold.hold.cost_spike_factor',
        TRUE,
        'If the latest video cost exceeds this multiple of the rolling average, '
            || 'issue a HOLD. Default 3.0 (3x spike).',
        '{"value": 3.0}'::jsonb
    ),
    (
        'brain.threshold.hold.budget_pct_remaining',
        TRUE,
        'Fraction of daily budget remaining below which a HOLD is issued. '
            || 'Default 0.05 (5%). Set to 0 to disable.',
        '{"value": 0.05}'::jsonb
    ),

    -- ── Nudge thresholds ──────────────────────────────────────────────────
    (
        'brain.threshold.nudge.avg_quality_score',
        TRUE,
        'Average composite score below which the Brain issues a NUDGE '
            || '(soft redirect). Requires >= 5 recent videos. Default 7.0.',
        '{"value": 7.0}'::jsonb
    ),

    -- ── Resolver ─────────────────────────────────────────────────────────
    (
        'brain.resolver.stale_hard_days',
        TRUE,
        'Days after which unresolved HALT/HOLD decisions are auto-resolved '
            || 'as stale. Default 7.',
        '{"value": 7}'::jsonb
    ),
    (
        'brain.resolver.stale_soft_days',
        TRUE,
        'Days after which unresolved ADVISE/NUDGE/RESUME decisions are '
            || 'auto-resolved. Default 1.',
        '{"value": 1}'::jsonb
    )

ON CONFLICT (key) DO NOTHING;
