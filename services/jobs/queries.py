"""SQL queries for job viewing and job notes."""

# Query to get jobs with rankings, companies, notes, and status for a campaign
GET_JOBS_FOR_CAMPAIGN = """
    SELECT
        jsearch_job_id,
        campaign_id,
        rank_score,
        rank_explain,
        ranked_at,
        job_title,
        job_location,
        job_employment_type,
        job_is_remote,
        job_posted_at_datetime_utc,
        apply_options,
        job_apply_link,
        extracted_skills,
        job_min_salary,
        job_max_salary,
        remote_work_type,
        company_name,
        company_size,
        rating,
        company_link,
        company_logo,
        note_text,
        note_id,
        note_created_at,
        note_updated_at,
        job_status
    FROM (
        SELECT DISTINCT ON (dr.jsearch_job_id)
            dr.jsearch_job_id,
            dr.campaign_id,
            dr.rank_score,
            dr.rank_explain,
            dr.ranked_at,
            fj.job_title,
            fj.job_location,
            fj.job_employment_type,
            fj.job_is_remote,
            fj.job_posted_at_datetime_utc,
            fj.apply_options,
            fj.job_apply_link,
            fj.extracted_skills,
            fj.job_min_salary,
            fj.job_max_salary,
            fj.remote_work_type,
            fj.employer_name,
            COALESCE(dc.company_name, fj.employer_name, 'Unknown') as company_name,
            dc.company_size,
            dc.rating,
            dc.company_link,
            dc.logo as company_logo,
            jn.note_text,
            jn.note_id,
            jn.created_at as note_created_at,
            jn.updated_at as note_updated_at,
            COALESCE(ujs.status, 'waiting') as job_status
        FROM marts.dim_ranking dr
        LEFT JOIN marts.fact_jobs fj
            ON dr.jsearch_job_id = fj.jsearch_job_id
            AND dr.campaign_id = fj.campaign_id
        LEFT JOIN marts.dim_companies dc
            ON fj.company_key = dc.company_key
        LEFT JOIN marts.job_notes jn
            ON dr.jsearch_job_id = jn.jsearch_job_id
            AND jn.user_id = %s
        LEFT JOIN marts.user_job_status ujs
            ON dr.jsearch_job_id = ujs.jsearch_job_id
            AND ujs.user_id = %s
        WHERE dr.campaign_id = %s
        ORDER BY dr.jsearch_job_id, dr.rank_score DESC NULLS LAST, dr.ranked_at DESC NULLS LAST
    ) ranked_jobs
    ORDER BY rank_score DESC NULLS LAST, ranked_at DESC NULLS LAST
"""

# Query to get jobs for all user's campaigns
GET_JOBS_FOR_USER = """
    SELECT
        jsearch_job_id,
        campaign_id,
        campaign_name,
        rank_score,
        rank_explain,
        ranked_at,
        job_title,
        job_location,
        job_employment_type,
        job_is_remote,
        job_posted_at_datetime_utc,
        apply_options,
        job_apply_link,
        extracted_skills,
        job_min_salary,
        job_max_salary,
        remote_work_type,
        company_name,
        company_size,
        rating,
        company_link,
        company_logo,
        note_text,
        note_id,
        note_created_at,
        note_updated_at,
        job_status
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
            fj.job_employment_type,
            fj.job_is_remote,
            fj.job_posted_at_datetime_utc,
            fj.apply_options,
            fj.job_apply_link,
            fj.extracted_skills,
            fj.job_min_salary,
            fj.job_max_salary,
            fj.remote_work_type,
            fj.employer_name,
            COALESCE(dc.company_name, fj.employer_name, 'Unknown') as company_name,
            dc.company_size,
            dc.rating,
            dc.company_link,
            dc.logo as company_logo,
            jn.note_text,
            jn.note_id,
            jn.created_at as note_created_at,
            jn.updated_at as note_updated_at,
            COALESCE(ujs.status, 'waiting') as job_status
        FROM marts.dim_ranking dr
        LEFT JOIN marts.fact_jobs fj
            ON dr.jsearch_job_id = fj.jsearch_job_id
            AND dr.campaign_id = fj.campaign_id
        INNER JOIN marts.job_campaigns jc
            ON dr.campaign_id = jc.campaign_id
        LEFT JOIN marts.dim_companies dc
            ON fj.company_key = dc.company_key
        LEFT JOIN marts.job_notes jn
            ON dr.jsearch_job_id = jn.jsearch_job_id
            AND jn.user_id = %s
        LEFT JOIN marts.user_job_status ujs
            ON dr.jsearch_job_id = ujs.jsearch_job_id
            AND ujs.user_id = %s
        WHERE jc.user_id = %s
        ORDER BY dr.jsearch_job_id, dr.campaign_id, dr.rank_score DESC NULLS LAST, dr.ranked_at DESC NULLS LAST
    ) ranked_jobs
    ORDER BY rank_score DESC NULLS LAST, ranked_at DESC NULLS LAST
"""

