"""SQL queries for job viewing and job notes."""

# Query to get jobs with rankings, companies, notes, and status for a campaign.
# Uses INNER JOIN fact_jobs so we only show jobs that have full gold data (title,
# company, location, etc.). Jobs in dim_ranking without fact_jobs are not shown
# to avoid "Unknown" placeholders in the UI.
# Note: The rejected filter is applied conditionally in the service method
GET_JOBS_FOR_CAMPAIGN_BASE = """
    SELECT
        jsearch_job_id,
        campaign_id,
        rank_score,
        rank_explain,
        ranked_at,
        job_title,
        job_location,
        employment_type,
        job_posted_at_datetime_utc,
        apply_options,
        job_apply_link,
        job_publisher,
        extracted_skills,
        job_min_salary,
        job_max_salary,
        job_salary_currency,
        remote_work_type,
        company_name,
        company_size,
        rating,
        company_link,
        company_logo,
        note_count,
        job_status,
        user_applied_to_company,
        job_summary,
        seniority_level
    FROM (
        SELECT DISTINCT ON (dr.jsearch_job_id)
            dr.jsearch_job_id,
            dr.campaign_id,
            dr.rank_score,
            dr.rank_explain,
            dr.ranked_at,
            fj.job_title,
            fj.job_location,
            fj.employment_type,
            fj.job_posted_at_datetime_utc,
            fj.apply_options,
            fj.job_apply_link,
            fj.job_publisher,
            fj.job_summary,
            fj.extracted_skills,
            fj.job_min_salary,
            fj.job_max_salary,
            fj.job_salary_period,
            fj.job_salary_currency,
            fj.remote_work_type,
            fj.seniority_level,
            fj.employer_name,
            COALESCE(dc.company_name, fj.employer_name) as company_name,
            dc.company_size,
            dc.rating,
            dc.company_link,
            dc.logo as company_logo,
            COALESCE(jn.note_count, 0) as note_count,
            COALESCE(ujs.status, 'waiting') as job_status,
            (fj.company_key IS NOT NULL AND EXISTS (
                SELECT 1
                FROM marts.fact_jobs fj2
                INNER JOIN marts.user_job_status ujs2
                    ON fj2.jsearch_job_id = ujs2.jsearch_job_id AND ujs2.user_id = %s
                WHERE fj2.company_key = fj.company_key
                  AND ujs2.status != 'waiting'
            )) as user_applied_to_company
        FROM marts.dim_ranking dr
        INNER JOIN marts.job_campaigns jc
            ON dr.campaign_id = jc.campaign_id
        INNER JOIN marts.fact_jobs fj
            ON dr.jsearch_job_id = fj.jsearch_job_id
            AND dr.campaign_id = fj.campaign_id
        LEFT JOIN marts.dim_companies dc
            ON fj.company_key = dc.company_key
        LEFT JOIN (
            SELECT jsearch_job_id, user_id, COUNT(*) as note_count
            FROM marts.job_notes
            GROUP BY jsearch_job_id, user_id
        ) jn ON dr.jsearch_job_id = jn.jsearch_job_id AND jn.user_id = %s
        LEFT JOIN marts.user_job_status ujs
            ON dr.jsearch_job_id = ujs.jsearch_job_id
            AND ujs.user_id = %s
        WHERE dr.campaign_id = %s
        ORDER BY dr.jsearch_job_id, dr.rank_score DESC NULLS LAST, dr.ranked_at DESC NULLS LAST
    ) ranked_jobs
    ORDER BY rank_score DESC NULLS LAST, ranked_at DESC NULLS LAST
"""

