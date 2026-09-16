-- 202606171930_p1_outcome_scorer.sql
-- AE-P1 / Agentic Foundation: OutcomeScorer feature flags.
--
-- The scorer populates ``brain_decisions.outcome_score`` (and the free-
-- form ``outcome`` jsonb) for resolved decisions whose downstream
-- effects can be measured against the ``videos`` table. The Reflector
-- (202606171900_p1_brain_reflector.sql) reads this column — without
-- the scorer it has nothing to mine.
--
-- No new tables: ``outcome_score`` + ``outcome`` are already on
-- ``brain_decisions`` (added in 202606131830). This migration only
-- seeds the flags driving the loop.
--
-- All flags are SAFE-OFF or SAFE-CONSERVATIVE defaults so a freshly-
-- deployed environment behaves identically to today.

INSERT INTO feature_flags (key, enabled, description, payload) VALUES
    (
        'brain.scorer.enabled',
        FALSE,
        'Master switch for the OutcomeScorer loop. When FALSE the loop '
            || 'wakes up but writes nothing. Flip ON once enough '
            || 'resolved decisions exist for scoring to be meaningful.',
        '{}'::jsonb
    ),
    (
        'brain.scorer.interval_hours',
        TRUE,
        'Hours between consecutive OutcomeScorer passes. Default 6. '
            || 'The scorer is cheap (one indexed query + per-row arithmetic) '
            || 'so this can be lowered safely if faster feedback is desired.',
        '{"value": 6}'::jsonb
    ),
    (
        'brain.scorer.measurement_window_days',
        TRUE,
        'Days of post-resolved_at data the scorer waits for before '
            || 'committing an outcome. Shorter window = faster Reflector '
            || 'feedback but noisier scores. Default 7.',
        '{"value": 7}'::jsonb
    ),
    (
        'brain.scorer.min_videos_for_signal',
        TRUE,
        'Minimum number of delivered videos in the measurement window '
            || 'required before HALT/NUDGE/RESUME decisions can be scored. '
            || 'Below this threshold the scorer skips the row and tries '
            || 'again on the next pass. Default 3.',
        '{"value": 3}'::jsonb
    ),
    (
        'brain.scorer.batch_size',
        TRUE,
        'Maximum decisions scored per pass. Caps memory + DB load on '
            || 'first-run backfills. Default 200.',
        '{"value": 200}'::jsonb
    )
ON CONFLICT (key) DO NOTHING;
