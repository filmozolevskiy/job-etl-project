-- ============================================================
-- DDL Statements for All Tables
-- Generated in requested format
-- ============================================================

-- ============================================================
-- RAW LAYER TABLES
-- ============================================================

CREATE TABLE raw_jsearch_job_postings
(
    jsearch_job_postings_key bigint NOT NULL PRIMARY KEY,
    raw_payload text,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system char(50),
    profile_id int
);

CREATE TABLE raw_glassdoor_companies
(
    glassdoor_companies_key bigint NOT NULL PRIMARY KEY,
    raw_payload text,
    company_lookup_key char(255),
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system char(50)
);

-- ============================================================
-- STAGING LAYER TABLES
-- ============================================================

CREATE TABLE staging_glassdoor_companies
(
    glassdoor_companies_key bigint NOT NULL PRIMARY KEY,
    company_lookup_key char(255),
    glassdoor_company_id int NOT NULL,
    company_name char(255),
    website char(255),
    industry char(100),
    company_description text,
    company_size char(50),
    company_size_category char(50),
    company_type char(50),
    revenue char(100),
    year_founded int,
    stock char(10),
    headquarters_location char(255),
    rating numeric,
    review_count int,
    salary_count int,
    job_count int,
    business_outlook_rating numeric,
    career_opportunities_rating numeric,
    compensation_and_benefits_rating numeric,
    culture_and_values_rating numeric,
    diversity_and_inclusion_rating numeric,
    recommend_to_friend_rating numeric,
    ceo_rating numeric,
    senior_management_rating numeric,
    work_life_balance_rating numeric,
    ceo char(100),
    company_link char(255),
    logo char(255),
    reviews_link char(255),
    jobs_link char(255),
    faq_link char(255),
    competitors text,
    office_locations text,
    best_places_to_work_awards text,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system char(50)
);

CREATE TABLE staging_jsearch_job_postings
(
    jsearch_job_postings_key bigint NOT NULL PRIMARY KEY,
    profile_id int,
    jsearch_job_id char(100) NOT NULL,
    job_title char(255),
    job_description text,
    employer_name char(255),
    job_city char(100),
    job_state char(50),
    job_country char(10),
    job_location char(255),
    job_latitude numeric,
    job_longitude numeric,
    job_employment_type char(50),
    job_employment_types text,
    employment_types char(255),
    job_is_remote boolean,
    job_posted_at char(50),
    job_posted_at_timestamp bigint,
    job_posted_at_datetime_utc timestamp,
    job_min_salary numeric,
    job_max_salary numeric,
    job_salary_period char(20),
    job_apply_link char(500),
    job_google_link char(500),
    job_apply_is_direct boolean,
    apply_options text,
    job_publisher char(100),
    job_benefits text,
    job_highlights text,
    job_onet_soc char(20),
    job_onet_job_zone char(10),
    employer_logo char(500),
    employer_website char(500),
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system char(50)
);

CREATE TABLE staging_company_enrichment_queue
(
    company_lookup_key char(255) NOT NULL PRIMARY KEY,
    enrichment_status char(50),
    first_queued_at timestamp,
    last_attempt_at timestamp,
    completed_at timestamp,
    error_message text,
    attempt_count int
);

-- ============================================================
-- MARTS LAYER TABLES
-- ============================================================

CREATE TABLE marts_dim_companies
(
    company_key char(32) NOT NULL PRIMARY KEY,
    glassdoor_company_id int NOT NULL,
    normalized_company_name char(255),
    company_name char(255),
    company_size char(50),
    year_founded int,
    rating numeric,
    job_count int,
    career_opportunities_rating numeric,
    compensation_and_benefits_rating numeric,
    culture_and_values_rating numeric,
    work_life_balance_rating numeric,
    company_link char(255),
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system char(50)
);

CREATE TABLE marts_fact_jobs
(
    jsearch_job_id char(100) NOT NULL PRIMARY KEY,
    company_key char(32),
    job_title char(255),
    employer_name char(255),
    job_location char(255),
    job_employment_type char(50),
    apply_options text,
    job_is_remote boolean,
    job_posted_at_datetime_utc timestamp,
    dwh_load_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system char(50)
);

CREATE TABLE marts_dim_ranking
(
    jsearch_job_id char(100) NOT NULL,
    profile_id int NOT NULL,
    rank_score numeric NOT NULL,
    rank_explain text,
    ranked_at timestamp,
    ranked_date date,
    dwh_load_timestamp timestamp,
    dwh_source_system char(50),
    PRIMARY KEY (jsearch_job_id, profile_id)
);

CREATE TABLE marts_profile_preferences
(
    profile_id int NOT NULL PRIMARY KEY,
    profile_name char(100) NOT NULL,
    is_active boolean NOT NULL,
    query char(255),
    location char(255),
    country char(10),
    date_window char(50),
    email char(255),
    skills char(500),
    min_salary numeric,
    max_salary numeric,
    remote_preference char(50),
    seniority char(50),
    created_at timestamp,
    updated_at timestamp,
    total_run_count int,
    last_run_at timestamp,
    last_run_status char(50),
    last_run_job_count int
);
