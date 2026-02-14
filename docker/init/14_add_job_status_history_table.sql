-- ============================================================
-- Job Status History Table
-- Creates table for tracking job status change history
-- This script is idempotent and safe to run multiple times
-- ============================================================

-- ============================================================
-- MARTS LAYER (Gold)
-- Job status history tracking table
-- ============================================================

-- Job status history table
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'job_status_history') THEN
        CREATE TABLE marts.job_status_history (
            history_id SERIAL PRIMARY KEY,
            jsearch_job_id varchar NOT NULL,
            user_id integer NOT NULL,
            status varchar NOT NULL,
            change_type varchar NOT NULL,
            changed_by varchar,
            changed_by_user_id integer,
            metadata jsonb,
            notes text,
            created_at timestamp DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_history_user FOREIGN KEY (user_id) REFERENCES marts.users(user_id) ON DELETE CASCADE,
            CONSTRAINT fk_history_changed_by_user FOREIGN KEY (changed_by_user_id) REFERENCES marts.users(user_id) ON DELETE SET NULL
        );
    END IF;
END $$;

COMMENT ON TABLE marts.job_status_history IS 'Tracks historical status changes for job postings per user. Records all lifecycle events including job discovery, AI enrichment, user actions, document changes, and status updates.';

COMMENT ON COLUMN marts.job_status_history.status IS 'Status value: job_found, updated_by_ai, updated_by_chatgpt, approved, rejected, documents_uploaded, documents_changed, status_changed, note_added, note_updated, note_deleted';

COMMENT ON COLUMN marts.job_status_history.change_type IS 'Category of change: extraction, enrichment, user_action, document_change, status_change, note_change';

COMMENT ON COLUMN marts.job_status_history.changed_by IS 'Who made the change: system, user, ai_enricher, chatgpt_enricher';

COMMENT ON COLUMN marts.job_status_history.metadata IS 'JSONB field storing detailed change information: what changed, old/new values, enrichment details, etc.';

-- ============================================================
-- INDEXES (for performance)
-- ============================================================

-- Index for querying user's job history (most common query)
CREATE INDEX IF NOT EXISTS idx_job_status_history_job_user_created 
    ON marts.job_status_history(jsearch_job_id, user_id, created_at DESC);

-- Index for querying all user's history
CREATE INDEX IF NOT EXISTS idx_job_status_history_user_created 
    ON marts.job_status_history(user_id, created_at DESC);

-- Index for querying job's global history (across all users)
CREATE INDEX IF NOT EXISTS idx_job_status_history_job_created 
    ON marts.job_status_history(jsearch_job_id, created_at DESC);

-- Index for filtering by change type
CREATE INDEX IF NOT EXISTS idx_job_status_history_change_type 
    ON marts.job_status_history(change_type);

-- Index for filtering by status
CREATE INDEX IF NOT EXISTS idx_job_status_history_status 
    ON marts.job_status_history(status);

-- ============================================================
-- GRANT PERMISSIONS
-- ============================================================

-- Grant permissions to application user (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_user WHERE usename = 'app_user') THEN
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.job_status_history TO app_user';
        -- Grant sequence permissions for SERIAL columns
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE marts.job_status_history_history_id_seq TO app_user';
    END IF;
END $$;

-- Grant permissions to postgres user (for Docker default)
GRANT ALL PRIVILEGES ON TABLE marts.job_status_history TO postgres;
