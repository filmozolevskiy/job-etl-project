-- ============================================================
-- Migration Script: Convert Salaries to Yearly Integer and Simplify dim_ranking
-- 
-- This script migrates existing data to the new schema:
-- 1. Converts salary columns in job_campaigns to INTEGER (yearly amounts)
-- 2. Migrates dim_ranking_staging to dim_ranking table (if staging exists)
-- 3. Drops dim_ranking_staging table and view (if they exist)
-- 
-- This script is idempotent and safe to run multiple times
-- ============================================================

-- ============================================================
-- Step 1: Convert salary columns in job_campaigns to INTEGER
-- ============================================================

-- Note: This assumes existing salaries are already in yearly amounts or need conversion
-- If you have existing data with different periods, you'll need to handle conversion
-- For now, we'll convert numeric to integer (rounding if needed)

DO $$
BEGIN
    -- Check if columns are already INTEGER
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'marts' 
        AND table_name = 'job_campaigns' 
        AND column_name = 'min_salary' 
        AND data_type = 'integer'
    ) THEN
        RAISE NOTICE 'min_salary and max_salary are already INTEGER, skipping conversion';
    ELSE
        -- Convert numeric to integer (rounding to nearest integer)
        ALTER TABLE marts.job_campaigns 
        ALTER COLUMN min_salary TYPE integer USING ROUND(COALESCE(min_salary, 0))::integer;
        
        ALTER TABLE marts.job_campaigns 
        ALTER COLUMN max_salary TYPE integer USING ROUND(COALESCE(max_salary, 0))::integer;
        
        RAISE NOTICE 'Converted salary columns to INTEGER';
    END IF;
END $$;

-- ============================================================
-- Step 2: Migrate dim_ranking_staging to dim_ranking table
-- ============================================================

-- First, drop the view if it exists (must be done before creating table)
DROP VIEW IF EXISTS marts.dim_ranking CASCADE;

-- Ensure dim_ranking table exists (should be created by 02_create_tables.sql)
CREATE TABLE IF NOT EXISTS marts.dim_ranking (
    jsearch_job_id varchar,
    campaign_id integer,
    rank_score numeric,
    rank_explain jsonb,
    ranked_at timestamp,
    ranked_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar,
    CONSTRAINT dim_ranking_pkey PRIMARY KEY (jsearch_job_id, campaign_id)
);

-- Migrate data from dim_ranking_staging to dim_ranking (if staging exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = 'marts' 
        AND table_name = 'dim_ranking_staging'
        AND table_type = 'BASE TABLE'
    ) THEN
        -- Check if dim_ranking table is empty
        IF NOT EXISTS (SELECT 1 FROM marts.dim_ranking LIMIT 1) THEN
            -- Migrate data from staging to table
            INSERT INTO marts.dim_ranking (
                jsearch_job_id,
                campaign_id,
                rank_score,
                rank_explain,
                ranked_at,
                ranked_date,
                dwh_load_timestamp,
                dwh_source_system
            )
            SELECT 
                jsearch_job_id,
                campaign_id,
                rank_score,
                rank_explain,
                ranked_at,
                ranked_date,
                dwh_load_timestamp,
                dwh_source_system
            FROM marts.dim_ranking_staging
            ON CONFLICT (jsearch_job_id, campaign_id) DO NOTHING;
            
            RAISE NOTICE 'Migrated data from dim_ranking_staging to dim_ranking table';
        ELSE
            RAISE NOTICE 'dim_ranking table already contains data, skipping migration';
        END IF;
        
        -- Drop staging table (after migration)
        DROP TABLE IF EXISTS marts.dim_ranking_staging CASCADE;
        RAISE NOTICE 'Dropped dim_ranking_staging table';
    ELSE
        RAISE NOTICE 'dim_ranking_staging table does not exist, skipping migration';
    END IF;
END $$;

-- ============================================================
-- Step 3: Add comments and permissions
-- ============================================================

-- Add comment and grant permissions (only if table exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = 'marts' 
        AND table_name = 'dim_ranking'
        AND table_type = 'BASE TABLE'
    ) THEN
        EXECUTE 'COMMENT ON TABLE marts.dim_ranking IS ''Job ranking scores per campaign. One row per (job, campaign) pair. Populated by the Ranker service using UPSERT.''';
        
        -- Grant permissions to application user (if exists)
        IF EXISTS (SELECT FROM pg_user WHERE usename = 'app_user') THEN
            EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.dim_ranking TO app_user';
        END IF;
        
        -- Grant permissions to postgres user (for Docker default)
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.dim_ranking TO postgres';
        
        RAISE NOTICE 'Added comments and permissions to dim_ranking table';
    ELSE
        RAISE NOTICE 'dim_ranking table does not exist, skipping comments and permissions';
    END IF;
END $$;

