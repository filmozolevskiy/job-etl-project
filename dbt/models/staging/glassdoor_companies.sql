{{ config(
    materialized='table'
) }}

-- Staging layer: Normalized company data from Glassdoor
-- Extracts and cleans data from raw.glassdoor_companies JSON payloads
-- Deduplicates on glassdoor_company_id
-- 
-- Updated based on actual API payload inspection (2025-12-07)
-- Added additional useful fields: year_founded, stock, additional ratings, links

with raw_data as (
    select
        glassdoor_companies_key,
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
        glassdoor_companies_key,
        company_lookup_key,
        
        -- Extract glassdoor_company_id (natural key from Glassdoor)
        (raw_payload->>'company_id')::integer as glassdoor_company_id,
        
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
        (raw_payload->>'year_founded')::integer as year_founded,
        raw_payload->>'stock' as stock,
        
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
        (raw_payload->>'senior_management_rating')::numeric as senior_management_rating,
        (raw_payload->>'work_life_balance_rating')::numeric as work_life_balance_rating,
        
        -- CEO information
        raw_payload->>'ceo' as ceo,
        
        -- Links
        raw_payload->>'company_link' as company_link,
        raw_payload->>'logo' as logo,
        raw_payload->>'reviews_link' as reviews_link,
        raw_payload->>'jobs_link' as jobs_link,
        raw_payload->>'faq_link' as faq_link,
        
        -- Additional data (stored as JSONB for complex structures)
        raw_payload->'competitors' as competitors,  -- Array of competitor objects
        raw_payload->'office_locations' as office_locations,  -- Array of location objects
        raw_payload->'best_places_to_work_awards' as best_places_to_work_awards,  -- Array of award objects
        
        -- Technical columns
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system
        
    from raw_data
),

-- Deduplicate on glassdoor_company_id, keeping the most recent record
deduplicated as (
    select
        *,
        row_number() over (
            partition by glassdoor_company_id 
            order by dwh_load_timestamp desc
        ) as rn
    from extracted
    where glassdoor_company_id is not null
)

select
    glassdoor_companies_key,
    company_lookup_key,
    glassdoor_company_id,
    company_name,
    website,
    industry,
    company_description,
    company_size,
    company_size_category,
    company_type,
    revenue,
    year_founded,
    stock,
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
    senior_management_rating,
    work_life_balance_rating,
    ceo,
    company_link,
    logo,
    reviews_link,
    jobs_link,
    faq_link,
    competitors,
    office_locations,
    best_places_to_work_awards,
    dwh_load_date,
    dwh_load_timestamp,
    dwh_source_system
from deduplicated
where rn = 1

