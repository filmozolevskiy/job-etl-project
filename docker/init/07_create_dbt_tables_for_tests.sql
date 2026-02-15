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
