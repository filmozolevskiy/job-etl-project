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
        created_at,
        updated_at,
        total_run_count,
        last_run_status
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 'pending'
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
