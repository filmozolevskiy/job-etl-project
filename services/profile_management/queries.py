"""SQL queries for Profile Management Service."""

GET_ALL_PROFILES = """
    SELECT
        profile_id,
        profile_name,
        is_active,
        query,
        location,
        country,
        email,
        total_run_count,
        last_run_at,
        last_run_status,
        last_run_job_count,
        created_at,
        updated_at
    FROM marts.profile_preferences
    ORDER BY profile_id DESC
"""

GET_PROFILE_BY_ID = """
    SELECT
        profile_id,
        profile_name,
        is_active,
        query,
        location,
        country,
        date_window,
        email,
        skills,
        min_salary,
        max_salary,
        currency,
        remote_preference,
        seniority,
        company_size_preference,
        employment_type_preference,
        ranking_weights,
        total_run_count,
        last_run_at,
        last_run_status,
        last_run_job_count,
        created_at,
        updated_at
    FROM marts.profile_preferences
    WHERE profile_id = %s
"""

GET_NEXT_PROFILE_ID = """
    SELECT COALESCE(MAX(profile_id), 0) + 1 as next_id
    FROM marts.profile_preferences
"""

INSERT_PROFILE = """
    INSERT INTO marts.profile_preferences (
        profile_id,
        profile_name,
        is_active,
        query,
        location,
        country,
        date_window,
        email,
        skills,
        min_salary,
        max_salary,
        currency,
        remote_preference,
        seniority,
        company_size_preference,
        employment_type_preference,
        ranking_weights,
        created_at,
        updated_at,
        total_run_count,
        last_run_status
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 'pending'
    )
"""

UPDATE_PROFILE = """
    UPDATE marts.profile_preferences SET
        profile_name = %s,
        is_active = %s,
        query = %s,
        location = %s,
        country = %s,
        date_window = %s,
        email = %s,
        skills = %s,
        min_salary = %s,
        max_salary = %s,
        currency = %s,
        remote_preference = %s,
        seniority = %s,
        company_size_preference = %s,
        employment_type_preference = %s,
        ranking_weights = %s,
        updated_at = %s
    WHERE profile_id = %s
"""

GET_PROFILE_NAME = """
    SELECT profile_name FROM marts.profile_preferences WHERE profile_id = %s
"""

GET_PROFILE_ACTIVE_STATUS = """
    SELECT is_active FROM marts.profile_preferences WHERE profile_id = %s
"""

TOGGLE_PROFILE_ACTIVE = """
    UPDATE marts.profile_preferences
    SET is_active = %s, updated_at = %s
    WHERE profile_id = %s
"""

DELETE_PROFILE = """
    DELETE FROM marts.profile_preferences WHERE profile_id = %s
"""

UPDATE_PROFILE_TRACKING_FIELDS = """
    UPDATE marts.profile_preferences
    SET
        last_run_at = NOW(),
        last_run_status = %s,
        last_run_job_count = %s,
        total_run_count = COALESCE(total_run_count, 0) + 1,
        updated_at = NOW()
    WHERE profile_id = %s
"""

UPDATE_PROFILE_TRACKING_STATUS_ONLY = """
    UPDATE marts.profile_preferences
    SET
        last_run_at = NOW(),
        last_run_status = %s,
        updated_at = NOW()
    WHERE profile_id = %s
"""

# Query to get profile statistics
GET_PROFILE_STATISTICS = """
    SELECT
        -- Average ranking score
        COALESCE(AVG(dr.rank_score), 0) as avg_rank_score,
        COUNT(DISTINCT dr.jsearch_job_id) as total_ranked_jobs,
        -- Run history from ETL metrics
        COUNT(DISTINCT erm.run_id) as total_etl_runs,
        SUM(CASE WHEN erm.task_status = 'success' THEN 1 ELSE 0 END) as successful_runs,
        SUM(CASE WHEN erm.task_status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
        -- Job counts over time (last 30 days)
        SUM(CASE WHEN erm.run_timestamp >= CURRENT_DATE - INTERVAL '30 days'
                 AND erm.task_name = 'extract_job_postings'
                 THEN erm.rows_processed_raw ELSE 0 END) as jobs_last_30_days
    FROM marts.profile_preferences pp
    LEFT JOIN marts.dim_ranking dr ON pp.profile_id = dr.profile_id
    LEFT JOIN marts.etl_run_metrics erm ON pp.profile_id = erm.profile_id
    WHERE pp.profile_id = %s
    GROUP BY pp.profile_id
"""

# Query to get run history
GET_RUN_HISTORY = """
    SELECT
        run_timestamp,
        task_name,
        task_status,
        rows_processed_raw,
        rows_processed_marts,
        processing_duration_seconds,
        error_message
    FROM marts.etl_run_metrics
    WHERE profile_id = %s
    ORDER BY run_timestamp DESC
    LIMIT 20
"""

# Query to get job counts over time for chart
GET_JOB_COUNTS_OVER_TIME = """
    SELECT
        DATE(run_timestamp) as run_date,
        SUM(rows_processed_raw) as job_count
    FROM marts.etl_run_metrics
    WHERE profile_id = %s
        AND task_name = 'extract_job_postings'
        AND run_timestamp >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY DATE(run_timestamp)
    ORDER BY run_date ASC
"""
