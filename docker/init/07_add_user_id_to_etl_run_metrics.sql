-- ============================================================
-- Migration Script: Add user_id to etl_run_metrics table
-- Adds user_id column to track which user owns the profile
-- ============================================================

-- Add user_id column
ALTER TABLE marts.etl_run_metrics
ADD COLUMN IF NOT EXISTS user_id integer;

-- Add foreign key constraint
ALTER TABLE marts.etl_run_metrics
DROP CONSTRAINT IF EXISTS fk_etl_run_metrics_user;

ALTER TABLE marts.etl_run_metrics
ADD CONSTRAINT fk_etl_run_metrics_user
FOREIGN KEY (user_id) REFERENCES marts.users(user_id) ON DELETE SET NULL;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_etl_run_metrics_user_id
ON marts.etl_run_metrics(user_id);

-- Update existing records: populate user_id from profile_preferences
UPDATE marts.etl_run_metrics erm
SET user_id = pp.user_id
FROM marts.profile_preferences pp
WHERE erm.profile_id = pp.profile_id
AND erm.user_id IS NULL;

-- Add comment
COMMENT ON COLUMN marts.etl_run_metrics.user_id IS 'User ID of the profile owner. Populated from profile_preferences.user_id when profile_id is set.';

