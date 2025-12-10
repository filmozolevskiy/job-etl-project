-- ============================================================
-- Recreate Tables Script (for empty databases)
-- Drops and recreates raw tables with correct column names
-- Only run this if database is empty (no data loss)
-- ============================================================

-- Drop existing raw tables if they exist (will lose data!)
-- Only use this if you're sure the database is empty
DROP TABLE IF EXISTS raw.jsearch_job_postings CASCADE;
DROP TABLE IF EXISTS raw.glassdoor_companies CASCADE;

-- Recreate raw.jsearch_job_postings with correct column names
CREATE TABLE raw.jsearch_job_postings (
    jsearch_job_postings_key bigint,
    raw_payload jsonb,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar,
    profile_id integer
);

COMMENT ON TABLE raw.jsearch_job_postings IS 'Raw layer table for JSearch job postings. Stores raw JSON payloads from JSearch API with minimal transformation. Populated by Source Extractor service.';

-- Recreate raw.glassdoor_companies with correct column names
CREATE TABLE raw.glassdoor_companies (
    glassdoor_companies_key bigint,
    raw_payload jsonb,
    company_lookup_key varchar,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar
);

COMMENT ON TABLE raw.glassdoor_companies IS 'Raw layer table for Glassdoor company data. Stores raw JSON payloads from Glassdoor API with minimal transformation. Populated by Company Extraction service.';

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_jsearch_job_postings_profile_id 
    ON raw.jsearch_job_postings(profile_id);
    
CREATE INDEX IF NOT EXISTS idx_jsearch_job_postings_load_timestamp 
    ON raw.jsearch_job_postings(dwh_load_timestamp);
    
CREATE INDEX IF NOT EXISTS idx_glassdoor_companies_lookup_key 
    ON raw.glassdoor_companies(company_lookup_key);
    
CREATE INDEX IF NOT EXISTS idx_glassdoor_companies_load_timestamp 
    ON raw.glassdoor_companies(dwh_load_timestamp);

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE raw.jsearch_job_postings TO postgres;
GRANT ALL PRIVILEGES ON TABLE raw.glassdoor_companies TO postgres;
