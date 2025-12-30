-- ============================================================
-- Migration Script: Convert Salaries to Yearly Integer and Convert dim_ranking to View
-- 
-- This script migrates existing data to the new schema:
-- 1. Converts salary columns in job_campaigns to INTEGER (yearly amounts)
-- 2. Migrates dim_ranking table to dim_ranking_staging
-- 3. Creates dim_ranking view
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
-- Step 2: Migrate dim_ranking table to dim_ranking_staging
-- ============================================================

-- Create staging table if it doesn't exist
CREATE TABLE IF NOT EXISTS marts.dim_ranking_staging (
    jsearch_job_id varchar,
    campaign_id integer,
    rank_score numeric,
    rank_explain jsonb,
    ranked_at timestamp,
    ranked_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar,
    CONSTRAINT dim_ranking_staging_pkey PRIMARY KEY (jsearch_job_id, campaign_id)
);

-- Migrate data from dim_ranking to dim_ranking_staging (if old table exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = 'marts' 
        AND table_name = 'dim_ranking'
        AND table_type = 'BASE TABLE'  -- Only migrate if it's a table, not a view
    ) THEN
        -- Check if staging table is empty
        IF NOT EXISTS (SELECT 1 FROM marts.dim_ranking_staging LIMIT 1) THEN
            -- Migrate data
            INSERT INTO marts.dim_ranking_staging (
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
            FROM marts.dim_ranking
            ON CONFLICT (jsearch_job_id, campaign_id) DO NOTHING;
            
            RAISE NOTICE 'Migrated data from dim_ranking to dim_ranking_staging';
        ELSE
            RAISE NOTICE 'dim_ranking_staging already contains data, skipping migration';
        END IF;
        
        -- Drop old table (after migration)
        DROP TABLE IF EXISTS marts.dim_ranking CASCADE;
        RAISE NOTICE 'Dropped old dim_ranking table';
    ELSE
        RAISE NOTICE 'dim_ranking table does not exist or is already a view, skipping migration';
    END IF;
END $$;

-- ============================================================
-- Step 3: Create dim_ranking view
-- ============================================================

CREATE OR REPLACE VIEW marts.dim_ranking AS
SELECT
    jsearch_job_id,
    campaign_id,
    rank_score,
    rank_explain,
    ranked_at,
    ranked_date,
    dwh_load_timestamp,
    dwh_source_system
FROM marts.dim_ranking_staging;

COMMENT ON VIEW marts.dim_ranking IS 'View over dim_ranking_staging table. Provides same interface as before for backward compatibility.';

-- ============================================================
-- Step 4: Update permissions
-- ============================================================

-- Grant permissions to application user (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_user WHERE usename = 'app_user') THEN
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.dim_ranking_staging TO app_user';
        IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'marts' AND viewname = 'dim_ranking') THEN
            BEGIN
                EXECUTE format('GRANT SELECT ON VIEW %I.%I TO %I', 'marts', 'dim_ranking', 'app_user');
            EXCEPTION
                WHEN OTHERS THEN
                    -- Ignore errors if grant fails
                    NULL;
            END;
        END IF;
    END IF;
END $$;

-- Grant permissions to postgres user (for Docker default)
GRANT ALL PRIVILEGES ON TABLE marts.dim_ranking_staging TO postgres;
-- Grant view permissions conditionally (view might not exist in some test scenarios)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'marts' AND viewname = 'dim_ranking') THEN
        BEGIN
            EXECUTE format('GRANT SELECT ON VIEW %I.%I TO %I', 'marts', 'dim_ranking', 'postgres');
        EXCEPTION
            WHEN OTHERS THEN
                -- Ignore errors if grant fails
                NULL;
        END;
    END IF;
END $$;

