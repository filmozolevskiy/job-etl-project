-- ============================================================
-- User Job Status Table
-- Creates table for tracking user-specific job application status
-- This script is idempotent and safe to run multiple times
-- ============================================================

-- ============================================================
-- MARTS LAYER (Gold)
-- User-managed job status table
-- ============================================================

-- User job status table
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'user_job_status') THEN
        CREATE TABLE marts.user_job_status (
            user_job_status_id SERIAL PRIMARY KEY,
            jsearch_job_id varchar NOT NULL,
            user_id integer NOT NULL,
            status varchar NOT NULL,
            created_at timestamp DEFAULT CURRENT_TIMESTAMP,
            updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_user_job_status_user FOREIGN KEY (user_id) REFERENCES marts.users(user_id) ON DELETE CASCADE,
            CONSTRAINT unique_user_job_status UNIQUE (user_id, jsearch_job_id),
            CONSTRAINT chk_user_job_status CHECK (status IN ('waiting', 'applied', 'approved', 'rejected', 'interview', 'offer', 'archived'))
        );
    END IF;
END $$;

COMMENT ON TABLE marts.user_job_status IS 'Tracks user-specific application status for job postings. Each user can have one status per job posting. Status values: waiting, applied, approved, rejected, interview, offer, archived.';

-- ============================================================
-- INDEXES (for performance)
-- ============================================================

-- Indexes for user_job_status
CREATE INDEX IF NOT EXISTS idx_user_job_status_job_id 
    ON marts.user_job_status(jsearch_job_id);
    
CREATE INDEX IF NOT EXISTS idx_user_job_status_user_id 
    ON marts.user_job_status(user_id);
    
CREATE INDEX IF NOT EXISTS idx_user_job_status_status 
    ON marts.user_job_status(status);

-- ============================================================
-- GRANT PERMISSIONS
-- ============================================================

-- Grant permissions to application user (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_user WHERE usename = 'app_user') THEN
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.user_job_status TO app_user';
        -- Grant sequence permissions for SERIAL columns
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE marts.user_job_status_user_job_status_id_seq TO app_user';
    END IF;
END $$;

-- Grant permissions to postgres user (for Docker default)
GRANT ALL PRIVILEGES ON TABLE marts.user_job_status TO postgres;
