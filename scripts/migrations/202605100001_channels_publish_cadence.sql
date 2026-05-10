-- 202605100001_channels_publish_cadence.sql
-- Adds the publish_cadence column referenced by the v2 channels list query.
-- The legacy table has `posting_frequency` (e.g. 'daily') which we copy over
-- as a default so existing channels don't show NULL in the dashboard.

ALTER TABLE channels
    ADD COLUMN IF NOT EXISTS publish_cadence VARCHAR(40);

UPDATE channels
   SET publish_cadence = posting_frequency
 WHERE publish_cadence IS NULL
   AND posting_frequency IS NOT NULL;
