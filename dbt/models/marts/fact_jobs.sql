{{ config(
    materialized='table',
    schema='marts'
) }}

-- Marts layer: Fact Jobs
-- One row per unique job per campaign (deduplicated by jsearch_job_id, campaign_id)
-- Built from staging.jsearch_job_postings
-- Joined to dim_companies on employer_name (used for matching only, not stored)
-- Primary key: (jsearch_job_id, campaign_id) - composite key
-- Foreign keys: company_key, campaign_id (references job_campaigns)

with staging_jobs as (
    select
        jsearch_job_postings_key,
        jsearch_job_id,
        campaign_id,
        job_title,
        employer_name,
        job_location,
        job_employment_type,
        job_employment_types,
        employment_types,
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
        and campaign_id is not null
        -- Filter by campaign_id if provided via dbt variable
        -- Uses -1 as sentinel value (invalid campaign_id) to detect if variable was provided
        -- When campaign_id is not provided, var('campaign_id', -1) returns -1, so condition is false
        -- When campaign_id is provided, condition is true and filters to that campaign
        {% if var('campaign_id', -1) != -1 %}
        and campaign_id = {{ var('campaign_id') }}
        {% endif %}
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

-- Deduplicate on (jsearch_job_id, campaign_id), keeping the most recent record
with_derived as (
    select
        -- Natural keys (composite primary key)
        jsearch_job_id,
        campaign_id,
        
        -- Foreign key
        company_key,
        
        -- Essential job fields
        job_title,
        employer_name,
        job_location,
        job_employment_type,
        job_employment_types,
        employment_types,
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
            partition by jsearch_job_id, campaign_id
            order by dwh_load_timestamp desc
        ) as rn
        
    from jobs_with_companies
)

select
    jsearch_job_id,
    campaign_id,
    company_key,
    job_title,
    employer_name,
    job_location,
    job_employment_type,
    job_employment_types,
    employment_types,
    apply_options,
    job_apply_link,
    job_is_remote,
    job_posted_at_datetime_utc,
    -- Enriched columns (populated by Enricher service)
    extracted_skills,  -- JSON array of extracted skills
    seniority_level,   -- Seniority level: intern, junior, mid, senior, executive
    remote_work_type, -- Remote work type: remote, hybrid, onsite
    job_min_salary,    -- Minimum yearly salary as integer
    job_max_salary,    -- Maximum yearly salary as integer
    job_salary_period, -- Original salary period: year, month, week, day, hour (for reference)
    job_salary_currency, -- Currency code: USD, CAD, EUR, GBP, or NULL
    dwh_load_date,
    dwh_load_timestamp,
    dwh_source_system
from with_derived
where rn = 1
