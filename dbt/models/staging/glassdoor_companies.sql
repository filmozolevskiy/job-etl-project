{{ config(
    materialized='table'
) }}

-- Staging layer: Normalized company data from Glassdoor
-- Extracts and cleans data from raw.glassdoor_companies JSON payloads
-- Deduplicates on company_id

with raw_data as (
    select
        raw_company_id,
        raw_payload,
        company_lookup_key,
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system
    from {{ ref('raw_glassdoor_companies') }}
    where raw_payload is not null
),

extracted as (
    select
        raw_company_id,
        company_lookup_key,
        
        -- Extract company_id (natural key from Glassdoor)
        (raw_payload->>'company_id')::integer as company_id,
        
        -- Basic company information
        raw_payload->>'name' as company_name,
        raw_payload->>'website' as website,
        raw_payload->>'industry' as industry,
        raw_payload->>'company_description' as company_description,
        
        -- Company size
        raw_payload->>'company_size' as company_size,
        raw_payload->>'company_size_category' as company_size_category,
        raw_payload->>'company_type' as company_type,
        raw_payload->>'revenue' as revenue,
        
        -- Location
        raw_payload->>'headquarters_location' as headquarters_location,
        
        -- Ratings
        (raw_payload->>'rating')::numeric as rating,
        (raw_payload->>'review_count')::integer as review_count,
        (raw_payload->>'salary_count')::integer as salary_count,
        (raw_payload->>'job_count')::integer as job_count,
        (raw_payload->>'business_outlook_rating')::numeric as business_outlook_rating,
        (raw_payload->>'career_opportunities_rating')::numeric as career_opportunities_rating,
        (raw_payload->>'compensation_and_benefits_rating')::numeric as compensation_and_benefits_rating,
        (raw_payload->>'culture_and_values_rating')::numeric as culture_and_values_rating,
        (raw_payload->>'diversity_and_inclusion_rating')::numeric as diversity_and_inclusion_rating,
        (raw_payload->>'recommend_to_friend_rating')::numeric as recommend_to_friend_rating,
        (raw_payload->>'ceo_rating')::numeric as ceo_rating,
        
        -- CEO information
        raw_payload->>'ceo' as ceo,
        
        -- Links
        raw_payload->>'company_link' as company_link,
        raw_payload->>'logo' as logo,
        
        -- Technical columns
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system
        
    from raw_data
),

-- Deduplicate on company_id, keeping the most recent record
deduplicated as (
    select
        *,
        row_number() over (
            partition by company_id 
            order by dwh_load_timestamp desc
        ) as rn
    from extracted
    where company_id is not null
)

select
    raw_company_id,
    company_lookup_key,
    company_id,
    company_name,
    website,
    industry,
    company_description,
    company_size,
    company_size_category,
    company_type,
    revenue,
    headquarters_location,
    rating,
    review_count,
    salary_count,
    job_count,
    business_outlook_rating,
    career_opportunities_rating,
    compensation_and_benefits_rating,
    culture_and_values_rating,
    diversity_and_inclusion_rating,
    recommend_to_friend_rating,
    ceo_rating,
    ceo,
    company_link,
    logo,
    dwh_load_date,
    dwh_load_timestamp,
    dwh_source_system
from deduplicated
where rn = 1