# Query to get a note by job_id and user_id
GET_NOTE_BY_JOB_AND_USER = """
    SELECT
        note_id,
        jsearch_job_id,
        user_id,
        note_text,
        created_at,
        updated_at
    FROM marts.job_notes
    WHERE jsearch_job_id = %s AND user_id = %s
"""

# Query to insert a new note
INSERT_NOTE = """
    INSERT INTO marts.job_notes (jsearch_job_id, user_id, note_text, created_at, updated_at)
    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    RETURNING note_id
"""

# Query to update an existing note
UPDATE_NOTE = """
    UPDATE marts.job_notes
    SET note_text = %s, updated_at = CURRENT_TIMESTAMP
    WHERE note_id = %s AND user_id = %s
    RETURNING note_id
"""

# Query to upsert a note (insert or update)
UPSERT_NOTE = """
    INSERT INTO marts.job_notes (jsearch_job_id, user_id, note_text, created_at, updated_at)
    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT (jsearch_job_id, user_id)
    DO UPDATE SET
        note_text = EXCLUDED.note_text,
        updated_at = CURRENT_TIMESTAMP
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
    INSERT INTO marts.user_job_status (jsearch_job_id, user_id, status, created_at, updated_at)
    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT (user_id, jsearch_job_id)
    DO UPDATE SET
        status = EXCLUDED.status,
        updated_at = CURRENT_TIMESTAMP
    RETURNING user_job_status_id
"""

# Query to get job counts for multiple campaigns
GET_JOB_COUNTS_FOR_CAMPAIGNS = """
    SELECT
        dr.campaign_id,
        COUNT(DISTINCT dr.jsearch_job_id) as job_count
    FROM marts.dim_ranking dr
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
        job_employment_type,
        job_is_remote,
        job_posted_at_datetime_utc,
        apply_options,
        job_apply_link,
        extracted_skills,
        job_min_salary,
        job_max_salary,
        remote_work_type,
        company_name,
        company_size,
        rating,
        company_link,
        company_logo,
        note_text,
        note_id,
        note_created_at,
        note_updated_at,
        job_status
    FROM (
        SELECT DISTINCT ON (dr.jsearch_job_id)
            dr.jsearch_job_id,
            dr.campaign_id,
            dr.rank_score,
            dr.rank_explain,
            dr.ranked_at,
            fj.job_title,
            fj.job_location,
            fj.job_employment_type,
            fj.job_is_remote,
            fj.job_posted_at_datetime_utc,
            fj.apply_options,
            fj.job_apply_link,
            fj.extracted_skills,
            fj.job_min_salary,
            fj.job_max_salary,
            fj.remote_work_type,
            fj.employer_name,
            COALESCE(dc.company_name, fj.employer_name, 'Unknown') as company_name,
            dc.company_size,
            dc.rating,
            dc.company_link,
            dc.logo as company_logo,
            jn.note_text,
            jn.note_id,
            jn.created_at as note_created_at,
            jn.updated_at as note_updated_at,
            COALESCE(ujs.status, 'waiting') as job_status
        FROM marts.dim_ranking dr
        LEFT JOIN marts.fact_jobs fj
            ON dr.jsearch_job_id = fj.jsearch_job_id
            AND dr.campaign_id = fj.campaign_id
        LEFT JOIN marts.job_campaigns jc
            ON dr.campaign_id = jc.campaign_id
        LEFT JOIN marts.dim_companies dc
            ON fj.company_key = dc.company_key
        LEFT JOIN marts.job_notes jn
            ON dr.jsearch_job_id = jn.jsearch_job_id
            AND jn.user_id = %s
        LEFT JOIN marts.user_job_status ujs
            ON dr.jsearch_job_id = ujs.jsearch_job_id
            AND ujs.user_id = %s
        WHERE dr.jsearch_job_id = %s
        ORDER BY dr.jsearch_job_id, dr.rank_score DESC NULLS LAST, dr.ranked_at DESC NULLS LAST
    ) ranked_jobs
    LIMIT 1
"""
