-- ============================================================
-- Migration Script: Rename Raw Table Columns
-- Updates column names to follow naming conventions
-- Run this if tables were created with old column names
-- ============================================================

-- Rename columns in raw.jsearch_job_postings
DO $$
BEGIN
    -- Check if old column exists and new column doesn't
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'raw' 
        AND table_name = 'jsearch_job_postings' 
        AND column_name = 'raw_job_posting_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'raw' 
        AND table_name = 'jsearch_job_postings' 
        AND column_name = 'jsearch_job_postings_key'
    ) THEN
        ALTER TABLE raw.jsearch_job_postings 
        RENAME COLUMN raw_job_posting_id TO jsearch_job_postings_key;
        
        RAISE NOTICE 'Renamed raw_job_posting_id to jsearch_job_postings_key';
    END IF;
END $$;

-- Rename columns in raw.glassdoor_companies
DO $$
BEGIN
    -- Check if old column exists and new column doesn't
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'raw' 
        AND table_name = 'glassdoor_companies' 
        AND column_name = 'raw_company_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'raw' 
        AND table_name = 'glassdoor_companies' 
        AND column_name = 'glassdoor_companies_key'
    ) THEN
        ALTER TABLE raw.glassdoor_companies 
        RENAME COLUMN raw_company_id TO glassdoor_companies_key;
        
        RAISE NOTICE 'Renamed raw_company_id to glassdoor_companies_key';
    END IF;
END $$;

-- Recreate indexes if they reference old column names
DROP INDEX IF EXISTS raw.idx_jsearch_job_postings_profile_id;
CREATE INDEX IF NOT EXISTS idx_jsearch_job_postings_profile_id 
    ON raw.jsearch_job_postings(profile_id);

DROP INDEX IF EXISTS raw.idx_jsearch_job_postings_load_timestamp;
CREATE INDEX IF NOT EXISTS idx_jsearch_job_postings_load_timestamp 
    ON raw.jsearch_job_postings(dwh_load_timestamp);

DROP INDEX IF EXISTS raw.idx_glassdoor_companies_lookup_key;
CREATE INDEX IF NOT EXISTS idx_glassdoor_companies_lookup_key 
    ON raw.glassdoor_companies(company_lookup_key);

DROP INDEX IF EXISTS raw.idx_glassdoor_companies_load_timestamp;
CREATE INDEX IF NOT EXISTS idx_glassdoor_companies_load_timestamp 
    ON raw.glassdoor_companies(dwh_load_timestamp);
