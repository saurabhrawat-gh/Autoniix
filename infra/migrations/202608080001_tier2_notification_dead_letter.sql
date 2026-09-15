-- Tier 2 orchestration: notification dispatcher hardening
--
-- Adds:
--   1. `dead_letter` as a permitted status on notification_deliveries
--   2. `next_attempt_at` timestamp column for exponential backoff scheduling
--   3. Index on (status, next_attempt_at) for efficient claim
--   4. `dead_letter_reason` column for post-mortem visibility
--
-- Backwards-compatible: existing rows get NULL next_attempt_at, which the
-- dispatcher treats as "eligible now" (matches previous behavior).

ALTER TABLE notification_deliveries
    DROP CONSTRAINT IF EXISTS deliveries_status_chk;

ALTER TABLE notification_deliveries
    ADD CONSTRAINT deliveries_status_chk
    CHECK (status IN ('queued', 'sent', 'failed', 'dropped', 'dead_letter'));

ALTER TABLE notification_deliveries
    ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ;

ALTER TABLE notification_deliveries
    ADD COLUMN IF NOT EXISTS dead_letter_reason TEXT;

CREATE INDEX IF NOT EXISTS deliveries_next_attempt_idx
    ON notification_deliveries(status, next_attempt_at)
    WHERE status IN ('queued', 'failed');
