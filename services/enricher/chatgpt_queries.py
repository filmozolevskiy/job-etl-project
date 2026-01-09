"""SQL queries for ChatGPT enrichment service.

This module contains all SQL queries used by the ChatGPTEnricher service.
"""

# Query to get jobs that need ChatGPT enrichment
# Jobs are eligible if they don't have a record in staging.chatgpt_enrichments yet
# and have a job description
# Includes additional fields to help extract seniority, remote work type, and salary
GET_JOBS_FOR_CHATGPT_ENRICHMENT = """
    SELECT
        jp.jsearch_job_postings_key,
        jp.jsearch_job_id,
        jp.job_title,
        jp.job_description,
        jp.job_location,
        jp.job_city,
        jp.job_state,
        jp.job_country,
        jp.employer_name,
        jp.job_min_salary,
        jp.job_max_salary,
        jp.job_salary_period,
        jp.job_is_remote,
        jp.job_employment_type
    FROM staging.jsearch_job_postings jp
    LEFT JOIN staging.chatgpt_enrichments ce
        ON jp.jsearch_job_postings_key = ce.jsearch_job_postings_key
    WHERE ce.jsearch_job_postings_key IS NULL
        AND jp.job_description IS NOT NULL
        AND trim(jp.job_description) != ''
        -- Filter by campaign_id if provided (None means process all campaigns)
        AND (%s IS NULL OR jp.campaign_id = %s)
    ORDER BY jp.dwh_load_timestamp DESC
    LIMIT %s
"""

# Query to get all jobs for ChatGPT enrichment (no limit, for batch processing)
GET_ALL_JOBS_FOR_CHATGPT_ENRICHMENT = """
    SELECT
        jp.jsearch_job_postings_key,
        jp.jsearch_job_id,
        jp.job_title,
        jp.job_description,
        jp.job_location,
        jp.job_city,
        jp.job_state,
        jp.job_country,
        jp.employer_name,
        jp.job_min_salary,
        jp.job_max_salary,
        jp.job_salary_period,
        jp.job_is_remote,
        jp.job_employment_type
    FROM staging.jsearch_job_postings jp
    LEFT JOIN staging.chatgpt_enrichments ce
        ON jp.jsearch_job_postings_key = ce.jsearch_job_postings_key
    WHERE ce.jsearch_job_postings_key IS NULL
        AND jp.job_description IS NOT NULL
        AND trim(jp.job_description) != ''
        -- Filter by campaign_id if provided (None means process all campaigns)
        AND (%s IS NULL OR jp.campaign_id = %s)
    ORDER BY jp.dwh_load_timestamp DESC
"""

# Query to upsert ChatGPT enrichment data into staging.chatgpt_enrichments
# Uses INSERT ... ON CONFLICT UPDATE for idempotent upserts
# Includes all enrichment fields: summary, skills, location, seniority, remote work type, salary
UPDATE_CHATGPT_ENRICHMENT = """
    INSERT INTO staging.chatgpt_enrichments (
        jsearch_job_postings_key,
        job_summary,
        chatgpt_extracted_skills,
        chatgpt_extracted_location,
        chatgpt_seniority_level,
        chatgpt_remote_work_type,
        chatgpt_job_min_salary,
        chatgpt_job_max_salary,
        chatgpt_salary_period,
        chatgpt_salary_currency,
        chatgpt_enriched_at,
        chatgpt_enrichment_status,
        dwh_load_date,
        dwh_load_timestamp
    )
    VALUES (
        %s,  -- jsearch_job_postings_key
        %s,  -- job_summary
        %s,  -- chatgpt_extracted_skills (JSONB)
        %s,  -- chatgpt_extracted_location
        %s,  -- chatgpt_seniority_level
        %s,  -- chatgpt_remote_work_type
        %s,  -- chatgpt_job_min_salary
        %s,  -- chatgpt_job_max_salary
        %s,  -- chatgpt_salary_period
        %s,  -- chatgpt_salary_currency
        CURRENT_TIMESTAMP,  -- chatgpt_enriched_at
        %s,  -- chatgpt_enrichment_status (JSONB)
        CURRENT_DATE,  -- dwh_load_date
        CURRENT_TIMESTAMP  -- dwh_load_timestamp
    )
    ON CONFLICT (jsearch_job_postings_key)
    DO UPDATE SET
        job_summary = COALESCE(EXCLUDED.job_summary, staging.chatgpt_enrichments.job_summary),
        chatgpt_extracted_skills = COALESCE(EXCLUDED.chatgpt_extracted_skills, staging.chatgpt_enrichments.chatgpt_extracted_skills),
        chatgpt_extracted_location = COALESCE(EXCLUDED.chatgpt_extracted_location, staging.chatgpt_enrichments.chatgpt_extracted_location),
        chatgpt_seniority_level = COALESCE(EXCLUDED.chatgpt_seniority_level, staging.chatgpt_enrichments.chatgpt_seniority_level),
        chatgpt_remote_work_type = COALESCE(EXCLUDED.chatgpt_remote_work_type, staging.chatgpt_enrichments.chatgpt_remote_work_type),
        chatgpt_job_min_salary = COALESCE(EXCLUDED.chatgpt_job_min_salary, staging.chatgpt_enrichments.chatgpt_job_min_salary),
        chatgpt_job_max_salary = COALESCE(EXCLUDED.chatgpt_job_max_salary, staging.chatgpt_enrichments.chatgpt_job_max_salary),
        chatgpt_salary_period = COALESCE(EXCLUDED.chatgpt_salary_period, staging.chatgpt_enrichments.chatgpt_salary_period),
        chatgpt_salary_currency = COALESCE(EXCLUDED.chatgpt_salary_currency, staging.chatgpt_enrichments.chatgpt_salary_currency),
        chatgpt_enriched_at = CURRENT_TIMESTAMP,
        chatgpt_enrichment_status = COALESCE(staging.chatgpt_enrichments.chatgpt_enrichment_status, '{}'::jsonb) || EXCLUDED.chatgpt_enrichment_status,
        dwh_load_timestamp = CURRENT_TIMESTAMP
"""
