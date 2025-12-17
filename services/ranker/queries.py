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
        remote_preference,
        seniority
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
        fj.company_key
    FROM marts.fact_jobs fj
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

