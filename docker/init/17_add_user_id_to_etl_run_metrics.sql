-- Migration: Add user_id column to etl_run_metrics table
-- This column allows tracking metrics by user for better analytics

ALTER TABLE marts.etl_run_metrics 
ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES marts.users(user_id) ON DELETE SET NULL;

-- Create index for user_id lookups
CREATE INDEX IF NOT EXISTS idx_etl_run_metrics_user_id 
ON marts.etl_run_metrics(user_id);

COMMENT ON COLUMN marts.etl_run_metrics.user_id IS 'User ID of the campaign owner (denormalized from job_campaigns for query performance)';
