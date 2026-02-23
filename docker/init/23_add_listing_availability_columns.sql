-- ============================================================
-- Add listing availability columns to staging.jsearch_job_postings
-- Migration: 23_add_listing_availability_columns.sql
-- JOB-57: Detect jobs no longer relevant via JSearch job-details; mark without removing.
-- ============================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'staging' AND table_name = 'jsearch_job_postings') THEN
        ALTER TABLE staging.jsearch_job_postings
            ADD COLUMN IF NOT EXISTS listing_available BOOLEAN,
            ADD COLUMN IF NOT EXISTS listing_checked_at TIMESTAMPTZ;

        COMMENT ON COLUMN staging.jsearch_job_postings.listing_available IS 'True if job-details API returned the job; false if removed/filled; NULL if not yet checked';
        COMMENT ON COLUMN staging.jsearch_job_postings.listing_checked_at IS 'When listing availability was last checked via JSearch job-details';
    END IF;
END $$;
