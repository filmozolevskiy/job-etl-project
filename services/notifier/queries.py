"""SQL queries for notifier services.

This module contains all SQL queries used by the notification services,
such as NotificationCoordinator. Extracting queries here improves
maintainability, enables syntax highlighting, and makes queries easier to
review and test.
"""

# Query to get active campaigns with email addresses for notifications
GET_ACTIVE_CAMPAIGNS_WITH_EMAIL = """
    SELECT
        campaign_id,
        campaign_name,
        email,
        query
    FROM marts.job_campaigns
    WHERE is_active = true
        AND email IS NOT NULL
        AND email != ''
    ORDER BY campaign_id
"""

# Query to get top ranked jobs with details for a specific campaign
GET_TOP_RANKED_JOBS_FOR_CAMPAIGN = """
    SELECT
        dr.jsearch_job_id,
        dr.campaign_id,
        dr.rank_score,
        fj.job_title,
        fj.job_location,
        fj.employment_type,
        fj.remote_work_type,
        fj.job_posted_at_datetime_utc,
        COALESCE(dc.company_name, fj.employer_name) as company_name,
        fj.job_apply_link as apply_link
    FROM marts.dim_ranking dr
    INNER JOIN marts.fact_jobs fj
        ON dr.jsearch_job_id = fj.jsearch_job_id
        AND dr.campaign_id = fj.campaign_id
    LEFT JOIN marts.dim_companies dc
        ON fj.company_key = dc.company_key
    WHERE dr.campaign_id = %s
    ORDER BY dr.rank_score DESC, dr.ranked_at DESC
    LIMIT %s
"""
