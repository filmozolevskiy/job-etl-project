"""SQL queries for ranker service.

This module contains all SQL queries used by the JobRanker service. Extracting
queries here improves maintainability, enables syntax highlighting, and makes
queries easier to review and test.
"""

# Query to get active campaigns for ranking
GET_ACTIVE_CAMPAIGNS_FOR_RANKING = """
    SELECT
        campaign_id,
        campaign_name,
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
        employment_type_preference,
        -- Ranking weights (JSONB, percentages should sum to 100%)
        ranking_weights
    FROM marts.job_campaigns
    WHERE is_active = true
    ORDER BY campaign_id
"""

# Query to get jobs for a specific campaign
GET_JOBS_FOR_CAMPAIGN = """
    SELECT
        fj.jsearch_job_id,
        fj.job_title,
        fj.job_location,
        fj.employment_type,
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
    WHERE fj.campaign_id = %s
    ORDER BY fj.job_posted_at_datetime_utc DESC NULLS LAST
"""

# Query to validate that a job exists in fact_jobs
VALIDATE_JOB_EXISTS = """
    SELECT COUNT(*) as job_count
    FROM marts.fact_jobs
    WHERE jsearch_job_id = %s
        AND campaign_id = %s
"""

# Query to insert/update rankings in marts.dim_ranking
INSERT_RANKINGS = """
    INSERT INTO marts.dim_ranking (
        jsearch_job_id,
        campaign_id,
        rank_score,
        rank_explain,
        ranked_at,
        ranked_date,
        dwh_load_timestamp,
        dwh_source_system
    ) VALUES %s
    ON CONFLICT (jsearch_job_id, campaign_id)
    DO UPDATE SET
        rank_score = EXCLUDED.rank_score,
        rank_explain = EXCLUDED.rank_explain,
        ranked_at = EXCLUDED.ranked_at,
        ranked_date = EXCLUDED.ranked_date,
        dwh_load_timestamp = EXCLUDED.dwh_load_timestamp,
        dwh_source_system = EXCLUDED.dwh_source_system
"""
