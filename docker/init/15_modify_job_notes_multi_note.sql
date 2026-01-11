-- ============================================================
-- Modify Job Notes for Multi-Note Support
-- Removes unique constraint to allow multiple notes per job per user
-- Adds referential integrity check to prevent orphan notes
-- This script is idempotent and safe to run multiple times
-- ============================================================

-- ============================================================
-- STEP 1: Remove unique constraint to allow multiple notes
-- ============================================================

-- Drop the unique constraint if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'unique_job_user_note' 
        AND conrelid = 'marts.job_notes'::regclass
    ) THEN
        ALTER TABLE marts.job_notes DROP CONSTRAINT unique_job_user_note;
        RAISE NOTICE 'Dropped unique constraint unique_job_user_note';
    ELSE
        RAISE NOTICE 'Unique constraint unique_job_user_note does not exist, skipping';
    END IF;
END $$;

-- ============================================================
-- STEP 2: Create function to check if job exists
-- ============================================================

CREATE OR REPLACE FUNCTION marts.check_job_exists(job_id varchar)
RETURNS boolean AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM marts.fact_jobs WHERE jsearch_job_id = job_id
        UNION
        SELECT 1 FROM staging.jsearch_job_postings WHERE jsearch_job_id = job_id
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION marts.check_job_exists IS 'Checks if a job exists in either fact_jobs or staging.jsearch_job_postings to ensure referential integrity for job_notes';

-- ============================================================
-- STEP 3: Add check constraint for referential integrity
-- ============================================================

-- Drop constraint if it exists (for idempotency)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'chk_job_exists' 
        AND conrelid = 'marts.job_notes'::regclass
    ) THEN
        ALTER TABLE marts.job_notes DROP CONSTRAINT chk_job_exists;
        RAISE NOTICE 'Dropped existing check constraint chk_job_exists';
    END IF;
END $$;

-- Add check constraint
ALTER TABLE marts.job_notes
ADD CONSTRAINT chk_job_exists
CHECK (marts.check_job_exists(jsearch_job_id));

COMMENT ON CONSTRAINT chk_job_exists ON marts.job_notes IS 'Ensures jsearch_job_id exists in fact_jobs or staging.jsearch_job_postings to prevent orphan notes';

-- ============================================================
-- STEP 4: Update table comment
-- ============================================================

COMMENT ON TABLE marts.job_notes IS 'User notes for job postings. Each user can have multiple notes per job posting. Notes can be edited and track modification timestamps.';

-- ============================================================
-- STEP 5: Clean up any orphan notes (optional, for data integrity)
-- ============================================================

-- Delete any notes that reference non-existent jobs
DELETE FROM marts.job_notes
WHERE NOT marts.check_job_exists(jsearch_job_id);

-- Log cleanup if any rows were deleted
DO $$
DECLARE
    deleted_count integer;
BEGIN
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    IF deleted_count > 0 THEN
        RAISE NOTICE 'Cleaned up % orphan note(s)', deleted_count;
    END IF;
END $$;
