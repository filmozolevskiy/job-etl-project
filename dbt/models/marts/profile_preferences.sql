{{ config(
    materialized='ephemeral',
    schema='marts'
) }}

-- Profile preferences: Managed exclusively via Profile Management UI
-- 
-- IMPORTANT: Table structure is created by docker/init/02_create_tables.sql
-- Profiles are created and managed via the Profile Management UI only
-- This model exists for dbt lineage only (ephemeral = no database object created)
-- 
-- The actual table is marts.profile_preferences (created by script)
-- ETL services should query: SELECT * FROM marts.profile_preferences WHERE is_active = true
-- If no active profiles exist, ETL services should fail with clear error message:
-- "No active profiles found. Please create at least one profile via the Profile Management UI."

select
    profile_id,
    profile_name,
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
    last_run_job_count
from marts.profile_preferences
