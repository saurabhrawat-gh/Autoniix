-- 202606171900_p1_brain_reflector.sql
-- AE-P1 / Agentic Foundation: BrainReflector — periodic self-tuning loop.
--
-- The Reflector reads brain_decisions rows whose outcome has been scored
-- (outcome_score IS NOT NULL), groups them by decision_type, and detects
-- patterns where a decision class is under-performing (sustained low
-- outcome_score over a sufficiently large sample). When it finds one, it
-- writes a *proposal* into brain_flag_proposals — a write-protected
-- queue that operators (or a future auto-apply policy) review before
-- the change actually lands in feature_flags.
--
-- The Reflector itself NEVER mutates feature_flags. The proposal queue
-- is the only side-effect, and the dashboard / CLI is responsible for
-- transitioning ``status`` from ``pending`` to ``approved``/``rejected``
-- (and finally ``applied`` when the flag is updated).
--
-- Pure additive DDL. All statements idempotent.

-- ─────────────────────────────────────────────────────────────────────────────
-- brain_flag_proposals
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS brain_flag_proposals (
    id                      BIGSERIAL     PRIMARY KEY,
    -- The feature_flags.key the proposal would update on apply.
    flag_key                VARCHAR(100)  NOT NULL,
    -- Snapshot of the flag's payload at proposal time. Lets reviewers
    -- see exactly what the Reflector observed.
    current_payload         JSONB,
    -- The Reflector's suggested replacement payload. Same shape as
    -- feature_flags.payload (typically {"value": <new_number>}).
    proposed_payload        JSONB         NOT NULL,
    -- Human-readable rationale ("HALT avg outcome_score=3.1 over 12
    -- decisions in last 14d, raise consecutive_failures from 3 to 4").
    rationale               TEXT,
    -- Supporting metrics: avg_score, sample_size, decision_type, lookback_days, etc.
    supporting_evidence     JSONB,
    -- pending | approved | rejected | applied
    status                  VARCHAR(20)   NOT NULL DEFAULT 'pending',
    -- Cached sample size + avg score for fast dashboard queries.
    sample_size             INTEGER,
    observed_avg_score      NUMERIC(4,2),
    created_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    reviewed_at             TIMESTAMPTZ,
    reviewed_by             VARCHAR(100),
    review_notes            TEXT,
    CONSTRAINT brain_flag_proposals_status_chk
        CHECK (status IN ('pending', 'approved', 'rejected', 'applied'))
);

-- Hot path: dashboard "show me pending proposals".
CREATE INDEX IF NOT EXISTS brain_flag_proposals_status_idx
    ON brain_flag_proposals(status, created_at DESC);

-- Idempotence guard: at most ONE pending proposal per flag at any time.
-- The Reflector's UPSERT logic relies on this so re-running on similar
-- data updates the pending proposal in place rather than piling up
-- duplicates. Partial unique index — approved/rejected/applied rows
-- are historical and may be many.
CREATE UNIQUE INDEX IF NOT EXISTS brain_flag_proposals_pending_uidx
    ON brain_flag_proposals(flag_key)
    WHERE status = 'pending';


-- ─────────────────────────────────────────────────────────────────────────────
-- Feature flags driving the Reflector
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO feature_flags (key, enabled, description, payload) VALUES
    (
        'brain.reflector.enabled',
        FALSE,
        'Master switch for the BrainReflector loop. When FALSE the loop '
            || 'wakes up but does not query brain_decisions or write any '
            || 'proposals. Default OFF so newly-deployed environments do '
            || 'not generate noise before there is enough scored data.',
        '{}'::jsonb
    ),
    (
        'brain.reflector.min_sample_size',
        TRUE,
        'Minimum count of scored decisions of one decision_type required '
            || 'before the Reflector will emit a proposal for that '
            || 'class. Avoids over-fitting to a handful of bad outcomes.',
        '{"value": 5}'::jsonb
    ),
    (
        'brain.reflector.score_threshold',
        TRUE,
        'Average outcome_score (0-10 scale) below which a decision_type '
            || 'is considered under-performing. The Reflector only '
            || 'proposes a tweak when avg < this value.',
        '{"value": 4}'::jsonb
    ),
    (
        'brain.reflector.lookback_days',
        TRUE,
        'How far back the Reflector looks when computing per-type '
            || 'averages. Default 14 days — long enough to smooth daily '
            || 'noise, short enough to react to recent regressions.',
        '{"value": 14}'::jsonb
    ),
    (
        'brain.reflector.interval_hours',
        TRUE,
        'Hours between consecutive Reflector passes. Default 24 (once a '
            || 'day, off-peak). Operators can shorten this to accelerate '
            || 'tuning during stabilisation.',
        '{"value": 24}'::jsonb
    )
ON CONFLICT (key) DO NOTHING;
