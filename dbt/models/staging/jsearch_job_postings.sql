{{ config(
    materialized='incremental',
    unique_key=['jsearch_job_id', 'campaign_id'],
    on_schema_change='append_new_columns'
) }}

-- Staging layer: Normalized job postings from JSearch
-- Extracts and cleans data from raw.jsearch_job_postings JSON payloads
-- Deduplicates on (jsearch_job_id, campaign_id)

with raw_data as (
    select
        jsearch_job_postings_key,
        raw_payload,
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system,
        campaign_id
    from {{ ref('raw_jsearch_job_postings') }}
    where raw_payload is not null
        -- Filter by campaign_id if provided via dbt variable
        -- Uses -1 as sentinel value (invalid campaign_id) to detect if variable was provided
        -- When campaign_id is not provided, var('campaign_id', -1) returns -1, so condition is false
        -- When campaign_id is provided, condition is true and filters to that campaign
        {% if var('campaign_id', -1) != -1 %}
        and campaign_id = {{ var('campaign_id') }}
        {% endif %}
),

extracted as (
    select
        jsearch_job_postings_key,
        campaign_id,
        
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
        -- Convert to yearly integer amounts (rounding to nearest integer)
        CASE
            WHEN raw_payload->>'job_min_salary' IS NOT NULL AND raw_payload->>'job_salary_period' IS NOT NULL THEN
                CASE LOWER(raw_payload->>'job_salary_period')
                    WHEN 'year' THEN ROUND((raw_payload->>'job_min_salary')::numeric)::integer
                    WHEN 'month' THEN ROUND((raw_payload->>'job_min_salary')::numeric * 12)::integer
                    WHEN 'week' THEN ROUND((raw_payload->>'job_min_salary')::numeric * 52)::integer
                    WHEN 'day' THEN ROUND((raw_payload->>'job_min_salary')::numeric * 260)::integer  -- ~260 working days per year
                    WHEN 'hour' THEN ROUND((raw_payload->>'job_min_salary')::numeric * 2080)::integer  -- ~2080 working hours per year
                    ELSE ROUND((raw_payload->>'job_min_salary')::numeric)::integer  -- Assume yearly if unknown
                END
            ELSE NULL
        END as job_min_salary,
        CASE
            WHEN raw_payload->>'job_max_salary' IS NOT NULL AND raw_payload->>'job_salary_period' IS NOT NULL THEN
                CASE LOWER(raw_payload->>'job_salary_period')
                    WHEN 'year' THEN ROUND((raw_payload->>'job_max_salary')::numeric)::integer
                    WHEN 'month' THEN ROUND((raw_payload->>'job_max_salary')::numeric * 12)::integer
                    WHEN 'week' THEN ROUND((raw_payload->>'job_max_salary')::numeric * 52)::integer
                    WHEN 'day' THEN ROUND((raw_payload->>'job_max_salary')::numeric * 260)::integer  -- ~260 working days per year
                    WHEN 'hour' THEN ROUND((raw_payload->>'job_max_salary')::numeric * 2080)::integer  -- ~2080 working hours per year
                    ELSE ROUND((raw_payload->>'job_max_salary')::numeric)::integer  -- Assume yearly if unknown
                END
            ELSE NULL
        END as job_max_salary,
        raw_payload->>'job_salary_period' as job_salary_period,  -- Keep original period for reference
        
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

-- Deduplicate on (jsearch_job_id, campaign_id), keeping the most recent record per campaign
deduplicated as (
    select
        *,
        row_number() over (
            partition by jsearch_job_id, campaign_id
            order by dwh_load_timestamp desc
        ) as rn
    from extracted
    where jsearch_job_id is not null
),

-- Preserve existing enrichment data from current table (if it exists)
enrichment_preserved as (
    select
        d.*,
        -- Preserve enrichment columns from existing table if available (only in incremental mode)
        {% if is_incremental() %}
        COALESCE(
            existing.extracted_skills,
            NULL::jsonb
        ) as extracted_skills,
        COALESCE(
            existing.seniority_level,
            NULL::varchar
        ) as seniority_level,
        COALESCE(
            existing.remote_work_type,
            NULL::varchar
        ) as remote_work_type,
        COALESCE(
            existing.job_salary_currency,
            NULL::varchar
        ) as job_salary_currency,
        -- ChatGPT enrichment columns (preserve if exists)
        COALESCE(
            existing.job_summary,
            NULL::text
        ) as job_summary,
        COALESCE(
            existing.chatgpt_extracted_skills,
            NULL::jsonb
        ) as chatgpt_extracted_skills,
        COALESCE(
            existing.chatgpt_extracted_location,
            NULL::varchar
        ) as chatgpt_extracted_location,
        COALESCE(
            existing.chatgpt_enriched_at,
            NULL::timestamp
        ) as chatgpt_enriched_at,
        -- Enrichment status tracking (preserve if exists, otherwise default to all false).
        -- New fields (e.g., salary_enriched, chatgpt_enriched) may be added over time; for older rows that
        -- don't have the key yet, COALESCE in the enricher queries will treat them as false.
        COALESCE(
            existing.enrichment_status,
            '{"skills_enriched": false, "seniority_enriched": false, "remote_type_enriched": false, "salary_enriched": false, "chatgpt_enriched": false}'::jsonb
        ) as enrichment_status
        {% else %}
        -- First run: no existing data to preserve
        NULL::jsonb as extracted_skills,
        NULL::varchar as seniority_level,
        NULL::varchar as remote_work_type,
        NULL::varchar as job_salary_currency,
        NULL::text as job_summary,
        NULL::jsonb as chatgpt_extracted_skills,
        NULL::varchar as chatgpt_extracted_location,
        NULL::timestamp as chatgpt_enriched_at,
        '{"skills_enriched": false, "seniority_enriched": false, "remote_type_enriched": false, "salary_enriched": false, "chatgpt_enriched": false}'::jsonb as enrichment_status
        {% endif %}
    from deduplicated d
    {% if is_incremental() %}
    left join {{ this }} existing
        on d.jsearch_job_postings_key = existing.jsearch_job_postings_key
    {% endif %}
    where d.rn = 1
        {% if is_incremental() %}
            {% if var('campaign_id', -1) != -1 %}
                -- Process new records OR records for the specified campaign
                and (
                    d.dwh_load_timestamp > (select coalesce(max(dwh_load_timestamp), '1970-01-01'::timestamp) from {{ this }})
                    or d.campaign_id = {{ var('campaign_id') }}
                )
            {% else %}
                -- Process only new records
                and d.dwh_load_timestamp > (select coalesce(max(dwh_load_timestamp), '1970-01-01'::timestamp) from {{ this }})
            {% endif %}
        {% endif %}
)

select
    jsearch_job_postings_key,
    campaign_id,
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
    job_min_salary,  -- Yearly salary as integer
    job_max_salary,  -- Yearly salary as integer
    job_salary_period,  -- Original period (year, month, week, day, hour) for reference
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
    -- Enrichment columns (populated by Enricher service, preserved from existing table)
    extracted_skills,  -- JSON array of extracted skills
    seniority_level,   -- Seniority level: intern, junior, mid, senior, executive
    remote_work_type, -- Remote work type: remote, hybrid, onsite
    job_salary_currency, -- Currency code: USD, CAD, EUR, GBP, or NULL
    -- ChatGPT enrichment columns (populated by ChatGPTEnricher service)
    job_summary,  -- 2-sentence summary generated by ChatGPT
    chatgpt_extracted_skills,  -- JSON array of skills extracted by ChatGPT
    chatgpt_extracted_location,  -- Normalized location extracted by ChatGPT
    chatgpt_enriched_at,  -- Timestamp when ChatGPT enrichment was completed
    enrichment_status, -- JSONB tracking which enrichment fields have been processed: {"skills_enriched": boolean, "seniority_enriched": boolean, "remote_type_enriched": boolean, "salary_enriched": boolean, "chatgpt_enriched": boolean}
    dwh_load_date,
    dwh_load_timestamp,
    dwh_source_system
from enrichment_preserved

