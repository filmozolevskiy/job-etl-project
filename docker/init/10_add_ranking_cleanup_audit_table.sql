-- Migration Script: Add Ranking Cleanup Audit Table
-- Purpose: Track deleted orphaned rankings for audit and recovery purposes
-- Created: 2025-01-XX

-- Create audit table for tracking deleted orphaned rankings
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'dim_ranking_cleanup_audit') THEN
        CREATE TABLE marts.dim_ranking_cleanup_audit (
            audit_id SERIAL PRIMARY KEY,
            jsearch_job_id varchar NOT NULL,
            campaign_id integer NOT NULL,
            rank_score numeric,
            rank_explain jsonb,
            ranked_at timestamp,
            ranked_date date,
            dwh_load_timestamp timestamp,
            dwh_source_system varchar,
            cleanup_timestamp timestamp DEFAULT CURRENT_TIMESTAMP,
            cleanup_reason varchar DEFAULT 'orphaned_ranking',
            cleanup_batch_id varchar,
            CONSTRAINT dim_ranking_cleanup_audit_pkey UNIQUE (jsearch_job_id, campaign_id, cleanup_timestamp)
        );
    END IF;
END $$;

COMMENT ON TABLE marts.dim_ranking_cleanup_audit IS 'Audit trail for deleted orphaned rankings from dim_ranking. Stores rankings that were deleted because they referenced non-existent jobs in fact_jobs.';

COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.audit_id IS 'Primary key, auto-incrementing audit record ID';
COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.jsearch_job_id IS 'Job ID from deleted ranking';
COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.campaign_id IS 'Campaign ID from deleted ranking';
COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.rank_score IS 'Ranking score from deleted ranking';
COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.rank_explain IS 'Ranking explanation JSON from deleted ranking';
COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.ranked_at IS 'Original ranked_at timestamp';
COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.ranked_date IS 'Original ranked_date';
COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.dwh_load_timestamp IS 'Original dwh_load_timestamp';
COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.dwh_source_system IS 'Original source system';
COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.cleanup_timestamp IS 'Timestamp when this ranking was deleted';
COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.cleanup_reason IS 'Reason for deletion (default: orphaned_ranking)';
COMMENT ON COLUMN marts.dim_ranking_cleanup_audit.cleanup_batch_id IS 'Optional batch ID for grouping cleanup operations';

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_dim_ranking_cleanup_audit_cleanup_timestamp
    ON marts.dim_ranking_cleanup_audit(cleanup_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_dim_ranking_cleanup_audit_campaign_id
    ON marts.dim_ranking_cleanup_audit(campaign_id);

CREATE INDEX IF NOT EXISTS idx_dim_ranking_cleanup_audit_job_id
    ON marts.dim_ranking_cleanup_audit(jsearch_job_id);

CREATE INDEX IF NOT EXISTS idx_dim_ranking_cleanup_audit_batch_id
    ON marts.dim_ranking_cleanup_audit(cleanup_batch_id)
    WHERE cleanup_batch_id IS NOT NULL;

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE marts.dim_ranking_cleanup_audit TO app_user;
GRANT ALL PRIVILEGES ON TABLE marts.dim_ranking_cleanup_audit TO postgres;

-- Grant sequence permissions for SERIAL column
GRANT USAGE, SELECT ON SEQUENCE marts.dim_ranking_cleanup_audit_audit_id_seq TO app_user;
GRANT USAGE, SELECT ON SEQUENCE marts.dim_ranking_cleanup_audit_audit_id_seq TO postgres;

