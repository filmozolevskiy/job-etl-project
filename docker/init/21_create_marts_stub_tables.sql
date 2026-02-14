-- Stub tables for marts.fact_jobs and marts.dim_companies so app queries work in environments
-- where dbt has not been run (e.g. CI). These tables are normally created by dbt; this script
-- creates empty tables with the same columns the application queries expect.
-- Idempotent: CREATE TABLE IF NOT EXISTS.

-- ============================================================
-- marts.dim_companies (referenced by fact_jobs and job queries)
-- ============================================================
CREATE TABLE IF NOT EXISTS marts.dim_companies (
    company_key varchar PRIMARY KEY,
    glassdoor_company_id varchar,
    normalized_company_name varchar,
    company_name varchar,
    company_size varchar,
    year_founded integer,
    rating numeric,
    job_count integer,
    career_opportunities_rating numeric,
    compensation_and_benefits_rating numeric,
    culture_and_values_rating numeric,
    work_life_balance_rating numeric,
    company_link varchar,
    logo varchar,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar
);

COMMENT ON TABLE marts.dim_companies IS 'Stub for CI/test: normally created by dbt. One row per distinct company.';

-- ============================================================
-- marts.fact_jobs (used by job_service and dashboard queries)
-- ============================================================
CREATE TABLE IF NOT EXISTS marts.fact_jobs (
    jsearch_job_id varchar NOT NULL,
    campaign_id integer NOT NULL,
    company_key varchar,
    job_title varchar,
    job_summary text,
    employer_name varchar,
    job_location varchar,
    employment_type varchar,
    apply_options jsonb,
    job_apply_link varchar,
    job_google_link varchar,
    job_posted_at_datetime_utc timestamp,
    extracted_skills jsonb,
    seniority_level varchar,
    remote_work_type varchar,
    job_min_salary integer,
    job_max_salary integer,
    job_salary_period varchar,
    job_salary_currency varchar,
    chatgpt_enriched_at timestamp,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system varchar,
    CONSTRAINT fact_jobs_pkey PRIMARY KEY (jsearch_job_id, campaign_id),
    CONSTRAINT fk_fact_jobs_campaign FOREIGN KEY (campaign_id)
        REFERENCES marts.job_campaigns(campaign_id) ON DELETE CASCADE
);

COMMENT ON TABLE marts.fact_jobs IS 'Stub for CI/test: normally created by dbt. One row per unique job per campaign.';
