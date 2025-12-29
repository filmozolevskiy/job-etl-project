-- ============================================================
-- Migration Script: Rename Profile to Campaign
-- Renames marts.profile_preferences to marts.job_campaigns
-- Renames all profile_id columns to campaign_id
-- Renames profile_name columns to campaign_name
-- ============================================================
-- This script is idempotent and safe to run multiple times
-- Run this after ensuring all services are stopped
-- ============================================================

BEGIN;

-- Step 1: Rename the table
ALTER TABLE IF EXISTS marts.profile_preferences 
    RENAME TO job_campaigns;

-- Step 2: Rename columns in marts.job_campaigns
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'marts' 
        AND table_name = 'job_campaigns' 
        AND column_name = 'profile_id'
    ) THEN
        ALTER TABLE marts.job_campaigns RENAME COLUMN profile_id TO campaign_id;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'marts' 
        AND table_name = 'job_campaigns' 
        AND column_name = 'profile_name'
    ) THEN
        ALTER TABLE marts.job_campaigns RENAME COLUMN profile_name TO campaign_name;
    END IF;
END $$;

-- Step 3: Rename columns in raw.jsearch_job_postings
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'raw' 
        AND table_name = 'jsearch_job_postings' 
        AND column_name = 'profile_id'
    ) THEN
        ALTER TABLE raw.jsearch_job_postings RENAME COLUMN profile_id TO campaign_id;
    END IF;
END $$;

-- Step 4: Rename columns in marts.dim_ranking
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'marts' 
        AND table_name = 'dim_ranking' 
        AND column_name = 'profile_id'
    ) THEN
        ALTER TABLE marts.dim_ranking RENAME COLUMN profile_id TO campaign_id;
    END IF;
END $$;

-- Step 5: Rename columns in marts.etl_run_metrics
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'marts' 
        AND table_name = 'etl_run_metrics' 
        AND column_name = 'profile_id'
    ) THEN
        ALTER TABLE marts.etl_run_metrics RENAME COLUMN profile_id TO campaign_id;
    END IF;
END $$;

-- Step 5a: Rename columns in marts.fact_jobs (dbt materialized table)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'marts' 
        AND table_name = 'fact_jobs' 
        AND column_name = 'profile_id'
    ) THEN
        ALTER TABLE marts.fact_jobs RENAME COLUMN profile_id TO campaign_id;
    END IF;
END $$;

-- Step 6: Update primary key constraint name in dim_ranking (if it references profile_id in name)
-- Note: The constraint name might not include profile_id, but we'll update it for consistency
DO $$
BEGIN
    -- Drop and recreate primary key with new column name
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'dim_ranking_pkey' 
        AND conrelid = 'marts.dim_ranking'::regclass
    ) THEN
        ALTER TABLE marts.dim_ranking DROP CONSTRAINT dim_ranking_pkey;
        ALTER TABLE marts.dim_ranking ADD CONSTRAINT dim_ranking_pkey PRIMARY KEY (jsearch_job_id, campaign_id);
    END IF;
END $$;

-- Step 7: Update foreign key constraint name in job_campaigns
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'fk_profile_user' 
        AND conrelid = 'marts.job_campaigns'::regclass
    ) THEN
        ALTER TABLE marts.job_campaigns DROP CONSTRAINT fk_profile_user;
        ALTER TABLE marts.job_campaigns ADD CONSTRAINT fk_campaign_user FOREIGN KEY (user_id) REFERENCES marts.users(user_id) ON DELETE CASCADE;
    END IF;
END $$;

-- Step 8: Rename indexes
DROP INDEX IF EXISTS marts.idx_profile_preferences_active;
CREATE INDEX IF NOT EXISTS idx_job_campaigns_active 
    ON marts.job_campaigns(is_active) 
    WHERE is_active = true;

DROP INDEX IF EXISTS marts.idx_profile_preferences_profile_id;
CREATE INDEX IF NOT EXISTS idx_job_campaigns_campaign_id 
    ON marts.job_campaigns(campaign_id);

DROP INDEX IF EXISTS marts.idx_profile_preferences_user_id;
CREATE INDEX IF NOT EXISTS idx_job_campaigns_user_id 
    ON marts.job_campaigns(user_id);

DROP INDEX IF EXISTS raw.idx_jsearch_job_postings_profile_id;
CREATE INDEX IF NOT EXISTS idx_jsearch_job_postings_campaign_id 
    ON raw.jsearch_job_postings(campaign_id);

DROP INDEX IF EXISTS marts.idx_etl_run_metrics_profile_id;
CREATE INDEX IF NOT EXISTS idx_etl_run_metrics_campaign_id 
    ON marts.etl_run_metrics(campaign_id);

-- Step 9: Update table comments
COMMENT ON TABLE marts.job_campaigns IS 'Stores job campaigns that drive extraction and ranking. Campaigns are managed exclusively via the Campaign Management UI. Each campaign belongs to a user. ETL services query active campaigns (WHERE is_active = true) for job extraction.';

-- Step 10: Update column comments
COMMENT ON COLUMN marts.job_campaigns.campaign_id IS 'Unique identifier for the job campaign (formerly profile_id)';
COMMENT ON COLUMN marts.job_campaigns.campaign_name IS 'Human-readable name for the campaign (formerly profile_name)';

COMMIT;

