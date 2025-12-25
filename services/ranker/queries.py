"""SQL queries for ranker service.

This module contains all SQL queries used by the JobRanker service. Extracting
queries here improves maintainability, enables syntax highlighting, and makes
queries easier to review and test.
"""

# Query to get active profiles for ranking
GET_ACTIVE_PROFILES_FOR_RANKING = """
    SELECT
        profile_id,
        profile_name,
        query,
        location,
        country,
        skills,
        min_salary,
        max_salary,
        currency,
        remote_preference,
        seniority,
        company_size_preference,
        employment_type_preference
    FROM marts.profile_preferences
    WHERE is_active = true
    ORDER BY profile_id
"""

# Query to get jobs for a specific profile
GET_JOBS_FOR_PROFILE = """
    SELECT
        fj.jsearch_job_id,
        fj.job_title,
        fj.job_location,
        fj.job_employment_type,
        fj.job_is_remote,
        fj.job_posted_at_datetime_utc,
        fj.company_key,
        -- Enriched fields
        fj.extracted_skills,
        fj.seniority_level,
        fj.remote_work_type,
        fj.job_min_salary,
        fj.job_max_salary,
        fj.job_salary_period,
        fj.job_salary_currency,
        -- Company size from dim_companies
        dc.company_size
    FROM marts.fact_jobs fj
    LEFT JOIN marts.dim_companies dc ON fj.company_key = dc.company_key
    WHERE fj.profile_id = %s
    ORDER BY fj.job_posted_at_datetime_utc DESC NULLS LAST
"""

# Query to insert/update rankings in marts.dim_ranking
INSERT_RANKINGS = """
    INSERT INTO marts.dim_ranking (
        jsearch_job_id,
        profile_id,
        rank_score,
        ranked_at,
        ranked_date,
        dwh_load_timestamp,
        dwh_source_system
    ) VALUES %s
    ON CONFLICT (jsearch_job_id, profile_id)
    DO UPDATE SET
        rank_score = EXCLUDED.rank_score,
        ranked_at = EXCLUDED.ranked_at,
        ranked_date = EXCLUDED.ranked_date,
        dwh_load_timestamp = EXCLUDED.dwh_load_timestamp,
        dwh_source_system = EXCLUDED.dwh_source_system
"""
