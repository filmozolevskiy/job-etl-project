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
    campaign_id integer
);

COMMENT ON TABLE raw.jsearch_job_postings IS 'Raw layer table for JSearch job postings. Stores raw JSON payloads from JSearch API with minimal transformation. Populated by Source Extractor service. Each row is associated with a campaign_id.';

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
-- Configuration table: populated exclusively via Campaign Management UI
-- ============================================================

-- Users table (for authentication and authorization)
CREATE TABLE IF NOT EXISTS marts.users (
    user_id SERIAL PRIMARY KEY,
    username varchar UNIQUE NOT NULL,
    email varchar UNIQUE NOT NULL,
    password_hash varchar NOT NULL,
    role varchar NOT NULL DEFAULT 'user',  -- 'user' or 'admin'
    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
    last_login timestamp
);

COMMENT ON TABLE marts.users IS 'User accounts for the job search platform. Supports role-based access control (regular users and admins).';

-- Job campaigns
CREATE TABLE IF NOT EXISTS marts.job_campaigns (
    campaign_id integer,
    user_id integer,
    campaign_name varchar,
    is_active boolean,
    query varchar,
    location varchar,
    country varchar,
    date_window varchar,
    email varchar,
    skills varchar,
    min_salary integer,  -- Yearly salary in campaign currency
    max_salary integer,  -- Yearly salary in campaign currency
    currency varchar(3),
    remote_preference varchar,
    seniority varchar,
    company_size_preference varchar,
    employment_type_preference varchar,
    -- Ranking weights (JSONB, percentages should sum to 100%)
    -- Format: {"location_match": 15.0, "salary_match": 15.0, ...}
    ranking_weights jsonb,
    created_at timestamp,
    updated_at timestamp,
    total_run_count integer,
    last_run_at timestamp,
    last_run_status varchar,
    last_run_job_count integer,
    CONSTRAINT fk_campaign_user FOREIGN KEY (user_id) REFERENCES marts.users(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE marts.job_campaigns IS 'Stores job campaigns that drive extraction and ranking. Campaigns are managed exclusively via the Campaign Management UI. Each campaign belongs to a user. ETL services query active campaigns (WHERE is_active = true) for job extraction.';

-- Job rankings table (populated by Ranker service)
CREATE TABLE IF NOT EXISTS marts.dim_ranking (
    jsearch_job_id varchar,
    campaign_id integer,
    rank_score numeric,
    rank_explain jsonb,
    ranked_at timestamp,
    ranked_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar,
    CONSTRAINT dim_ranking_pkey PRIMARY KEY (jsearch_job_id, campaign_id)
);

COMMENT ON TABLE marts.dim_ranking IS 'Job ranking scores per campaign. One row per (job, campaign) pair. Populated by the Ranker service using UPSERT.';

-- ETL Run Metrics (populated by Airflow tasks)
CREATE TABLE IF NOT EXISTS marts.etl_run_metrics (
    run_id varchar PRIMARY KEY,
    dag_run_id varchar,
    run_timestamp timestamp,
    campaign_id integer,
    task_name varchar,
    task_status varchar,  -- success, failed, skipped
    rows_processed_raw integer,
    rows_processed_staging integer,
    rows_processed_marts integer,
    api_calls_made integer,
    api_errors integer,
    processing_duration_seconds numeric,
    data_quality_tests_passed integer,
    data_quality_tests_failed integer,
    error_message text,
    metadata jsonb
);

COMMENT ON TABLE marts.etl_run_metrics IS 'Tracks per-run statistics for pipeline health monitoring. Populated by Airflow tasks to record processing metrics, API usage, data quality test results, and errors.';

-- Job notes (user notes for job postings)
CREATE TABLE IF NOT EXISTS marts.job_notes (
    note_id SERIAL PRIMARY KEY,
    jsearch_job_id varchar NOT NULL,
    user_id integer NOT NULL,
    note_text text,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_job_note_user FOREIGN KEY (user_id) REFERENCES marts.users(user_id) ON DELETE CASCADE,
    CONSTRAINT unique_job_user_note UNIQUE (jsearch_job_id, user_id)
);

COMMENT ON TABLE marts.job_notes IS 'User notes for job postings. Each user can have one note per job posting.';

-- ============================================================
-- INDEXES (for performance)
-- ============================================================

-- Indexes for raw tables
CREATE INDEX IF NOT EXISTS idx_jsearch_job_postings_campaign_id 
    ON raw.jsearch_job_postings(campaign_id);
    
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

-- Indexes for users
CREATE INDEX IF NOT EXISTS idx_users_username 
    ON marts.users(username);
    
CREATE INDEX IF NOT EXISTS idx_users_email 
    ON marts.users(email);
    
CREATE INDEX IF NOT EXISTS idx_users_role 
    ON marts.users(role);

-- Indexes for job campaigns
CREATE INDEX IF NOT EXISTS idx_job_campaigns_active 
    ON marts.job_campaigns(is_active) 
    WHERE is_active = true;
    
CREATE INDEX IF NOT EXISTS idx_job_campaigns_campaign_id 
    ON marts.job_campaigns(campaign_id);
    
CREATE INDEX IF NOT EXISTS idx_job_campaigns_user_id 
    ON marts.job_campaigns(user_id);

-- Indexes for job notes
CREATE INDEX IF NOT EXISTS idx_job_notes_job_id 
    ON marts.job_notes(jsearch_job_id);
    
CREATE INDEX IF NOT EXISTS idx_job_notes_user_id 
    ON marts.job_notes(user_id);

-- Indexes for dim_ranking (primary key already provides unique index, but we can add additional indexes if needed)
-- Note: Primary key constraint automatically creates an index on (jsearch_job_id, campaign_id)

-- Indexes for etl_run_metrics
CREATE INDEX IF NOT EXISTS idx_etl_run_metrics_dag_run_id 
    ON marts.etl_run_metrics(dag_run_id);
    
CREATE INDEX IF NOT EXISTS idx_etl_run_metrics_campaign_id 
    ON marts.etl_run_metrics(campaign_id);
    
CREATE INDEX IF NOT EXISTS idx_etl_run_metrics_run_timestamp 
    ON marts.etl_run_metrics(run_timestamp DESC);
    
CREATE INDEX IF NOT EXISTS idx_etl_run_metrics_task_name 
    ON marts.etl_run_metrics(task_name);
    
CREATE INDEX IF NOT EXISTS idx_etl_run_metrics_task_status 
    ON marts.etl_run_metrics(task_status);

-- ============================================================
-- GRANT PERMISSIONS
-- ============================================================

-- Grant permissions to application user (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_user WHERE usename = 'app_user') THEN
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE raw.jsearch_job_postings TO app_user';
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE raw.glassdoor_companies TO app_user';
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE staging.company_enrichment_queue TO app_user';
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.users TO app_user';
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.job_campaigns TO app_user';
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.dim_ranking TO app_user';
        IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'marts' AND viewname = 'dim_ranking') THEN
            BEGIN
                EXECUTE format('GRANT SELECT ON VIEW %I.%I TO %I', 'marts', 'dim_ranking', 'app_user');
            EXCEPTION
                WHEN OTHERS THEN
                    -- Ignore errors if grant fails
                    NULL;
            END;
        END IF;
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.etl_run_metrics TO app_user';
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.job_notes TO app_user';
        -- Grant sequence permissions for SERIAL columns
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE marts.users_user_id_seq TO app_user';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE marts.job_notes_note_id_seq TO app_user';
    END IF;
END $$;

-- Grant permissions to postgres user (for Docker default)
GRANT ALL PRIVILEGES ON TABLE raw.jsearch_job_postings TO postgres;
GRANT ALL PRIVILEGES ON TABLE raw.glassdoor_companies TO postgres;
GRANT ALL PRIVILEGES ON TABLE staging.company_enrichment_queue TO postgres;
GRANT ALL PRIVILEGES ON TABLE marts.users TO postgres;
GRANT ALL PRIVILEGES ON TABLE marts.job_campaigns TO postgres;
GRANT ALL PRIVILEGES ON TABLE marts.dim_ranking TO postgres;
GRANT ALL PRIVILEGES ON TABLE marts.etl_run_metrics TO postgres;
GRANT ALL PRIVILEGES ON TABLE marts.job_notes TO postgres;

