{{ config(
    materialized='table',
    schema='marts'
) }}

-- Marts layer: Dimension Companies
-- One row per distinct company
-- Built from staging.glassdoor_companies
-- Surrogate key: company_key
-- Natural keys: glassdoor_company_id (from Glassdoor), normalized company_name

with staging_companies as (
    select
        glassdoor_company_id,
        company_name,
        company_size,
        year_founded,
        rating,
        job_count,
        career_opportunities_rating,
        compensation_and_benefits_rating,
        culture_and_values_rating,
        work_life_balance_rating,
        company_link,
        logo,
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system
    from {{ ref('glassdoor_companies') }}
    where glassdoor_company_id is not null
),

-- Generate surrogate key and normalize company name
with_keys as (
    select
        -- Surrogate key: hash of glassdoor_company_id and normalized name
        md5(
            coalesce(glassdoor_company_id::text, '') || '|' || 
            coalesce(lower(trim(company_name)), '')
        ) as company_key,
        
        -- Natural keys
        glassdoor_company_id,
        lower(trim(company_name)) as normalized_company_name,
        
        -- Essential company attributes
        company_name,
        company_size,
        year_founded,
        rating,
        job_count,
        career_opportunities_rating,
        compensation_and_benefits_rating,
        culture_and_values_rating,
        work_life_balance_rating,
        company_link,
        logo,
        
        -- Technical columns
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system,
        
        -- Keep most recent record per company
        row_number() over (
            partition by glassdoor_company_id 
            order by dwh_load_timestamp desc
        ) as rn
        
    from staging_companies
)

select
    company_key,
    glassdoor_company_id,
    normalized_company_name,
    company_name,
    company_size,
    year_founded,
    rating,
    job_count,
    career_opportunities_rating,
    compensation_and_benefits_rating,
    culture_and_values_rating,
    work_life_balance_rating,
    company_link,
    logo,
    dwh_load_date,
    dwh_load_timestamp,
    dwh_source_system
from with_keys
where rn = 1
