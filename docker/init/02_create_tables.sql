-- ============================================================
-- Table Creation Script
-- Creates tables that are populated by Python services or UI
-- These tables must exist before services run
-- This script is idempotent and safe to run multiple times
-- ============================================================

-- ============================================================
-- RAW LAYER (Bronze)
-- Tables populated by Python extraction services
-- ============================================================

-- Raw job postings from JSearch API
CREATE TABLE IF NOT EXISTS raw.jsearch_job_postings (
    jsearch_job_postings_key bigint,
    raw_payload jsonb,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar,
    profile_id integer
);

COMMENT ON TABLE raw.jsearch_job_postings IS 'Raw layer table for JSearch job postings. Stores raw JSON payloads from JSearch API with minimal transformation. Populated by Source Extractor service.';

-- Raw company data from Glassdoor API
CREATE TABLE IF NOT EXISTS raw.glassdoor_companies (
    glassdoor_companies_key bigint,
    raw_payload jsonb,
    company_lookup_key varchar,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar
);

COMMENT ON TABLE raw.glassdoor_companies IS 'Raw layer table for Glassdoor company data. Stores raw JSON payloads from Glassdoor API with minimal transformation. Populated by Company Extraction service.';

-- ============================================================
-- STAGING LAYER (Silver)
-- Queue table populated by Python services
-- ============================================================

-- Company enrichment queue
CREATE TABLE IF NOT EXISTS staging.company_enrichment_queue (
    company_lookup_key varchar PRIMARY KEY,
    enrichment_status varchar,  -- pending, success, not_found, error
    first_queued_at timestamp,
    last_attempt_at timestamp,
    completed_at timestamp,
    error_message text,
    attempt_count integer
);

COMMENT ON TABLE staging.company_enrichment_queue IS 'Tracks which companies need Glassdoor enrichment. Populated and updated by Company Extraction service as enrichment progresses.';

-- ============================================================
-- MARTS LAYER (Gold)
-- Configuration table: populated exclusively via Profile Management UI
-- ============================================================

-- Profile preferences
CREATE TABLE IF NOT EXISTS marts.profile_preferences (
    profile_id integer,
    profile_name varchar,
    is_active boolean,
    query varchar,
    location varchar,
    country varchar,
    date_window varchar,
    email varchar,
    skills varchar,
    min_salary numeric,
    max_salary numeric,
    remote_preference varchar,
    seniority varchar,
    created_at timestamp,
    updated_at timestamp,
    total_run_count integer,
    last_run_at timestamp,
    last_run_status varchar,
    last_run_job_count integer
);

COMMENT ON TABLE marts.profile_preferences IS 'Stores job profiles that drive extraction and ranking. Profiles are managed exclusively via the Profile Management UI. ETL services query active profiles (WHERE is_active = true) for job extraction.';

-- Job rankings (populated by Ranker service)
CREATE TABLE IF NOT EXISTS marts.dim_ranking (
    jsearch_job_id varchar,
    profile_id integer,
    rank_score numeric,
    rank_explain jsonb,
    ranked_at timestamp,
    ranked_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar,
    CONSTRAINT dim_ranking_pkey PRIMARY KEY (jsearch_job_id, profile_id)
);

COMMENT ON TABLE marts.dim_ranking IS 'Stores job ranking scores per profile. One row per (job, profile) pair. Populated by the Ranker service.';

-- ============================================================
-- INDEXES (for performance)
-- ============================================================

-- Indexes for raw tables
CREATE INDEX IF NOT EXISTS idx_jsearch_job_postings_profile_id 
    ON raw.jsearch_job_postings(profile_id);
    
CREATE INDEX IF NOT EXISTS idx_jsearch_job_postings_load_timestamp 
    ON raw.jsearch_job_postings(dwh_load_timestamp);
    
CREATE INDEX IF NOT EXISTS idx_glassdoor_companies_lookup_key 
    ON raw.glassdoor_companies(company_lookup_key);
    
CREATE INDEX IF NOT EXISTS idx_glassdoor_companies_load_timestamp 
    ON raw.glassdoor_companies(dwh_load_timestamp);

-- Indexes for enrichment queue
CREATE INDEX IF NOT EXISTS idx_company_enrichment_queue_status 
    ON staging.company_enrichment_queue(enrichment_status) 
    WHERE enrichment_status = 'pending';
    
CREATE INDEX IF NOT EXISTS idx_company_enrichment_queue_lookup 
    ON staging.company_enrichment_queue(company_lookup_key);

-- Indexes for profile preferences
CREATE INDEX IF NOT EXISTS idx_profile_preferences_active 
    ON marts.profile_preferences(is_active) 
    WHERE is_active = true;
    
CREATE INDEX IF NOT EXISTS idx_profile_preferences_profile_id 
    ON marts.profile_preferences(profile_id);

-- Indexes for dim_ranking (primary key already provides unique index, but we can add additional indexes if needed)
-- Note: Primary key constraint automatically creates an index on (jsearch_job_id, profile_id)

-- ============================================================
-- GRANT PERMISSIONS
-- ============================================================

-- Grant permissions to application user (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_user WHERE usename = 'app_user') THEN
        GRANT ALL PRIVILEGES ON TABLE raw.jsearch_job_postings TO app_user;
        GRANT ALL PRIVILEGES ON TABLE raw.glassdoor_companies TO app_user;
        GRANT ALL PRIVILEGES ON TABLE staging.company_enrichment_queue TO app_user;
        GRANT ALL PRIVILEGES ON TABLE marts.profile_preferences TO app_user;
        GRANT ALL PRIVILEGES ON TABLE marts.dim_ranking TO app_user;
    END IF;
END $$;

-- Grant permissions to postgres user (for Docker default)
GRANT ALL PRIVILEGES ON TABLE raw.jsearch_job_postings TO postgres;
GRANT ALL PRIVILEGES ON TABLE raw.glassdoor_companies TO postgres;
GRANT ALL PRIVILEGES ON TABLE staging.company_enrichment_queue TO postgres;
GRANT ALL PRIVILEGES ON TABLE marts.profile_preferences TO postgres;
GRANT ALL PRIVILEGES ON TABLE marts.dim_ranking TO postgres;

