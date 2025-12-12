{{ config(
    materialized='table',
    schema='marts',
    enabled=true,
    post_hook="
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'dim_ranking_pkey'
            ) THEN
                ALTER TABLE {{ this }} 
                ADD CONSTRAINT dim_ranking_pkey 
                PRIMARY KEY (jsearch_job_id, profile_id);
            END IF;
        END $$;
    "
) }}
-- Enabled - this is just table structure, no data extraction needed

-- Marts layer: Dimension Ranking
-- One row per (job, profile) pair
-- 
-- This table structure is created by dbt, but data is written by the Ranker service
-- This ensures the table exists with proper schema before Ranker runs
-- The Ranker service will INSERT/UPDATE ranking scores here
-- Foreign key: jsearch_job_id references fact_jobs.jsearch_job_id
-- Primary key: (jsearch_job_id, profile_id) - composite key


select
    -- Composite natural key
    cast(null as varchar) as jsearch_job_id,
    cast(null as integer) as profile_id,
    
    -- Ranking score (0-100)
    cast(null as numeric) as rank_score,
    
    -- Phase 3: rank_explain JSON (breakdown of each factor's contribution)
    -- For MVP, this will be NULL; Phase 3 will populate it
    cast(null as jsonb) as rank_explain,
    
    -- Timestamps
    cast(null as timestamp) as ranked_at,
    cast(null as date) as ranked_date,
    
    -- Technical columns
    cast(null as timestamp) as dwh_load_timestamp,
    cast(null as varchar) as dwh_source_system
    
where false  -- This ensures no rows are created, just the schema

