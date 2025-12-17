{{ config(
    materialized='table',
    schema='marts'
) }}

-- Marts layer: Fact Jobs
-- One row per unique job per profile (deduplicated by jsearch_job_id, profile_id)
-- Built from staging.jsearch_job_postings
-- Joined to dim_companies on employer_name (used for matching only, not stored)
-- Primary key: (jsearch_job_id, profile_id) - composite key
-- Foreign keys: company_key, profile_id (references profile_preferences)

with staging_jobs as (
    select
        jsearch_job_postings_key,
        jsearch_job_id,
        profile_id,
        job_title,
        employer_name,
        job_location,
        job_employment_type,
        apply_options,
        job_apply_link,
        job_is_remote,
        job_posted_at_datetime_utc,
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system
    from {{ ref('jsearch_job_postings') }}
    where jsearch_job_id is not null
        and profile_id is not null
),

-- Join to companies dimension
jobs_with_companies as (
    select
        sj.*,
        dc.company_key
    from staging_jobs sj
    left join {{ ref('dim_companies') }} dc
        on lower(trim(sj.employer_name)) = dc.normalized_company_name
),

-- Deduplicate on (jsearch_job_id, profile_id), keeping the most recent record
with_derived as (
    select
        -- Natural keys (composite primary key)
        jsearch_job_id,
        profile_id,
        
        -- Foreign key
        company_key,
        
        -- Essential job fields
        job_title,
        employer_name,
        job_location,
        job_employment_type,
        apply_options,
        job_is_remote,
        job_posted_at_datetime_utc,
        
        -- Get_apply_link
        CASE 
            WHEN job_apply_link IS NOT NULL 
            THEN job_apply_link
            ELSE NULL
        END as job_apply_link,
        
        -- Technical columns
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system,
        
        -- Deduplication row number
        row_number() over (
            partition by jsearch_job_id, profile_id
            order by dwh_load_timestamp desc
        ) as rn
        
    from jobs_with_companies
)

select
    jsearch_job_id,
    profile_id,
    company_key,
    job_title,
    employer_name,
    job_location,
    job_employment_type,
    apply_options,
    job_apply_link,
    job_is_remote,
    job_posted_at_datetime_utc,
    dwh_load_date,
    dwh_load_timestamp,
    dwh_source_system
from with_derived
where rn = 1
