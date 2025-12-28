-- ============================================================
-- Migration Script: Remove status column from job_notes
-- Status is now tracked separately in user_job_status table
-- ============================================================

-- Drop constraint if it exists
ALTER TABLE marts.job_notes DROP CONSTRAINT IF EXISTS chk_job_status;

-- Drop status column
ALTER TABLE marts.job_notes DROP COLUMN IF EXISTS status;

