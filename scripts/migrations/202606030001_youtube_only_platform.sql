-- AE-219: Enforce YouTube-only platform constraint on channels table
-- Backfill nulls / non-youtube values first, then add CHECK constraint.
-- Safe to run multiple times (idempotent).

BEGIN;

-- 1. Backfill any channels that have NULL or non-youtube platform
UPDATE channels
   SET platform = 'youtube'
 WHERE platform IS NULL OR platform != 'youtube';

-- 2. Add CHECK constraint (IF NOT EXISTS guard via DO block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'channels_platform_youtube_only'
           AND conrelid = 'channels'::regclass
    ) THEN
        ALTER TABLE channels
            ADD CONSTRAINT channels_platform_youtube_only
            CHECK (platform = 'youtube');
    END IF;
END $$;

COMMIT;
