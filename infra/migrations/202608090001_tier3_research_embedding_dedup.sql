-- Migration: Tier 3 Research Service - Embedding Deduplication
-- Date: 2026-08-09
-- Purpose: Add unique constraint on topic_embeddings to prevent duplicate embeddings

-- Add unique constraint on (content_id, text_type) if it doesn't exist
-- This allows ON CONFLICT DO UPDATE in store_topic_embedding
DO $$
BEGIN
    -- Check if the constraint already exists
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'topic_embeddings_content_id_text_type_key'
    ) THEN
        -- Add the unique constraint
        ALTER TABLE topic_embeddings
        ADD CONSTRAINT topic_embeddings_content_id_text_type_key
        UNIQUE (content_id, text_type);
        
        RAISE NOTICE 'Added unique constraint topic_embeddings_content_id_text_type_key';
    ELSE
        RAISE NOTICE 'Unique constraint topic_embeddings_content_id_text_type_key already exists';
    END IF;
END $$;

-- Add updated_at column if it doesn't exist (for ON CONFLICT DO UPDATE)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_embeddings'
        AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE topic_embeddings
        ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
        
        RAISE NOTICE 'Added updated_at column to topic_embeddings';
    ELSE
        RAISE NOTICE 'Column updated_at already exists in topic_embeddings';
    END IF;
END $$;

-- Create index on updated_at for efficient queries
CREATE INDEX IF NOT EXISTS idx_topic_embeddings_updated_at
ON topic_embeddings (updated_at DESC);

COMMENT ON CONSTRAINT topic_embeddings_content_id_text_type_key ON topic_embeddings IS
'Tier 3: Prevents duplicate embeddings for the same content_id + text_type combination';