# Query to get jobs for all user's campaigns
# Note: The rejected filter is applied conditionally in the service method
GET_JOBS_FOR_USER_BASE = """
    SELECT
        jsearch_job_id,
        campaign_id,
        campaign_name,
        rank_score,
        rank_explain,
        ranked_at,
        job_title,
        job_location,
        employment_type,
        job_posted_at_datetime_utc,
        apply_options,
        job_apply_link,
        job_publisher,
        extracted_skills,
        job_min_salary,
        job_max_salary,
        job_salary_currency,
        remote_work_type,
        company_name,
        company_size,
        rating,
        company_link,
        company_logo,
        note_count,
        job_status,
        user_applied_to_company,
        job_summary,
        seniority_level
    FROM (
        SELECT DISTINCT ON (dr.jsearch_job_id, dr.campaign_id)
            dr.jsearch_job_id,
            dr.campaign_id,
            jc.campaign_name,
            dr.rank_score,
            dr.rank_explain,
            dr.ranked_at,
            fj.job_title,
            fj.job_location,
            fj.employment_type,
            fj.job_posted_at_datetime_utc,
            fj.apply_options,
            fj.job_apply_link,
            fj.job_publisher,
            fj.job_summary,
            fj.extracted_skills,
            fj.job_min_salary,
            fj.job_max_salary,
            fj.job_salary_period,
            fj.job_salary_currency,
            fj.remote_work_type,
            fj.seniority_level,
            fj.employer_name,
            COALESCE(dc.company_name, fj.employer_name) as company_name,
            dc.company_size,
            dc.rating,
            dc.company_link,
            dc.logo as company_logo,
            COALESCE(jn.note_count, 0) as note_count,
            COALESCE(ujs.status, 'waiting') as job_status,
            (fj.company_key IS NOT NULL AND EXISTS (
                SELECT 1
                FROM marts.fact_jobs fj2
                INNER JOIN marts.user_job_status ujs2
                    ON fj2.jsearch_job_id = ujs2.jsearch_job_id AND ujs2.user_id = %s
                WHERE fj2.company_key = fj.company_key
                  AND ujs2.status != 'waiting'
            )) as user_applied_to_company
        FROM marts.dim_ranking dr
        INNER JOIN marts.fact_jobs fj
            ON dr.jsearch_job_id = fj.jsearch_job_id
            AND dr.campaign_id = fj.campaign_id
        INNER JOIN marts.job_campaigns jc
            ON dr.campaign_id = jc.campaign_id
        LEFT JOIN marts.dim_companies dc
            ON fj.company_key = dc.company_key
        LEFT JOIN (
            SELECT jsearch_job_id, user_id, COUNT(*) as note_count
            FROM marts.job_notes
            GROUP BY jsearch_job_id, user_id
        ) jn ON dr.jsearch_job_id = jn.jsearch_job_id AND jn.user_id = %s
        LEFT JOIN marts.user_job_status ujs
            ON dr.jsearch_job_id = ujs.jsearch_job_id
            AND ujs.user_id = %s
        WHERE jc.user_id = %s
        ORDER BY dr.jsearch_job_id, dr.campaign_id, dr.rank_score DESC NULLS LAST, dr.ranked_at DESC NULLS LAST
    ) ranked_jobs
    ORDER BY rank_score DESC NULLS LAST, ranked_at DESC NULLS LAST
"""

# Query to get all notes by job_id and user_id (ordered newest first)
GET_NOTES_BY_JOB_AND_USER = """
    SELECT
        note_id,
        jsearch_job_id,
        user_id,
        note_text,
        created_at,
        updated_at
    FROM marts.job_notes
    WHERE jsearch_job_id = %s AND user_id = %s
    ORDER BY created_at DESC
"""

# Query to get a single note by note_id and user_id (for authorization)
GET_NOTE_BY_ID = """
    SELECT
        note_id,
        jsearch_job_id,
        user_id,
        note_text,
        created_at,
        updated_at
    FROM marts.job_notes
    WHERE note_id = %s AND user_id = %s
"""

# Query to insert a new note
INSERT_NOTE = """
    INSERT INTO marts.job_notes (jsearch_job_id, user_id, campaign_id, note_text, created_at, updated_at)
    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    RETURNING note_id
"""

# Query to update an existing note
UPDATE_NOTE = """
    UPDATE marts.job_notes
    SET note_text = %s, updated_at = CURRENT_TIMESTAMP
    WHERE note_id = %s AND user_id = %s
    RETURNING note_id
"""


# Query to delete a note
DELETE_NOTE = """
    DELETE FROM marts.job_notes
    WHERE note_id = %s AND user_id = %s
    RETURNING note_id
"""

