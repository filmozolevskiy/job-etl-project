-- Insert test profile for BI Developer in Canada
-- This script can be run directly against the PostgreSQL database

-- First, ensure we have a profile_id (if no sequence exists, we'll use the max + 1)
DO $$
DECLARE
    next_profile_id INTEGER;
BEGIN
    -- Get the next profile_id (max existing + 1, or 1 if no profiles exist)
    SELECT COALESCE(MAX(profile_id), 0) + 1 INTO next_profile_id
    FROM marts.profile_preferences;
    
    -- Insert the test profile
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
        remote_preference,
        seniority,
        created_at,
        updated_at,
        total_run_count,
        last_run_at,
        last_run_status,
        last_run_job_count
    ) VALUES (
        next_profile_id,
        'BI Developer - Canada',
        true,  -- is_active
        'BI Developer',  -- query
        'Canada',  -- location
        'ca',  -- country code (lowercase)
        '7d',  -- date_window (last 7 days)
        'test@example.com',  -- email (update with real email if needed)
        'Python;DBT;Looker;SQL',  -- skills (semicolon-separated)
        NULL,  -- min_salary (optional)
        NULL,  -- max_salary (optional)
        NULL,  -- remote_preference (optional)
        NULL,  -- seniority (optional)
        CURRENT_TIMESTAMP,  -- created_at
        CURRENT_TIMESTAMP,  -- updated_at
        0,  -- total_run_count
        NULL,  -- last_run_at
        'never',  -- last_run_status
        0  -- last_run_job_count
    )
    ON CONFLICT DO NOTHING;  -- Prevent duplicate inserts
    
    RAISE NOTICE 'Inserted test profile with profile_id: %', next_profile_id;
END $$;

-- Verify the profile was inserted
SELECT 
    profile_id,
    profile_name,
    is_active,
    query,
    location,
    country,
    skills,
    created_at
FROM marts.profile_preferences
WHERE profile_name = 'BI Developer - Canada';

