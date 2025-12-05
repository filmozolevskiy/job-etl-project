{{ config(
    materialized='table'
) }}

-- Staging layer: Normalized job postings from JSearch
-- Extracts and cleans data from raw.jsearch_job_postings JSON payloads
-- Deduplicates on job_id

with raw_data as (
    select
        raw_job_posting_id,
        raw_payload,
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system,
        profile_id
    from {{ ref('raw_jsearch_job_postings') }}
    where raw_payload is not null
),

extracted as (
    select
        raw_job_posting_id,
        profile_id,
        
        -- Extract job_id (natural key from JSearch)
        raw_payload->>'job_id' as job_id,
        
        -- Basic job information
        raw_payload->>'job_title' as job_title,
        raw_payload->>'job_description' as job_description,
        raw_payload->>'employer_name' as employer_name,
        
        -- Location fields
        raw_payload->>'job_city' as job_city,
        raw_payload->>'job_state' as job_state,
        raw_payload->>'job_country' as job_country,
        raw_payload->>'job_location' as job_location,
        (raw_payload->>'job_latitude')::numeric as job_latitude,
        (raw_payload->>'job_longitude')::numeric as job_longitude,
        
        -- Employment details
        raw_payload->>'employment_types' as employment_types,
        (raw_payload->>'job_is_remote')::boolean as job_is_remote,
        
        -- Dates
        raw_payload->>'job_posted_at' as job_posted_at,
        (raw_payload->>'job_posted_at_timestamp')::bigint as job_posted_at_timestamp,
        raw_payload->>'job_posted_at_datetime_utc' as job_posted_at_datetime_utc,
        
        -- Salary information
        raw_payload->>'job_salary' as job_salary,
        (raw_payload->>'job_min_salary')::numeric as job_min_salary,
        (raw_payload->>'job_max_salary')::numeric as job_max_salary,
        raw_payload->>'job_salary_period' as job_salary_period,
        
        -- Application links
        raw_payload->>'job_apply_link' as job_apply_link,
        raw_payload->>'job_google_link' as job_google_link,
        
        -- Publisher information
        raw_payload->>'job_publisher' as job_publisher,
        
        -- Technical columns
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system
        
    from raw_data
),

-- Deduplicate on job_id, keeping the most recent record
deduplicated as (
    select
        *,
        row_number() over (
            partition by job_id 
            order by dwh_load_timestamp desc
        ) as rn
    from extracted
    where job_id is not null
)

select
    raw_job_posting_id,
    profile_id,
    job_id,
    job_title,
    job_description,
    employer_name,
    job_city,
    job_state,
    job_country,
    job_location,
    job_latitude,
    job_longitude,
    employment_types,
    job_is_remote,
    job_posted_at,
    job_posted_at_timestamp,
    job_posted_at_datetime_utc,
    job_salary,
    job_min_salary,
    job_max_salary,
    job_salary_period,
    job_apply_link,
    job_google_link,
    job_publisher,
    dwh_load_date,
    dwh_load_timestamp,
    dwh_source_system
from deduplicated
where rn = 1

