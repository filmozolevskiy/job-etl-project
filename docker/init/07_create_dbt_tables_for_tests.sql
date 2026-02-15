-- ============================================================
-- Create dbt-built tables for integration tests
-- These are normally created by dbt models but must exist for
-- migrations (e.g. 09, 15) and integration tests
-- ============================================================

DROP TABLE IF EXISTS marts.dim_companies CASCADE;
DROP TABLE IF EXISTS marts.fact_jobs CASCADE;
DROP TABLE IF EXISTS staging.jsearch_job_postings CASCADE;

CREATE TABLE staging.jsearch_job_postings (
    jsearch_job_postings_key bigint,
    jsearch_job_id varchar,
    campaign_id integer,
    job_title varchar,
    employer_name varchar,
    job_location varchar,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar
);

CREATE TABLE marts.dim_companies (
    company_key varchar PRIMARY KEY,
    company_name varchar,
    company_size varchar,
    rating numeric,
    company_link varchar,
    logo varchar,
    glassdoor_company_id bigint,
    normalized_company_name varchar,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar
);

CREATE TABLE marts.fact_jobs (
    jsearch_job_id varchar NOT NULL,
    campaign_id integer NOT NULL,
    company_key varchar,
    job_title varchar,
    job_summary text,
    employer_name varchar,
    job_location varchar,
    employment_type varchar,
    job_posted_at_datetime_utc timestamp,
    apply_options jsonb,
    job_apply_link varchar,
    extracted_skills jsonb,
    job_min_salary numeric,
    job_max_salary numeric,
    job_salary_period varchar,
    job_salary_currency varchar,
    remote_work_type varchar,
    seniority_level varchar,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar,
    CONSTRAINT fact_jobs_pkey PRIMARY KEY (jsearch_job_id, campaign_id)
);

-- staging.chatgpt_enrichments (required by campaign deletion, ChatGPT enricher, GET_JOB_BY_ID)
DROP TABLE IF EXISTS staging.chatgpt_enrichments CASCADE;
CREATE TABLE staging.chatgpt_enrichments (
    chatgpt_enrichment_key BIGSERIAL PRIMARY KEY,
    jsearch_job_postings_key BIGINT NOT NULL,
    job_summary TEXT,
    chatgpt_extracted_skills JSONB,
    chatgpt_extracted_location VARCHAR(255),
    chatgpt_seniority_level VARCHAR(50),
    chatgpt_remote_work_type VARCHAR(50),
    chatgpt_job_min_salary NUMERIC,
    chatgpt_job_max_salary NUMERIC,
    chatgpt_salary_period VARCHAR(50),
    chatgpt_salary_currency VARCHAR(10),
    chatgpt_enriched_at TIMESTAMP,
    chatgpt_enrichment_status JSONB,
    dwh_load_date DATE DEFAULT CURRENT_DATE,
    dwh_load_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_chatgpt_enrichments_job_postings_key UNIQUE (jsearch_job_postings_key)
);
