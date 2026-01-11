-- Migration: Add campaign_id to user_job_status and job_notes
-- This allows these tables to be cleaned up when campaigns are deleted
-- This script is idempotent and safe to run multiple times

-- ============================================================
-- STEP 1: Add campaign_id to user_job_status
-- ============================================================

-- Add campaign_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'marts' 
        AND table_name = 'user_job_status' 
        AND column_name = 'campaign_id'
    ) THEN
        ALTER TABLE marts.user_job_status 
        ADD COLUMN campaign_id integer;
        
        -- Populate campaign_id from dim_ranking for existing records
        -- Use the most recent campaign_id for each job
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'dim_ranking') THEN
            UPDATE marts.user_job_status ujs
            SET campaign_id = (
                SELECT dr.campaign_id
                FROM marts.dim_ranking dr
                WHERE dr.jsearch_job_id = ujs.jsearch_job_id
                ORDER BY dr.ranked_at DESC NULLS LAST
                LIMIT 1
            )
            WHERE ujs.campaign_id IS NULL;
        END IF;
        
        -- If still NULL, try fact_jobs (if it exists)
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'fact_jobs') THEN
            UPDATE marts.user_job_status ujs
            SET campaign_id = (
                SELECT fj.campaign_id
                FROM marts.fact_jobs fj
                WHERE fj.jsearch_job_id = ujs.jsearch_job_id
                ORDER BY fj.dwh_load_timestamp DESC NULLS LAST
                LIMIT 1
            )
            WHERE ujs.campaign_id IS NULL;
        END IF;
        
        RAISE NOTICE 'Added campaign_id column to user_job_status and populated existing records';
    ELSE
        RAISE NOTICE 'campaign_id column already exists in user_job_status';
    END IF;
END $$;

-- Add foreign key constraint with CASCADE DELETE
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'fk_user_job_status_campaign' 
        AND conrelid = 'marts.user_job_status'::regclass
    ) THEN
        ALTER TABLE marts.user_job_status 
        ADD CONSTRAINT fk_user_job_status_campaign 
        FOREIGN KEY (campaign_id) 
        REFERENCES marts.job_campaigns(campaign_id) 
        ON DELETE CASCADE;
        
        RAISE NOTICE 'Added FK constraint fk_user_job_status_campaign';
    ELSE
        RAISE NOTICE 'FK constraint fk_user_job_status_campaign already exists';
    END IF;
END $$;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_user_job_status_campaign_id 
    ON marts.user_job_status(campaign_id);

-- ============================================================
-- STEP 2: Add campaign_id to job_notes
-- ============================================================

-- Add campaign_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'marts' 
        AND table_name = 'job_notes' 
        AND column_name = 'campaign_id'
    ) THEN
        ALTER TABLE marts.job_notes 
        ADD COLUMN campaign_id integer;
        
        -- Populate campaign_id from dim_ranking for existing records
        -- Use the most recent campaign_id for each job
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'dim_ranking') THEN
            UPDATE marts.job_notes jn
            SET campaign_id = (
                SELECT dr.campaign_id
                FROM marts.dim_ranking dr
                WHERE dr.jsearch_job_id = jn.jsearch_job_id
                ORDER BY dr.ranked_at DESC NULLS LAST
                LIMIT 1
            )
            WHERE jn.campaign_id IS NULL;
        END IF;
        
        -- If still NULL, try fact_jobs (if it exists)
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'fact_jobs') THEN
            UPDATE marts.job_notes jn
            SET campaign_id = (
                SELECT fj.campaign_id
                FROM marts.fact_jobs fj
                WHERE fj.jsearch_job_id = jn.jsearch_job_id
                ORDER BY fj.dwh_load_timestamp DESC NULLS LAST
                LIMIT 1
            )
            WHERE jn.campaign_id IS NULL;
        END IF;
        
        RAISE NOTICE 'Added campaign_id column to job_notes and populated existing records';
    ELSE
        RAISE NOTICE 'campaign_id column already exists in job_notes';
    END IF;
END $$;

-- Add foreign key constraint with CASCADE DELETE
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'fk_job_notes_campaign' 
        AND conrelid = 'marts.job_notes'::regclass
    ) THEN
        ALTER TABLE marts.job_notes 
        ADD CONSTRAINT fk_job_notes_campaign 
        FOREIGN KEY (campaign_id) 
        REFERENCES marts.job_campaigns(campaign_id) 
        ON DELETE CASCADE;
        
        RAISE NOTICE 'Added FK constraint fk_job_notes_campaign';
    ELSE
        RAISE NOTICE 'FK constraint fk_job_notes_campaign already exists';
    END IF;
END $$;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_job_notes_campaign_id 
    ON marts.job_notes(campaign_id);

-- ============================================================
-- STEP 3: Update unique constraints to include campaign_id
-- ============================================================

-- Update unique constraint for user_job_status
-- Note: The existing constraint is (user_id, jsearch_job_id)
-- We'll keep it for backwards compatibility but add campaign_id for cleanup
-- Actually, we should allow same job in different campaigns, so keep existing constraint

-- Update unique constraint for job_notes
-- Note: The existing constraint was (jsearch_job_id, user_id) but was removed in migration 15
-- We'll keep it flexible to allow multiple notes per job per user

COMMENT ON COLUMN marts.user_job_status.campaign_id IS 'Campaign ID that this job status belongs to. Used for cleanup when campaigns are deleted.';
COMMENT ON COLUMN marts.job_notes.campaign_id IS 'Campaign ID that this job note belongs to. Used for cleanup when campaigns are deleted.';
