-- Migration script to add job_salary_currency column to staging.jsearch_job_postings
-- Run this before running dbt to update the staging model

-- Add column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'staging' 
        AND table_name = 'jsearch_job_postings' 
        AND column_name = 'job_salary_currency'
    ) THEN
        ALTER TABLE staging.jsearch_job_postings 
        ADD COLUMN job_salary_currency VARCHAR;
        
        RAISE NOTICE 'Added job_salary_currency column to staging.jsearch_job_postings';
    ELSE
        RAISE NOTICE 'Column job_salary_currency already exists in staging.jsearch_job_postings';
    END IF;
END $$;

