-- Migration: Fix campaign_id uniqueness and implement cascade deletion
-- This script ensures campaign IDs are unique and cleans up orphaned data

-- Step 1: Clean up orphaned data from deleted campaigns
-- Only delete if tables exist (fact_jobs is created by dbt, might not exist yet)

-- Delete rankings for non-existent campaigns
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'dim_ranking') THEN
        DELETE FROM marts.dim_ranking dr
        WHERE NOT EXISTS (
            SELECT 1 FROM marts.job_campaigns jc 
            WHERE jc.campaign_id = dr.campaign_id
        );
    END IF;
END $$;

-- Delete fact_jobs for non-existent campaigns (if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'fact_jobs') THEN
        DELETE FROM marts.fact_jobs fj
        WHERE NOT EXISTS (
            SELECT 1 FROM marts.job_campaigns jc 
            WHERE jc.campaign_id = fj.campaign_id
        );
    END IF;
END $$;

-- Delete ETL metrics for non-existent campaigns
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'etl_run_metrics') THEN
        DELETE FROM marts.etl_run_metrics erm
        WHERE erm.campaign_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM marts.job_campaigns jc 
                WHERE jc.campaign_id = erm.campaign_id
            );
    END IF;
END $$;

-- Step 2: Create sequence for campaign_id if it doesn't exist
-- This ensures unique, auto-incrementing IDs
DO $$
DECLARE
    max_id integer;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'marts' 
        AND c.relname = 'job_campaigns_campaign_id_seq'
        AND c.relkind = 'S'
    ) THEN
        CREATE SEQUENCE marts.job_campaigns_campaign_id_seq;
        -- Set sequence to current max + 1
        SELECT COALESCE(MAX(campaign_id), 0) INTO max_id FROM marts.job_campaigns;
        PERFORM setval('marts.job_campaigns_campaign_id_seq', max_id + 1, false);
    END IF;
END $$;

-- Step 3: Add PRIMARY KEY constraint if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'job_campaigns_pkey' 
        AND conrelid = 'marts.job_campaigns'::regclass
    ) THEN
        ALTER TABLE marts.job_campaigns 
        ADD CONSTRAINT job_campaigns_pkey PRIMARY KEY (campaign_id);
    END IF;
END $$;

-- Step 4: Set default value for campaign_id to use sequence (if sequence exists)
-- This makes new inserts automatically use the sequence
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'marts' 
        AND c.relname = 'job_campaigns_campaign_id_seq'
        AND c.relkind = 'S'
    ) THEN
        ALTER TABLE marts.job_campaigns 
        ALTER COLUMN campaign_id SET DEFAULT nextval('marts.job_campaigns_campaign_id_seq');
    END IF;
END $$;

-- Step 5: Add foreign key constraints with CASCADE DELETE for related tables
-- This ensures related data is automatically deleted when a campaign is deleted
-- Note: FK constraints are created separately in their own DO blocks to ensure
-- they are created even if cleanup steps above fail

-- Add FK constraint for dim_ranking (if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'dim_ranking') THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint 
            WHERE conname = 'fk_dim_ranking_campaign' 
            AND conrelid = 'marts.dim_ranking'::regclass
        ) THEN
            ALTER TABLE marts.dim_ranking 
            ADD CONSTRAINT fk_dim_ranking_campaign 
            FOREIGN KEY (campaign_id) 
            REFERENCES marts.job_campaigns(campaign_id) 
            ON DELETE CASCADE;
        END IF;
    END IF;
EXCEPTION WHEN OTHERS THEN
    -- Ignore errors (e.g., if campaign_id column doesn't exist yet)
    NULL;
END $$;

-- Add FK constraint for fact_jobs (if table exists - it's created by dbt)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'fact_jobs') THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint 
            WHERE conname = 'fk_fact_jobs_campaign' 
            AND conrelid = 'marts.fact_jobs'::regclass
        ) THEN
            ALTER TABLE marts.fact_jobs 
            ADD CONSTRAINT fk_fact_jobs_campaign 
            FOREIGN KEY (campaign_id) 
            REFERENCES marts.job_campaigns(campaign_id) 
            ON DELETE CASCADE;
        END IF;
    END IF;
END $$;

-- Add FK constraint for etl_run_metrics (if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'etl_run_metrics') THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint 
            WHERE conname = 'fk_etl_run_metrics_campaign' 
            AND conrelid = 'marts.etl_run_metrics'::regclass
        ) THEN
            ALTER TABLE marts.etl_run_metrics 
            ADD CONSTRAINT fk_etl_run_metrics_campaign 
            FOREIGN KEY (campaign_id) 
            REFERENCES marts.job_campaigns(campaign_id) 
            ON DELETE CASCADE;
        END IF;
    END IF;
EXCEPTION WHEN OTHERS THEN
    -- Ignore errors (e.g., if campaign_id column doesn't exist yet)
    NULL;
END $$;

COMMENT ON SEQUENCE marts.job_campaigns_campaign_id_seq IS 'Auto-incrementing sequence for campaign_id. Ensures unique campaign IDs even after deletions.';
COMMENT ON CONSTRAINT job_campaigns_pkey ON marts.job_campaigns IS 'Primary key constraint ensuring campaign_id uniqueness.';
COMMENT ON CONSTRAINT fk_dim_ranking_campaign ON marts.dim_ranking IS 'Foreign key ensuring rankings are deleted when campaign is deleted.';
COMMENT ON CONSTRAINT fk_fact_jobs_campaign ON marts.fact_jobs IS 'Foreign key ensuring jobs are deleted when campaign is deleted.';
COMMENT ON CONSTRAINT fk_etl_run_metrics_campaign ON marts.etl_run_metrics IS 'Foreign key ensuring ETL metrics are deleted when campaign is deleted.';
