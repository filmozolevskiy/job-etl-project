"""SQL queries for enricher service.

This module contains all SQL queries used by the JobEnricher service. Extracting
queries here improves maintainability, enables syntax highlighting, and makes
queries easier to review and test.
"""

# Query to get jobs that need enrichment (jobs where BOTH extracted_skills AND seniority_level are NULL)
# This ensures we only process jobs that haven't been enriched yet, avoiding infinite loops
GET_JOBS_TO_ENRICH = """
    SELECT
        jsearch_job_postings_key,
        jsearch_job_id,
        job_title,
        job_description
    FROM staging.jsearch_job_postings
    WHERE extracted_skills IS NULL
        AND seniority_level IS NULL
        AND job_description IS NOT NULL
        AND trim(job_description) != ''
    ORDER BY dwh_load_timestamp DESC
    LIMIT %s
"""

# Query to update job with extracted skills and seniority
UPDATE_JOB_ENRICHMENT = """
    UPDATE staging.jsearch_job_postings
    SET extracted_skills = %s,
        seniority_level = %s
    WHERE jsearch_job_postings_key = %s
"""

# Query to get all jobs for enrichment (no limit, for batch processing)
# Only selects jobs where BOTH extracted_skills AND seniority_level are NULL
GET_ALL_JOBS_TO_ENRICH = """
    SELECT
        jsearch_job_postings_key,
        jsearch_job_id,
        job_title,
        job_description
    FROM staging.jsearch_job_postings
    WHERE extracted_skills IS NULL
        AND seniority_level IS NULL
        AND job_description IS NOT NULL
        AND trim(job_description) != ''
    ORDER BY dwh_load_timestamp DESC
"""
