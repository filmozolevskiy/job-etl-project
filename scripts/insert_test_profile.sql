-- Insert test campaign for BI Developer in Canada
-- NOTE: This script references the old table structure (profile_preferences).
-- It should be updated to use job_campaigns table if still in use.
-- This script can be run directly against the PostgreSQL database

-- First, ensure we have a campaign_id (if no sequence exists, we'll use the max + 1)
DO $$
DECLARE
    next_campaign_id INTEGER;
BEGIN
    -- Get the next campaign_id (max existing + 1, or 1 if no campaigns exist)
    SELECT COALESCE(MAX(campaign_id), 0) + 1 INTO next_campaign_id
    FROM marts.job_campaigns;
    
    -- Insert the test campaign
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
    
    RAISE NOTICE 'Inserted test campaign with campaign_id: %', next_campaign_id;
END $$;

-- Verify the campaign was inserted
-- NOTE: This query references old table structure and should be updated
SELECT 
    campaign_id,
    campaign_name,
    is_active,
    query,
    location,
    country,
    skills,
    created_at
FROM marts.job_campaigns
WHERE campaign_name = 'BI Developer - Canada';

