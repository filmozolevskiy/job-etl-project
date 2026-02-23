{{ config(
    materialized='ephemeral',
    schema='marts'
) }}

-- Job campaigns: Managed exclusively via Campaign Management UI
-- 
-- IMPORTANT: Table structure is created by docker/init/02_create_tables.sql
-- Campaigns are created and managed via the Campaign Management UI only
-- This model exists for dbt lineage only (ephemeral = no database object created)
-- 
-- The actual table is marts.job_campaigns (created by script)
-- ETL services should query: SELECT * FROM marts.job_campaigns WHERE is_active = true
-- If no active campaigns exist, ETL services should fail with clear error message:
-- "No active campaigns found. Please create at least one campaign via the Campaign Management UI."

select
    campaign_id,
    campaign_name,
    is_active,
    query,
    location,
    country,
    date_window,
    email,
    skills,
    min_salary,
    max_salary,
    remote_preference,
    seniority,
    created_at,
    updated_at,
    total_run_count,
    last_run_at,
    last_run_status,
    last_run_job_count,
    last_notification_sent_at
from marts.job_campaigns
