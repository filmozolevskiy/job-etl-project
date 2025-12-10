{{ config(
    materialized='table'
) }}

-- Staging layer: Normalized job postings from JSearch
-- Extracts and cleans data from raw.jsearch_job_postings JSON payloads
-- Deduplicates on jsearch_job_id
-- 
-- Updated based on actual API payload inspection (2025-12-07)
-- Key changes:
-- - employment_types is actually job_employment_types (array)
-- - job_salary field doesn't exist (only min/max/period)
-- - Added additional useful fields from payload

with raw_data as (
    select
        jsearch_job_postings_key,
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
        jsearch_job_postings_key,
        profile_id,
        
        -- Extract jsearch_job_id (natural key from JSearch)
        raw_payload->>'job_id' as jsearch_job_id,
        
        -- Basic job information
        raw_payload->>'job_title' as job_title,
        raw_payload->>'job_description' as job_description,
        raw_payload->>'employer_name' as employer_name,
        raw_payload->>'employer_logo' as employer_logo,
        raw_payload->>'employer_website' as employer_website,
        
        -- Location fields
        raw_payload->>'job_city' as job_city,
        raw_payload->>'job_state' as job_state,
        raw_payload->>'job_country' as job_country,
        raw_payload->>'job_location' as job_location,
        (raw_payload->>'job_latitude')::numeric as job_latitude,
        (raw_payload->>'job_longitude')::numeric as job_longitude,
        
        -- Employment details
        raw_payload->>'job_employment_type' as job_employment_type,  -- String version (e.g., "Full-time")
        raw_payload->'job_employment_types' as job_employment_types,  -- Array version (e.g., ["FULLTIME"])
        -- Convert array to comma-separated string for easier querying
        array_to_string(
            ARRAY(SELECT jsonb_array_elements_text(raw_payload->'job_employment_types')),
            ','
        ) as employment_types,
        (raw_payload->>'job_is_remote')::boolean as job_is_remote,
        
        -- Dates
        raw_payload->>'job_posted_at' as job_posted_at,
        (raw_payload->>'job_posted_at_timestamp')::bigint as job_posted_at_timestamp,
        raw_payload->>'job_posted_at_datetime_utc' as job_posted_at_datetime_utc,
        
        -- Salary information (note: job_salary doesn't exist in API, only min/max/period)
        (raw_payload->>'job_min_salary')::numeric as job_min_salary,
        (raw_payload->>'job_max_salary')::numeric as job_max_salary,
        raw_payload->>'job_salary_period' as job_salary_period,
        
        -- Application links
        raw_payload->>'job_apply_link' as job_apply_link,
        raw_payload->>'job_google_link' as job_google_link,
        (raw_payload->>'job_apply_is_direct')::boolean as job_apply_is_direct,
        raw_payload->'apply_options' as apply_options,  -- Array of apply options
        
        -- Publisher information
        raw_payload->>'job_publisher' as job_publisher,
        
        -- Additional fields
        raw_payload->>'job_benefits' as job_benefits,
        raw_payload->'job_highlights' as job_highlights,  -- JSON object
        raw_payload->>'job_onet_soc' as job_onet_soc,
        raw_payload->>'job_onet_job_zone' as job_onet_job_zone,
        
        -- Technical columns
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system
        
    from raw_data
),

-- Deduplicate on jsearch_job_id, keeping the most recent record
deduplicated as (
    select
        *,
        row_number() over (
            partition by jsearch_job_id 
            order by dwh_load_timestamp desc
        ) as rn
    from extracted
    where jsearch_job_id is not null
)

select
    jsearch_job_postings_key,
    profile_id,
    jsearch_job_id,
    job_title,
    job_description,
    employer_name,
    job_city,
    job_state,
    job_country,
    job_location,
    job_latitude,
    job_longitude,
    job_employment_type,
    job_employment_types,
    employment_types,
    job_is_remote,
    job_posted_at,
    job_posted_at_timestamp,
    job_posted_at_datetime_utc,
    job_min_salary,
    job_max_salary,
    job_salary_period,
    job_apply_link,
    job_google_link,
    job_apply_is_direct,
    apply_options,
    job_publisher,
    job_benefits,
    job_highlights,
    job_onet_soc,
    job_onet_job_zone,
    employer_logo,
    employer_website,
    dwh_load_date,
    dwh_load_timestamp,
    dwh_source_system
from deduplicated
where rn = 1

