{{ config(
    materialized='view',
    schema='marts'
) }}

-- Dimension Ranking: View over dim_ranking_staging table
-- 
-- IMPORTANT: Staging table structure is created by docker/init/02_create_tables.sql
-- Data is written by the Ranker service (services/ranker/job_ranker.py) to dim_ranking_staging
-- This view provides backward compatibility for queries using dim_ranking
-- 
-- One row per (job, campaign) pair with ranking scores
-- Foreign key: jsearch_job_id references fact_jobs.jsearch_job_id
-- Primary key: (jsearch_job_id, campaign_id) - composite key (on staging table)

select
    -- Composite natural key
    jsearch_job_id,
    campaign_id,
    
    -- Ranking score (0-100)
    rank_score,
    
    -- rank_explain JSON (breakdown of each factor's contribution)
    rank_explain,
    
    -- Timestamps
    ranked_at,
    ranked_date,
    
    -- Technical columns
    dwh_load_timestamp,
    dwh_source_system
    
from marts.dim_ranking_staging

