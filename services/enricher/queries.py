"""SQL queries for enricher service.

This module contains all SQL queries used by the JobEnricher service. Extracting
queries here improves maintainability, enables syntax highlighting, and makes
queries easier to review and test.
"""

# Query to get jobs that need enrichment (jobs where ANY enrichment status flag is false)
# This allows partial enrichment - jobs can be updated if they're missing skills, seniority,
# remote type, or salary information. Also fetches current enrichment values and status to
# preserve existing data.
GET_JOBS_TO_ENRICH = """
    SELECT
        jsearch_job_postings_key,
        jsearch_job_id,
        job_title,
        job_description,
        job_country,
        extracted_skills,
        seniority_level,
        remote_work_type,
        job_min_salary,
        job_max_salary,
        job_salary_period,
        job_salary_currency,
        enrichment_status
    FROM staging.jsearch_job_postings
    WHERE (
        COALESCE((enrichment_status->>'skills_enriched')::boolean, false) = false
        OR COALESCE((enrichment_status->>'seniority_enriched')::boolean, false) = false
        OR COALESCE((enrichment_status->>'remote_type_enriched')::boolean, false) = false
        OR COALESCE((enrichment_status->>'salary_enriched')::boolean, false) = false
    )
        AND job_description IS NOT NULL
        AND trim(job_description) != ''
        -- Filter by campaign_id if provided (None means process all campaigns)
        -- Note: campaign_id parameter is passed twice: once for NULL check, once for equality check
        -- This allows the query to work for both filtered (campaign_id provided) and unfiltered (None) cases
        AND (%s IS NULL OR campaign_id = %s)
    ORDER BY dwh_load_timestamp DESC
    LIMIT %s
"""

# Query to update job with extracted skills, seniority, remote work type, salary info,
# and enrichment status. Updates enrichment_status using JSONB merge operator to set
# flags to true for processed fields.
UPDATE_JOB_ENRICHMENT = """
    UPDATE staging.jsearch_job_postings
    SET extracted_skills = COALESCE(%s, extracted_skills),
        seniority_level = COALESCE(%s, seniority_level),
        remote_work_type = COALESCE(%s, remote_work_type),
        job_min_salary   = COALESCE(%s, job_min_salary),
        job_max_salary   = COALESCE(%s, job_max_salary),
        job_salary_period = COALESCE(%s, job_salary_period),
        job_salary_currency = COALESCE(%s, job_salary_currency),
        enrichment_status = enrichment_status || %s::jsonb
    WHERE jsearch_job_postings_key = %s
"""

# Query to get all jobs for enrichment (no limit, for batch processing).
# Selects jobs where ANY enrichment status flag is false (allows partial enrichment)
# and fetches current enrichment values and status to preserve existing data.
GET_ALL_JOBS_TO_ENRICH = """
    SELECT
        jsearch_job_postings_key,
        jsearch_job_id,
        job_title,
        job_description,
        job_country,
        extracted_skills,
        seniority_level,
        remote_work_type,
        job_min_salary,
        job_max_salary,
        job_salary_period,
        job_salary_currency,
        enrichment_status
    FROM staging.jsearch_job_postings
    WHERE (
        COALESCE((enrichment_status->>'skills_enriched')::boolean, false) = false
        OR COALESCE((enrichment_status->>'seniority_enriched')::boolean, false) = false
        OR COALESCE((enrichment_status->>'remote_type_enriched')::boolean, false) = false
        OR COALESCE((enrichment_status->>'salary_enriched')::boolean, false) = false
    )
        AND job_description IS NOT NULL
        AND trim(job_description) != ''
        -- Filter by campaign_id if provided (None means process all campaigns)
        -- Note: campaign_id parameter is passed twice: once for NULL check, once for equality check
        -- This allows the query to work for both filtered (campaign_id provided) and unfiltered (None) cases
        AND (%s IS NULL OR campaign_id = %s)
    ORDER BY dwh_load_timestamp DESC
"""