# Query to get job status by job_id and user_id
GET_JOB_STATUS = """
    SELECT
        user_job_status_id,
        user_id,
        jsearch_job_id,
        status,
        created_at,
        updated_at
    FROM marts.user_job_status
    WHERE jsearch_job_id = %s AND user_id = %s
"""

# Query to upsert job status
UPSERT_JOB_STATUS = """
    INSERT INTO marts.user_job_status (jsearch_job_id, user_id, campaign_id, status, created_at, updated_at)
    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT (user_id, jsearch_job_id)
    DO UPDATE SET
        status = EXCLUDED.status,
        campaign_id = EXCLUDED.campaign_id,
        updated_at = CURRENT_TIMESTAMP
    RETURNING user_job_status_id
"""

# Query to get job counts for multiple campaigns.
# Count only jobs that exist in both dim_ranking and fact_jobs so the list
# matches what the campaign detail page shows (same JOIN as GET_JOBS_FOR_CAMPAIGN_BASE).
# Count only jobs that exist in both dim_ranking and fact_jobs (same set as
# campaign detail). Ensures we never show a count for jobs that would display
# as "Unknown" because fact_jobs is missing.
GET_JOB_COUNTS_FOR_CAMPAIGNS = """
    SELECT
        dr.campaign_id,
        COUNT(DISTINCT dr.jsearch_job_id) as job_count
    FROM marts.dim_ranking dr
    INNER JOIN marts.fact_jobs fj
        ON dr.jsearch_job_id = fj.jsearch_job_id
        AND dr.campaign_id = fj.campaign_id
    WHERE dr.campaign_id = ANY(%s::int[])
    GROUP BY dr.campaign_id
"""

# Query to get a single job by ID for a user
GET_JOB_BY_ID = """
    SELECT
        jsearch_job_id,
        campaign_id,
        rank_score,
        rank_explain,
        ranked_at,
        job_title,
        job_location,
        employment_type,
        job_posted_at_datetime_utc,
        apply_options,
        job_apply_link,
        job_google_link,
        job_publisher,
        extracted_skills,
        job_min_salary,
        job_max_salary,
        job_salary_period,
        job_salary_currency,
        remote_work_type,
        seniority_level,
        company_name,
        company_size,
        rating,
        company_link,
        company_logo,
        job_summary,
        campaign_count,
        campaign_names,
        note_count,
        job_status,
        user_applied_to_company
        FROM (
        SELECT DISTINCT ON (dr.jsearch_job_id)
            dr.jsearch_job_id,
            dr.campaign_id,
            dr.rank_score,
            dr.rank_explain,
            dr.ranked_at,
            fj.job_title,
            fj.job_location,
            fj.employment_type,
            fj.job_posted_at_datetime_utc,
            fj.apply_options,
            fj.job_apply_link,
            fj.job_google_link,
            fj.job_publisher,
            fj.extracted_skills,
            fj.job_min_salary,
            fj.job_max_salary,
            fj.job_salary_period,
            fj.job_salary_currency,
            fj.remote_work_type,
            fj.seniority_level,
            fj.employer_name,
            COALESCE(dc.company_name, fj.employer_name) as company_name,
            dc.company_size,
            dc.rating,
            dc.company_link,
            dc.logo as company_logo,
            fj.job_summary,
            (
                SELECT COUNT(DISTINCT dr2.campaign_id)
                FROM marts.dim_ranking dr2
                INNER JOIN marts.job_campaigns jc2
                    ON dr2.campaign_id = jc2.campaign_id
                WHERE dr2.jsearch_job_id = dr.jsearch_job_id
                    AND jc2.user_id = %s
            ) as campaign_count,
            (
                SELECT ARRAY_AGG(DISTINCT jc2.campaign_name ORDER BY jc2.campaign_name)
                FROM marts.dim_ranking dr2
                INNER JOIN marts.job_campaigns jc2
                    ON dr2.campaign_id = jc2.campaign_id
                WHERE dr2.jsearch_job_id = dr.jsearch_job_id
                    AND jc2.user_id = %s
            ) as campaign_names,
            COALESCE(jn.note_count, 0) as note_count,
            COALESCE(ujs.status, 'waiting') as job_status,
            (fj.company_key IS NOT NULL AND EXISTS (
                SELECT 1
                FROM marts.fact_jobs fj2
                INNER JOIN marts.user_job_status ujs2
                    ON fj2.jsearch_job_id = ujs2.jsearch_job_id AND ujs2.user_id = %s
                WHERE fj2.company_key = fj.company_key
                  AND ujs2.status != 'waiting'
            )) as user_applied_to_company
        FROM marts.dim_ranking dr
        INNER JOIN marts.fact_jobs fj
            ON dr.jsearch_job_id = fj.jsearch_job_id
            AND dr.campaign_id = fj.campaign_id
        INNER JOIN marts.job_campaigns jc
            ON dr.campaign_id = jc.campaign_id
        LEFT JOIN marts.dim_companies dc
            ON fj.company_key = dc.company_key
        LEFT JOIN (
            SELECT jsearch_job_id, user_id, COUNT(*) as note_count
            FROM marts.job_notes
            GROUP BY jsearch_job_id, user_id
        ) jn ON dr.jsearch_job_id = jn.jsearch_job_id AND jn.user_id = %s
        LEFT JOIN marts.user_job_status ujs
            ON dr.jsearch_job_id = ujs.jsearch_job_id
            AND ujs.user_id = %s
        WHERE dr.jsearch_job_id = %s
            AND jc.user_id = %s
        ORDER BY dr.jsearch_job_id, dr.rank_score DESC NULLS LAST, dr.ranked_at DESC NULLS LAST
    ) ranked_jobs
    LIMIT 1
"""

