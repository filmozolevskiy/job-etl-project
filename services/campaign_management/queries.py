"""SQL queries for Campaign Management Service."""

GET_ALL_CAMPAIGNS = """
    SELECT
        pp.campaign_id,
        pp.user_id,
        pp.campaign_name,
        pp.is_active,
        pp.query,
        pp.location,
        pp.country,
        pp.email,
        pp.total_run_count,
        pp.last_run_at,
        pp.last_run_status,
        pp.last_run_job_count,
        pp.created_at,
        pp.updated_at,
        u.username
    FROM marts.job_campaigns pp
    LEFT JOIN marts.users u ON pp.user_id = u.user_id
    ORDER BY pp.campaign_id DESC
"""

GET_ALL_CAMPAIGNS_BY_USER = """
    SELECT
        pp.campaign_id,
        pp.user_id,
        pp.campaign_name,
        pp.is_active,
        pp.query,
        pp.location,
        pp.country,
        pp.email,
        pp.total_run_count,
        pp.last_run_at,
        pp.last_run_status,
        pp.last_run_job_count,
        pp.created_at,
        pp.updated_at,
        u.username
    FROM marts.job_campaigns pp
    LEFT JOIN marts.users u ON pp.user_id = u.user_id
    WHERE pp.user_id = %s
    ORDER BY pp.campaign_id DESC
"""

GET_CAMPAIGN_BY_ID = """
    SELECT
        pp.campaign_id,
        pp.user_id,
        pp.campaign_name,
        pp.is_active,
        pp.query,
        pp.location,
        pp.country,
        pp.date_window,
        pp.email,
        pp.skills,
        pp.min_salary,
        pp.max_salary,
        pp.currency,
        pp.remote_preference,
        pp.seniority,
        pp.company_size_preference,
        pp.employment_type_preference,
        pp.ranking_weights,
        pp.total_run_count,
        pp.last_run_at,
        pp.last_run_status,
        pp.last_run_job_count,
        pp.created_at,
        pp.updated_at,
        u.username
    FROM marts.job_campaigns pp
    LEFT JOIN marts.users u ON pp.user_id = u.user_id
    WHERE pp.campaign_id = %s
"""

GET_NEXT_CAMPAIGN_ID = """
    SELECT nextval('marts.job_campaigns_campaign_id_seq') as next_id
"""

INSERT_CAMPAIGN = """
    INSERT INTO marts.job_campaigns (
        campaign_id,
        user_id,
        campaign_name,
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
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 'pending'
    )
    RETURNING campaign_id
"""

UPDATE_CAMPAIGN = """
    UPDATE marts.job_campaigns SET
        campaign_name = %s,
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
    WHERE campaign_id = %s
"""

GET_CAMPAIGN_NAME = """
    SELECT campaign_name FROM marts.job_campaigns WHERE campaign_id = %s
"""

GET_CAMPAIGN_ACTIVE_STATUS = """
    SELECT is_active FROM marts.job_campaigns WHERE campaign_id = %s
"""

TOGGLE_CAMPAIGN_ACTIVE = """
    UPDATE marts.job_campaigns
    SET is_active = %s, updated_at = %s
    WHERE campaign_id = %s
"""

DELETE_CAMPAIGN = """
    -- Delete campaign (CASCADE DELETE will automatically remove related data:
    -- - marts.dim_ranking (via FK constraint)
    -- - marts.fact_jobs (via FK constraint if exists, otherwise manual cleanup)
    -- - marts.etl_run_metrics (via FK constraint)
    -- 
    -- Note: Manual cleanup for fact_jobs and other tables without FK constraints
    -- is done in the delete_campaign method for safety
    DELETE FROM marts.job_campaigns WHERE campaign_id = %s
"""

UPDATE_CAMPAIGN_TRACKING_FIELDS = """
    UPDATE marts.job_campaigns
    SET
        last_run_at = NOW(),
        last_run_status = %s,
        last_run_job_count = %s,
        total_run_count = COALESCE(total_run_count, 0) + 1,
        updated_at = NOW()
    WHERE campaign_id = %s
"""

UPDATE_CAMPAIGN_TRACKING_STATUS_ONLY = """
    UPDATE marts.job_campaigns
    SET
        last_run_at = NOW(),
        last_run_status = %s,
        updated_at = NOW()
    WHERE campaign_id = %s
"""

# Query to get campaign statistics
GET_CAMPAIGN_STATISTICS = """
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
    FROM marts.job_campaigns pp
    LEFT JOIN marts.dim_ranking dr ON pp.campaign_id = dr.campaign_id
    LEFT JOIN marts.etl_run_metrics erm ON pp.campaign_id = erm.campaign_id
    WHERE pp.campaign_id = %s
    GROUP BY pp.campaign_id
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
    WHERE campaign_id = %s
    ORDER BY run_timestamp DESC
    LIMIT 20
"""

# Query to get job counts over time for chart
GET_JOB_COUNTS_OVER_TIME = """
    SELECT
        DATE(run_timestamp) as run_date,
        SUM(rows_processed_raw) as job_count
    FROM marts.etl_run_metrics
    WHERE campaign_id = %s
        AND task_name = 'extract_job_postings'
        AND run_timestamp >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY DATE(run_timestamp)
    ORDER BY run_date ASC
"""
