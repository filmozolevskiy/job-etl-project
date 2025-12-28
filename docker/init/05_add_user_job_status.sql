-- ============================================================
-- Migration Script: Create user_job_status table
-- Adds status tracking per user per job (separate from notes)
-- ============================================================

-- Create user_job_status table
CREATE TABLE IF NOT EXISTS marts.user_job_status (
    user_job_status_id SERIAL PRIMARY KEY,
    user_id integer NOT NULL,
    jsearch_job_id varchar NOT NULL,
    status varchar NOT NULL DEFAULT 'waiting',
    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_job_status_user FOREIGN KEY (user_id) REFERENCES marts.users(user_id) ON DELETE CASCADE,
    CONSTRAINT unique_user_job_status UNIQUE (user_id, jsearch_job_id),
    CONSTRAINT chk_user_job_status CHECK (status IN ('waiting', 'applied', 'rejected', 'interview', 'offer', 'archived'))
);

COMMENT ON TABLE marts.user_job_status IS 'User-specific job application status tracking. Each user can have one status per job.';

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_user_job_status_user_job 
    ON marts.user_job_status(user_id, jsearch_job_id);

CREATE INDEX IF NOT EXISTS idx_user_job_status_status 
    ON marts.user_job_status(status);

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE marts.user_job_status TO app_user;
GRANT ALL PRIVILEGES ON TABLE marts.user_job_status TO postgres;

-- Create sequence if needed (SERIAL creates it automatically, but ensure it exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE schemaname = 'marts' AND sequencename = 'user_job_status_user_job_status_id_seq') THEN
        CREATE SEQUENCE marts.user_job_status_user_job_status_id_seq;
        ALTER TABLE marts.user_job_status ALTER COLUMN user_job_status_id SET DEFAULT nextval('marts.user_job_status_user_job_status_id_seq');
    END IF;
END $$;

GRANT USAGE, SELECT ON SEQUENCE marts.user_job_status_user_job_status_id_seq TO app_user;