# Same-company jobs for job details: other jobs from the same company (same company_key)
# in the user's campaigns, with user's application status. Excludes the current job.
GET_SAME_COMPANY_JOBS = """
    SELECT
        dr.jsearch_job_id,
        dr.campaign_id,
        fj.job_title,
        COALESCE(ujs.status, 'waiting') as job_status
    FROM marts.fact_jobs fj
    INNER JOIN marts.dim_ranking dr
        ON fj.jsearch_job_id = dr.jsearch_job_id
        AND fj.campaign_id = dr.campaign_id
    INNER JOIN marts.job_campaigns jc
        ON dr.campaign_id = jc.campaign_id
    LEFT JOIN marts.user_job_status ujs
        ON dr.jsearch_job_id = ujs.jsearch_job_id
        AND ujs.user_id = %s
    WHERE fj.company_key = (
            SELECT company_key
            FROM marts.fact_jobs
            WHERE jsearch_job_id = %s
            LIMIT 1
        )
        AND fj.company_key IS NOT NULL
        AND fj.jsearch_job_id != %s
        AND jc.user_id = %s
    ORDER BY fj.job_posted_at_datetime_utc DESC NULLS LAST
"""

# ============================================================
# Job Status History Queries
# ============================================================

# Query to insert a status history entry
INSERT_STATUS_HISTORY = """
    INSERT INTO marts.job_status_history (
        jsearch_job_id, user_id, status, change_type, changed_by,
        changed_by_user_id, metadata, notes, created_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    RETURNING history_id
"""

# Query to get status history by job and user
GET_STATUS_HISTORY_BY_JOB_AND_USER = """
    SELECT
        history_id,
        jsearch_job_id,
        user_id,
        status,
        change_type,
        changed_by,
        changed_by_user_id,
        metadata,
        notes,
        created_at
    FROM marts.job_status_history
    WHERE jsearch_job_id = %s AND user_id = %s
    ORDER BY created_at ASC
"""

# Query to get status history by user (all jobs)
GET_STATUS_HISTORY_BY_USER = """
    SELECT
        history_id,
        jsearch_job_id,
        user_id,
        status,
        change_type,
        changed_by,
        changed_by_user_id,
        metadata,
        notes,
        created_at
    FROM marts.job_status_history
    WHERE user_id = %s
    ORDER BY created_at ASC
"""

# Query to get status history by job (all users)
GET_STATUS_HISTORY_BY_JOB = """
    SELECT
        history_id,
        jsearch_job_id,
        user_id,
        status,
        change_type,
        changed_by,
        changed_by_user_id,
        metadata,
        notes,
        created_at
    FROM marts.job_status_history
    WHERE jsearch_job_id = %s
    ORDER BY created_at ASC
"""
