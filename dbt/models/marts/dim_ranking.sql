{{ config(
    materialized='ephemeral',
    schema='marts'
) }}

-- Dimension Ranking: Populated by Ranker service
-- 
-- IMPORTANT: Table structure is created by docker/init/02_create_tables.sql
-- Data is written by the Ranker service (services/ranker/job_ranker.py)
-- This model exists for dbt lineage only (ephemeral = no database object created)
-- 
-- One row per (job, campaign) pair with ranking scores
-- Foreign key: jsearch_job_id references fact_jobs.jsearch_job_id
-- Primary key: (jsearch_job_id, campaign_id) - composite key (created in init script)

select
    -- Composite natural key
    jsearch_job_id,
    campaign_id,
    
    -- Ranking score (0-100)
    rank_score,
    
    -- Phase 3: rank_explain JSON (breakdown of each factor's contribution)
    -- For MVP, this will be NULL; Phase 3 will populate it
    rank_explain,
    
    -- Timestamps
    ranked_at,
    ranked_date,
    
    -- Technical columns
    dwh_load_timestamp,
    dwh_source_system
    
from marts.dim_ranking

