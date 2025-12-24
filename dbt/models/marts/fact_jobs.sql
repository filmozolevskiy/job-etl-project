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
        -- Enriched columns (populated by Enricher service)
        extracted_skills,
        seniority_level,
        remote_work_type,
        job_min_salary,
        job_max_salary,
        job_salary_period,
        job_salary_currency,
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
        
        -- Enriched columns (populated by Enricher service)
        extracted_skills,
        seniority_level,
        remote_work_type,
        job_min_salary,
        job_max_salary,
        job_salary_period,
        job_salary_currency,
        
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
    -- Enriched columns (populated by Enricher service)
    extracted_skills,  -- JSON array of extracted skills
    seniority_level,   -- Seniority level: intern, junior, mid, senior, executive
    remote_work_type, -- Remote work type: remote, hybrid, onsite
    job_min_salary,    -- Minimum salary (enriched or from API)
    job_max_salary,    -- Maximum salary (enriched or from API)
    job_salary_period, -- Salary period: year, month, week, day, hour
    job_salary_currency, -- Currency code: USD, CAD, EUR, GBP, or NULL
    dwh_load_date,
    dwh_load_timestamp,
    dwh_source_system
from with_derived
where rn = 1
