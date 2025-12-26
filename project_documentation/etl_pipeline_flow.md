# Job Postings ETL Pipeline Flow Documentation

## Table of Contents

- [Overview](#overview)
- [Pipeline Flow Diagram](#pipeline-flow-diagram)
  - [Process Flow (Mermaid)](#process-flow-mermaid)
  - [Database Schema Diagram (DBML)](#database-schema-diagram-dbml)
- [Detailed Step-by-Step Flow](#detailed-step-by-step-flow)
  - [Step 1: Extract Job Postings (Bronze Layer)](#step-1-extract-job-postings-bronze-layer)
  - [Step 2: Normalizer Jobs (Bronze → Silver)](#step-2-normalizer-jobs-bronze--silver)
  - [Step 3: Extract Company Information (Bronze Layer)](#step-3-extract-company-information-bronze-layer)
  - [Step 4: Normalizer Companies (Bronze → Silver)](#step-4-normalizer-companies-bronze--silver)
  - [Step 5: Enricher Service (Silver Layer)](#step-5-enricher-service-silver-layer)
  - [Step 6: DBT Modelling (Silver → Gold)](#step-6-dbt-modelling-silver--gold)
  - [Step 7: Ranker Service (Gold Layer)](#step-7-ranker-service-gold-layer)
  - [Step 8: Quality Assurance](#step-8-quality-assurance)
  - [Step 9: Notifications](#step-9-notifications)
  - [Step 10: Data Consumption](#step-10-data-consumption)
  - [Step 11: Orchestration (Airflow DAG)](#step-11-orchestration-airflow-dag)

---

## Overview

This document provides a comprehensive, step-by-step description of the entire ETL pipeline flow for the Job Postings Data Platform. The pipeline follows a **Medallion architecture** pattern (Bronze → Silver → Gold) and is orchestrated by Apache Airflow.

The pipeline extracts job postings from external APIs, normalizes and enriches the data, models it into dimensional and fact tables, ranks jobs based on user preferences, performs quality checks, and sends notifications. Finally, the processed data is made available for UI and BI reporting.

---

## Pipeline Flow Diagram

### Process Flow (Mermaid)

The process flow diagram is available in a separate file: [`etl_pipeline_flow_diagram.mmd`](etl_pipeline_flow_diagram.mmd)

### Database Schema Diagram (DBML)

For a detailed database schema diagram showing all tables, relationships, and data flow, see the [DBML file](etl_pipeline_data_flow.dbml).

---

## Detailed Step-by-Step Flow

---

## Step 1: Extract Job Postings (Bronze Layer)

### Purpose
Extract job postings from JSearch API for all active user profiles and store raw JSON responses in the Bronze layer.

### Input
- **Source**: `marts.profile_preferences` table
- **Filter**: Only profiles where `is_active = true`
- **Fields Used**: 
  - `profile_id` - Unique identifier for the profile
  - `query` - Job search query string
  - `location` - Geographic location filter
  - `country` - Country filter
  - `date_window` - Date posted window (e.g., "day", "week", "month")

### Process
1. **Read Active Profiles**: The Source-extractor (Python Service) queries `marts.profile_preferences` to retrieve all active profiles
2. **API Calls**: For each active profile:
   - Calls JSearch API with profile-specific search parameters
   - Fetches job postings matching the profile criteria
   - Each API response contains multiple job postings
3. **Data Storage**: 
   - Each job posting is stored as a separate JSONB record
   - Entire API response payload is stored in `raw_payload` column
   - Links each job posting to its `profile_id`

### Output
- **Table**: `raw.jsearch_job_postings`
- **Schema**:
  - `jsearch_job_postings_key` (bigint) - Surrogate key
  - `raw_payload` (jsonb) - Complete JSON response from JSearch API
  - `dwh_load_date` (date) - Date of extraction
  - `dwh_load_timestamp` (timestamp) - Timestamp of extraction
  - `dwh_source_system` (varchar) - Source system identifier ("jsearch")
  - `profile_id` (integer) - Foreign key to `marts.profile_preferences`

### Dependencies
- Requires at least one active profile in `marts.profile_preferences`

### Code References
- **Service**: [`services/extractor/job_extractor.py`](../services/extractor/job_extractor.py)
- **Orchestration**: [`airflow/dags/jobs_etl_daily.py`](../airflow/dags/jobs_etl_daily.py) - `extract_job_postings` task

### Technical Details
- Uses MD5 hash to generate surrogate keys: `hashlib.md5(f"{job_id}|{profile_id}")`
- Bulk insert using `psycopg2.extras.execute_values` for efficiency
- Duplicates are handled by staging layer deduplication (not at raw layer)
- If no active profiles exist, service logs warning and returns empty results

---

## Step 2: Normalizer Jobs (Bronze → Silver)

### Purpose
Transform raw job postings from the Bronze layer into normalized, clean, and deduplicated data in the Silver layer.

### Input
- **Source**: `raw.jsearch_job_postings` table
- **Filter**: Only records where `raw_payload IS NOT NULL`

### Process
1. **JSON Extraction**: 
   - Extracts fields from nested `raw_payload` JSONB structure
   - Flattens nested objects and arrays
   - Handles JSON path navigation (e.g., `raw_payload->>'job_id'`)

2. **Data Cleaning**:
   - Standardizes data types (converts strings to numeric, boolean, timestamp)
   - Handles null values appropriately
   - Normalizes text fields (trimming, case handling)
   - Converts arrays to comma-separated strings where needed

3. **Deduplication**:
   - Partitions by `jsearch_job_id` (natural key)
   - Keeps the most recent record based on `dwh_load_timestamp`

### Output
- **Table**: `staging.jsearch_job_postings`
- **Key Fields**:
  - `jsearch_job_id` (varchar) - Natural key from JSearch API
  - `job_title` (varchar)
  - `job_description` (text)
  - `employer_name` (varchar) - Used for company matching
  - `job_location`, `job_city`, `job_state`, `job_country` (varchar)
  - `job_employment_type` (varchar)
  - `job_is_remote` (boolean)
  - `job_posted_at_datetime_utc` (varchar)
  - `job_min_salary`, `job_max_salary` (numeric)
  - `job_salary_period` (varchar)
  - `job_apply_link` (varchar)
  - Plus technical columns: `dwh_load_date`, `dwh_load_timestamp`, `dwh_source_system`, `profile_id`

### Dependencies
- **Step 1** must complete

### Code References
- **DBT Model**: [`dbt/models/staging/jsearch_job_postings.sql`](../dbt/models/staging/jsearch_job_postings.sql)
- **Orchestration**: [`airflow/dags/jobs_etl_daily.py`](../airflow/dags/jobs_etl_daily.py) - `normalize_jobs` task

### Technical Details
- Uses PostgreSQL JSONB operators for efficient JSON extraction
- Deduplication ensures one row per unique `jsearch_job_id`
- Handles edge cases: missing fields, null values, type mismatches

---

## Step 3: Extract Company Information (Bronze Layer)

### Purpose
Identify companies that need enrichment and extract company data from Glassdoor API. Uses fuzzy matching to select the correct company from API results when multiple matches are returned.

### Input
- **Source 1**: `staging.jsearch_job_postings` table
  - Extracts unique `employer_name` values
- **Source 2**: `staging.company_enrichment_queue` table
  - Checks enrichment status for each company
- **Source 3**: `staging.glassdoor_companies` table
  - Checks existing companies to avoid duplicates (exact match on normalized name)

### Process
1. **Company Identification**:
   - Extracts distinct `employer_name` values from `staging.jsearch_job_postings`
   - Normalizes company names: `lower(trim(employer_name))` to create `company_lookup_key`

2. **Company Filtering**:
   - Compares each `company_lookup_key` against existing companies in `staging.glassdoor_companies`
   - Only extracts companies that:
     - Are not already in `staging.glassdoor_companies` (exact match on `company_lookup_key`)
     - Are not in `company_enrichment_queue` with status `success` or `not_found`
     - Have status `pending`, `error`, or are missing from queue

3. **Fuzzy Matching for Company Selection**:
   - When Glassdoor API returns multiple company results, uses fuzzy matching to select the best match
   - Compares each API result against the original `company_lookup_key` using similarity scoring
   - Selects the company with highest similarity score (above threshold, e.g., > 0.85)
   - Handles name variations: "Microsoft" vs "Microsoft Corp" vs "Microsoft Corporation"

4. **Queue Management**:
   - Marks companies as `pending` in `staging.company_enrichment_queue`
   - Tracks `attempt_count`, `first_queued_at`, `last_attempt_at`

5. **API Extraction**:
   - For each company needing enrichment, calls Source-extractor (Python Service)
   - Fetches company data from Glassdoor Data API
   - Handles API errors gracefully

6. **Status Updates**:
   - Updates `company_enrichment_queue` with status:
     - `success` - Company found and extracted
     - `not_found` - Company not found in Glassdoor
     - `error` - API error or extraction failure
   - Records `error_message` for failed extractions

### Output
- **Table**: `raw.glassdoor_companies`
- **Schema**:
  - `glassdoor_companies_key` (bigint) - Surrogate key
  - `raw_payload` (jsonb) - Complete JSON response from Glassdoor API
  - `company_lookup_key` (varchar) - Normalized company name used for lookup
  - `dwh_load_date` (date)
  - `dwh_load_timestamp` (timestamp)
  - `dwh_source_system` (varchar) - "glassdoor"
- **Queue Updates**: `staging.company_enrichment_queue` status fields updated

### Dependencies
- **Step 2** must complete

### Code References
- **Service**: [`services/extractor/company_extractor.py`](../services/extractor/company_extractor.py)
- **Queue Model**: [`dbt/models/staging/company_enrichment_queue.sql`](../dbt/models/staging/company_enrichment_queue.sql)
- **Orchestration**: [`airflow/dags/jobs_etl_daily.py`](../airflow/dags/jobs_etl_daily.py) - `extract_companies` task

### Technical Details
- **Fuzzy Matching**: Uses string similarity algorithms (PostgreSQL `pg_trgm` extension) to select the best company match from Glassdoor API results
- **Similarity Threshold**: Typically 0.85-0.90 (85-90% match) to ensure high confidence in company selection
- **Duplicate Prevention**: Uses exact matching on normalized `company_lookup_key` to check if company already exists
- **Normalization**: `lower(trim(employer_name))` handles basic name variations (case, whitespace)
- **Queue Management**: Ensures idempotency - same company won't be extracted multiple times
- **Error Handling**: Handles API errors gracefully with retry logic

---

## Step 4: Normalizer Companies (Bronze → Silver)

### Purpose
Transform raw company data from the Bronze layer into normalized, clean, and deduplicated data in the Silver layer.

### Input
- **Source**: `raw.glassdoor_companies` table
- **Filter**: Only records where `raw_payload IS NOT NULL`

### Process
1. **JSON Extraction**:
   - Extracts fields from nested `raw_payload` JSONB structure
   - Flattens nested objects (e.g., ratings, CEO info, links)
   - Handles arrays (e.g., `competitors`, `office_locations`) as JSONB arrays

2. **Data Cleaning**:
   - Standardizes data types (converts strings to numeric, integer, timestamp)
   - Handles null values appropriately
   - Normalizes text fields (trimming, case handling)
   - Preserves complex structures as JSONB (e.g., `competitors`, `office_locations`)

3. **Deduplication**:
   - Partitions by `glassdoor_company_id` (natural key)
   - Keeps the most recent record based on `dwh_load_timestamp`

### Output
- **Table**: `staging.glassdoor_companies`
- **Key Fields**:
  - `glassdoor_company_id` (integer) - Natural key from Glassdoor API
  - `company_name` (varchar)
  - `company_description` (text)
  - `company_size`, `company_size_category` (varchar)
  - `year_founded` (integer)
  - `rating` (numeric) - Overall company rating
  - `review_count`, `salary_count`, `job_count` (integer)
  - `career_opportunities_rating`, `compensation_and_benefits_rating`, etc. (numeric)
  - `headquarters_location` (varchar)
  - `company_link`, `logo`, `reviews_link` (varchar)
  - `competitors`, `office_locations`, `best_places_to_work_awards` (jsonb) - Complex structures
  - Plus technical columns: `dwh_load_date`, `dwh_load_timestamp`, `dwh_source_system`, `company_lookup_key`

### Dependencies
- **Step 3** must complete

### Code References
- **DBT Model**: [`dbt/models/staging/glassdoor_companies.sql`](../dbt/models/staging/glassdoor_companies.sql)
- **Orchestration**: [`airflow/dags/jobs_etl_daily.py`](../airflow/dags/jobs_etl_daily.py) - `normalize_companies` task

### Technical Details
- Deduplication ensures one row per unique `glassdoor_company_id`
- Preserves complex nested structures as JSONB for flexibility

---

## Step 5: Enricher Service (Silver Layer)

### Purpose
Enrich job postings with extracted skills and seniority levels using NLP techniques.

### Input
- **Source**: `staging.jsearch_job_postings` table
  - Reads `job_description` (text) - Full job description
  - Reads `job_title` (varchar) - Job title

### Process
1. **Skills Extraction**:
   - Uses spaCy NLP library for natural language processing
   - Extracts technical skills, programming languages, tools, frameworks from job descriptions
   - May use named entity recognition (NER) or custom skill dictionaries
   - Returns structured list of skills

2. **Seniority Extraction**:
   - Analyzes job titles and descriptions for seniority indicators
   - Identifies levels: Intern, Junior, Mid-level, Senior, Lead, Principal, etc.
   - Uses pattern matching and keyword detection
   - May consider years of experience mentioned in descriptions

3. **Data Storage**:
   - Writes extracted skills to enrichment columns/tables
   - Writes extracted seniority to enrichment columns/tables
   - Updates `staging.jsearch_job_postings` or creates enrichment staging table

### Output
- **Enriched Data**: 
  - Skills extracted and stored (format TBD - could be array, JSONB, or separate table)
  - Seniority level extracted and stored (varchar or enum)
- **Location**: Either updates `staging.jsearch_job_postings` with new columns or creates separate enrichment table

### Dependencies
- **Step 2** must complete
- Can run in parallel with Step 4

### Code References
- **Service**: Enricher service (to be implemented)
- **Orchestration**: [`airflow/dags/jobs_etl_daily.py`](../airflow/dags/jobs_etl_daily.py) - `enricher` task (to be added)

### Technical Details
- **Status**: To be implemented (Phase 3)
- **NLP Library**: spaCy for skills extraction
- **Pattern Matching**: Custom rules for seniority detection
- **Performance**: May process jobs in batches for efficiency

---

## Step 6: DBT Modelling (Silver → Gold)

### Purpose
Build dimensional model (star schema) with fact and dimension tables, joining jobs to companies using exact matching on normalized company names.

### Input
- **Source 1**: `staging.jsearch_job_postings` table
  - Contains normalized job data with `employer_name`
- **Source 2**: `staging.glassdoor_companies` table
  - Contains normalized company data with `company_name`

### Process
1. **Create Dimension: Companies**:
   - Builds `marts.dim_companies` from `staging.glassdoor_companies`
   - Generates surrogate key: `company_key` (MD5 hash of `glassdoor_company_id` and normalized name)
   - Creates `normalized_company_name` for matching: `lower(trim(company_name))`
   - Deduplicates on `glassdoor_company_id` (keeps most recent record)
   - Includes all company attributes (size, ratings, links, etc.)
   - **Primary Key**: `company_key` (surrogate key) - used for all joins after fact table creation

2. **Create Fact: Jobs**:
   - Builds `marts.fact_jobs` from `staging.jsearch_job_postings`
   - **Initial Join (to get company_key)**: Joins `staging.jsearch_job_postings.employer_name` (normalized) to `marts.dim_companies.normalized_company_name` using exact matching
   - **Stores company_key**: Once matched, stores `company_key` (surrogate key) in fact table as foreign key
   - **Company Key Only**: Stores only `company_key` (foreign key) in fact table, not `employer_name` or company attributes
   - Deduplicates on `jsearch_job_id`
   - **Future Joins**: After fact table creation, all queries join `fact_jobs.company_key` to `dim_companies.company_key` directly

3. **Create Dimension: Ranking**:
   - Creates table structure for `marts.dim_ranking`
   - Table is empty initially (populated by Ranker service in Step 7)
   - Ensures schema exists before Ranker runs

### Output
- **Table 1**: `marts.fact_jobs`
  - **Schema**:
    - `jsearch_job_id` (varchar) - Primary key
    - `company_key` (varchar) - Foreign key to `marts.dim_companies.company_key` (ONLY company reference)
    - `job_title` (varchar)
    - `job_location` (varchar)
    - `job_employment_type` (varchar)
    - `apply_options` (jsonb)
    - `job_is_remote` (boolean)
    - `job_posted_at_datetime_utc` (varchar)
    - Technical columns: `dwh_load_date`, `dwh_load_timestamp`, `dwh_source_system`
  
- **Table 2**: `marts.dim_companies`
  - **Schema**:
    - `company_key` (varchar) - Primary key (surrogate key - MD5 hash)
    - `glassdoor_company_id` (integer) - Natural key from Glassdoor
    - `normalized_company_name` (varchar) - Used for fuzzy matching
    - `company_name` (varchar) - Display name
    - `company_size` (varchar) - Company size category
    - `year_founded` (integer) - Year company was founded
    - `rating` (numeric) - Overall company rating
    - `job_count` (integer) - Number of job postings
    - `career_opportunities_rating` (numeric) - Career opportunities rating
    - `compensation_and_benefits_rating` (numeric) - Compensation and benefits rating
    - `culture_and_values_rating` (numeric) - Culture and values rating
    - `work_life_balance_rating` (numeric) - Work-life balance rating
    - `company_link` (varchar) - Link to company page
    - `dwh_load_date` (date) - Data warehouse load date
    - `dwh_load_timestamp` (timestamp) - Data warehouse load timestamp
    - `dwh_source_system` (varchar) - Source system identifier
  
- **Table 3**: `marts.dim_ranking`
  - **Schema** (structure only, no data):
    - `jsearch_job_id` (varchar) - Foreign key to `marts.fact_jobs`
    - `profile_id` (integer) - Foreign key to `marts.profile_preferences`
    - `rank_score` (numeric) - 0-100 ranking score
    - `rank_explain` (jsonb) - Scoring breakdown
    - `ranked_at` (timestamp)
    - Technical columns

### Dependencies
- **Step 2** and **Step 4** must complete
- **Step 5** (Enricher) should complete if skills/seniority are used in ranking

### Code References
- **DBT Models**:
  - [`dbt/models/marts/fact_jobs.sql`](../dbt/models/marts/fact_jobs.sql)
  - [`dbt/models/marts/dim_companies.sql`](../dbt/models/marts/dim_companies.sql)
  - [`dbt/models/marts/dim_ranking.sql`](../dbt/models/marts/dim_ranking.sql)
- **Orchestration**: [`airflow/dags/jobs_etl_daily.py`](../airflow/dags/jobs_etl_daily.py) - `dbt_modelling` task

### Technical Details
- **Surrogate Key**: `company_key` is MD5 hash of `glassdoor_company_id || '|' || normalized_company_name`
- **Initial Join**: Uses normalized company names to match jobs to companies and retrieve `company_key`
- **Future Joins**: All queries after fact table creation join on `company_key` directly

---

## Step 7: Ranker Service (Gold Layer)

### Purpose
Calculate job ranking scores for each (job, profile) pair based on profile preferences and job/company attributes.

### Input
- **Source 1**: `marts.profile_preferences` table
  - Reads active profiles (`is_active = true`)
  - Profile preferences: skills, salary range, remote preference, seniority, etc.
  - **Ranking weights**: Custom weights stored in `ranking_weights` JSONB column
    - Format: `{"location_match": 15.0, "salary_match": 15.0, ...}` (percentages, must sum to 100%)
    - If NULL/empty, falls back to `ranking_config.json` defaults
- **Source 2**: `marts.fact_jobs` table
  - Job attributes: title, location, employment type, remote flag
- **Source 3**: `marts.dim_companies` table (via join)
  - Company attributes: ratings, size, culture scores, etc.

### Process
1. **Data Retrieval**:
   - Retrieves all active profiles from `marts.profile_preferences`
   - Retrieves all jobs from `marts.fact_jobs`
   - Joins to `marts.dim_companies` via `company_key` to get company attributes

2. **Score Calculation**:
   - For each (job, profile) pair, calculates `rank_score` (0-100)
   - Uses profile-specific ranking weights if available, otherwise uses config file defaults
   - Scoring factors (with configurable weights):
     - Location match
     - Salary match (with currency conversion)
     - Company size match
     - Skills match (if available from Enricher)
     - Keyword/title match
     - Employment type match
     - Seniority level match
     - Remote work type match
     - Recency (posting date)

3. **Explanation Generation**:
   - Generates `rank_explain` JSON with breakdown of each factor's contribution
   - Format: `{"skills_match": 20, "salary_match": 15, "company_rating": 10, ...}`

4. **Data Storage**:
   - Writes/updates `marts.dim_ranking` with:
     - `jsearch_job_id` + `profile_id` (composite key)
     - `rank_score` (0-100)
     - `rank_explain` (JSONB)
     - `ranked_at` (timestamp)

### Output
- **Table**: `marts.dim_ranking`
- **Schema**:
  - `jsearch_job_id` (varchar) - Foreign key to `marts.fact_jobs`
  - `profile_id` (integer) - Foreign key to `marts.profile_preferences`
  - `rank_score` (numeric) - 0-100 ranking score
  - `rank_explain` (jsonb) - Scoring breakdown
  - `ranked_at` (timestamp) - When ranking was calculated
  - `ranked_date` (date) - Date of ranking
  - Technical columns: `dwh_load_timestamp`, `dwh_source_system`

### Dependencies
- **Step 6** must complete
- **Step 5** (Enricher) should complete if skills/seniority are used in ranking

### Code References
- **Service**: Ranker service (to be implemented)
- **Table Structure**: [`dbt/models/marts/dim_ranking.sql`](../dbt/models/marts/dim_ranking.sql)
- **Orchestration**: [`airflow/dags/jobs_etl_daily.py`](../airflow/dags/jobs_etl_daily.py) - `rank_jobs` task

### Technical Details
- **Status**: Implemented (Phase 3)
- **Scoring Algorithm**: Custom algorithm based on profile preferences with configurable weights
- **Weight Configuration**: 
  - Per-profile weights stored in `marts.profile_preferences.ranking_weights` (JSONB)
  - Default weights in `services/ranker/ranking_config.json`
  - Weights are percentages and must sum to 100% if provided
- **Performance**: Processes jobs in batches for efficiency
- **Idempotency**: Can be run multiple times (updates existing rankings)

---

## Step 8: Quality Assurance

### Purpose
Validate data quality and integrity across all Gold layer tables.

### Input
- **Source**: Gold layer tables
  - `marts.fact_jobs`
  - `marts.dim_companies`
  - `marts.dim_ranking`
  - `marts.profile_preferences`

### Process
1. **Schema Validation**:
   - Validates table structures match expected schemas
   - Checks data types, constraints, indexes

2. **Referential Integrity**:
   - Validates foreign keys:
     - `marts.fact_jobs.company_key` references `marts.dim_companies.company_key`
     - `marts.dim_ranking.jsearch_job_id` references `marts.fact_jobs.jsearch_job_id`
     - `marts.dim_ranking.profile_id` references `marts.profile_preferences.profile_id`

3. **Data Completeness**:
   - Checks for required fields (non-null constraints)
   - Validates key fields are populated

4. **Data Accuracy**:
   - Validates data ranges (e.g., rank_score between 0-100)
   - Checks for invalid values
   - Validates JSON structures (rank_explain)

5. **Business Rules**:
   - Custom business logic validations
   - Data quality thresholds

### Output
- **Test Results**: Pass/fail status for each test
- **Logs**: Detailed test results logged to dbt logs
- **Failure Handling**: Pipeline fails if critical tests fail

### Dependencies
- **Step 6** and **Step 7** must complete

### Code References
- **Test Definitions**: [`dbt/models/*/schema.yml`](../dbt/models/marts/schema.yml)
- **Orchestration**: [`airflow/dags/jobs_etl_daily.py`](../airflow/dags/jobs_etl_daily.py) - `dbt_tests` task

### Technical Details
- Uses dbt's built-in testing framework
- Tests defined in `schema.yml` files
- Can include custom SQL tests
- Critical tests cause pipeline failure; warnings may be logged only

---

## Step 9: Notifications

### Purpose
Send daily pipeline summary via email to notify stakeholders of pipeline execution results.

### Input
- **Source**: Pipeline execution results and statistics
  - Extraction counts (jobs, companies)
  - Ranking statistics
  - Quality test results
  - Error messages (if any)

### Process
1. **Summary Generation**:
   - Collects statistics from all pipeline steps
   - Formats summary with:
     - Total jobs extracted
     - Total companies extracted
     - Total jobs ranked
     - Quality test results
     - Any errors or warnings

2. **Email Composition**:
   - Creates HTML/text email with summary
   - Includes key metrics and status

3. **Email Delivery**:
   - Sends email via SMTP server
   - Recipients: Profile email addresses from `marts.profile_preferences`

### Output
- **Email Notifications**: Sent to SMTP server for delivery
- **Logs**: Notification status logged

### Dependencies
- **Step 8** must complete

### Code References
- **Service**: Notification service (to be implemented)
- **Orchestration**: [`airflow/dags/jobs_etl_daily.py`](../airflow/dags/jobs_etl_daily.py) - `notify_daily` task

### Technical Details
- **Status**: To be implemented
- **SMTP Configuration**: Configured via environment variables
- **Email Format**: HTML with summary tables and metrics
- **Error Handling**: Logs errors but doesn't fail pipeline

---

## Step 10: Data Consumption

### Purpose
Expose processed data from the Gold layer for end-user consumption via UI and BI tools.

### Input
- **Source**: Gold layer tables
  - `marts.fact_jobs` - Job facts
  - `marts.dim_companies` - Company dimensions
  - `marts.dim_ranking` - Job rankings per profile
  - `marts.profile_preferences` - User profiles

### Process
1. **UI Interface**:
   - Profile Management UI reads/writes `marts.profile_preferences`
   - Job browsing UI reads from:
     - `marts.fact_jobs` (joined to `marts.dim_companies` via `company_key`)
     - `marts.dim_ranking` (filtered by `profile_id`)
   - Displays ranked jobs with company information

2. **BI & Reporting**:
   - BI tools (e.g., Tableau) connect to Gold layer tables
   - Create dashboards and reports
   - Analyze job trends, company ratings, ranking patterns

### Output
- **UI Access**: Data accessible via Profile Management UI
- **BI Access**: Data accessible via BI tools (direct database connection or API)

### Dependencies
- **Step 6** and **Step 7** must complete

### Code References
- **UI Application**: [`profile_ui/app.py`](../profile_ui/app.py)

### Technical Details
- **UI**: Flask/Python web application for profile management
- **BI**: Direct PostgreSQL connection
- **Performance**: Indexes on foreign keys for fast joins
- **Security**: Access controls via database permissions

---

## Step 11: Orchestration (Airflow DAG)

### Purpose
Orchestrate all pipeline steps in the correct sequence with proper error handling and scheduling.

### DAG Configuration
- **DAG ID**: `jobs_etl_daily`
- **Schedule**: Daily at 07:00 America/Toronto (`0 7 * * *`)
- **Timezone**: America/Toronto (configured in docker-compose)
- **Catchup**: Disabled (`catchup=False`)
- **Tags**: `["etl", "jobs", "daily"]`

### Task Dependencies
```
extract_job_postings
    ↓
normalize_jobs
    ↓
extract_companies
    ↓
normalize_companies
    ↓
dbt_modelling
    ↓
rank_jobs
    ↓
dbt_tests
    ↓
notify_daily
```

**Note**: `enricher` task (Step 5) can run in parallel with `normalize_companies`.

### Error Handling
- **Retries**: 3 attempts per task
- **Retry Delay**: 5 minutes between retries
- **Email on Failure**: Enabled (`email_on_failure=True`)
- **Email on Retry**: Disabled (`email_on_retry=False`)

### Code References
- **DAG Definition**: [`airflow/dags/jobs_etl_daily.py`](../airflow/dags/jobs_etl_daily.py)
- **Task Types**:
  - `BashOperator` - For dbt commands
  - `PythonOperator` - For Python service calls (to be implemented)

### Technical Details
- **Default Args**: Owner, retries, email settings configured
- **Task Execution**: Each task runs in Airflow worker
- **Logging**: All task logs stored in Airflow logs directory
- **Monitoring**: Task status visible in Airflow UI
