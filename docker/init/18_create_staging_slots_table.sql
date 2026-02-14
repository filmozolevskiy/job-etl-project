-- Migration to add staging_slots table
-- Issue: JOB-46
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'staging_slots') THEN
        CREATE TABLE marts.staging_slots (
            slot_id integer PRIMARY KEY,
            slot_name varchar NOT NULL,
            status varchar NOT NULL DEFAULT 'Available', -- Available, In Use, Reserved
            health_status varchar NOT NULL DEFAULT 'Unknown', -- Healthy, Degraded, Down, Unknown
            owner varchar,
            branch varchar,
            issue_id varchar,
            deployed_at timestamp,
            purpose text,
            campaign_ui_url varchar,
            airflow_url varchar,
            api_url varchar,
            last_health_check_at timestamp,
            metadata jsonb DEFAULT '{}'::jsonb,
            created_at timestamp DEFAULT CURRENT_TIMESTAMP,
            updated_at timestamp DEFAULT CURRENT_TIMESTAMP
        );
    END IF;
END $$;

COMMENT ON TABLE marts.staging_slots IS 'Tracks staging slot allocations, status, credentials, and health.';

-- Initialize the 10 slots
INSERT INTO marts.staging_slots (slot_id, slot_name, campaign_ui_url, airflow_url, api_url)
VALUES 
    (1, 'staging-1', 'http://134.122.35.239:5001', 'http://134.122.35.239:8081', 'http://134.122.35.239:5001/api'),
    (2, 'staging-2', 'http://134.122.35.239:5002', 'http://134.122.35.239:8082', 'http://134.122.35.239:5002/api'),
    (3, 'staging-3', 'http://134.122.35.239:5003', 'http://134.122.35.239:8083', 'http://134.122.35.239:5003/api'),
    (4, 'staging-4', 'http://134.122.35.239:5004', 'http://134.122.35.239:8084', 'http://134.122.35.239:5004/api'),
    (5, 'staging-5', 'http://134.122.35.239:5005', 'http://134.122.35.239:8085', 'http://134.122.35.239:5005/api'),
    (6, 'staging-6', 'http://134.122.35.239:5006', 'http://134.122.35.239:8086', 'http://134.122.35.239:5006/api'),
    (7, 'staging-7', 'http://134.122.35.239:5007', 'http://134.122.35.239:8087', 'http://134.122.35.239:5007/api'),
    (8, 'staging-8', 'http://134.122.35.239:5008', 'http://134.122.35.239:8088', 'http://134.122.35.239:5008/api'),
    (9, 'staging-9', 'http://134.122.35.239:5009', 'http://134.122.35.239:8089', 'http://134.122.35.239:5009/api'),
    (10, 'staging-10', 'http://134.122.35.239:5010', 'http://134.122.35.239:8090', 'http://134.122.35.239:5010/api')
ON CONFLICT (slot_id) DO UPDATE 
SET campaign_ui_url = EXCLUDED.campaign_ui_url,
    airflow_url = EXCLUDED.airflow_url,
    api_url = EXCLUDED.api_url;

-- Update existing data from staging-slots.md (manual sync for first time)
UPDATE marts.staging_slots SET 
    status = 'In Use',
    owner = 'QA',
    branch = 'linear-JOB-39-add-job-location-column',
    issue_id = 'JOB-39',
    deployed_at = '2026-02-03T13:05:00Z',
    purpose = 'QA: Job Location column (Campaign Details)'
WHERE slot_id = 1;

UPDATE marts.staging_slots SET 
    status = 'In Use',
    owner = 'Deploy-Agent',
    branch = 'linear-JOB-17-restore-header-toggle',
    issue_id = 'JOB-17',
    deployed_at = '2026-02-09T03:15:00Z',
    purpose = 'QA: Campaign Active toggle in React'
WHERE slot_id = 2;

-- Grant permissions
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_user WHERE usename = 'app_user') THEN
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.staging_slots TO app_user';
    END IF;
END $$;

GRANT ALL PRIVILEGES ON TABLE marts.staging_slots TO postgres;
