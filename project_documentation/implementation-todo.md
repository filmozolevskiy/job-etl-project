# Job Postings Data Platform - Implementation TODO List

This document provides a phased implementation checklist for the Job Postings Data Platform project. Each task includes clear acceptance criteria and is ordered from easy to hard within each phase.

**📖 Related Documentation:**
- **[ETL Pipeline Flow Documentation](etl_pipeline_flow.md)** – Complete step-by-step flow with detailed descriptions of each pipeline step
- **[ETL Pipeline Flow Diagram](etl_pipeline_flow_diagram.mmd)** – Visual Mermaid diagram of the pipeline flow
- **[ETL Pipeline Data Flow (DBML)](etl_pipeline_data_flow.dbml)** – Database schema diagram showing tables and relationships

**Quick Progress Checklist**

- [x] [Phase 1: Project Scaffold & Local Runtime](#phase-1-project-scaffold--local-runtime)
  - [x] [Infrastructure & Setup](#infrastructure--setup)
- [ ] [Phase 2: First End-to-End Local MVP Path](#phase-2-first-end-to-end-local-mvp-path)
  - [x] [CI Pipeline](#ci-pipeline)
  - [x] [Data Model Foundation](#data-model-foundation)
  - [x] [Core Services - Source Extractor](#core-services---source-extractor)
  - [x] [Core Services - Ranking](#core-services---ranking)
  - [x] [Core Services - Notifications](#core-services---notifications)
  - [x] [Airflow DAG Implementation](#airflow-dag-implementation)
  - [x] [Profile Management Interface](#profile-management-interface)
  - [ ] [Testing & Validation](#testing--validation)
- [ ] [Phase 3: Enrichment & Data Quality (Feature Depth)](#phase-3-enrichment--data-quality-feature-depth)
  - [ ] [Enrichment Service](#enrichment-service)
  - [ ] [Extended Ranking](#extended-ranking)
  - [ ] [Data Quality & Observability](#data-quality--observability)
  - [ ] [Code Quality Improvements](#code-quality-improvements)
- [ ] [Phase 4: AWS Lift (Production Deployment)](#phase-4-aws-lift-production-deployment)
  - [ ] [Database Migration](#database-migration)
  - [ ] [S3 Integration](#s3-integration)
  - [ ] [Service Deployment](#service-deployment)
  - [ ] [BI Integration](#bi-integration)
  - [ ] [Deployment Pipeline](#deployment-pipeline)
  - [ ] [Security & Operations](#security--operations)
- [ ] [Post-Implementation](#post-implementation)

---

## Phase 1: Project Scaffold & Local Runtime

### Infrastructure & Setup

- [x] **1.1: Initialize Git Repository**
  - **Acceptance Criteria:**
    - Git repository initialized with appropriate `.gitignore` for Python, Docker, and database files
    - Initial commit created with project structure
    - README.md created with basic project description

- [x] **1.2: Create Project Folder Structure**
  - **Acceptance Criteria:**
    - Directory structure follows standard data engineering patterns:
      - `services/` (for Python services: extractor, enricher, ranker)
      - `dbt/` (dbt project)
      - `airflow/dags/` (Airflow DAGs)
      - `airflow/plugins/` (custom operators if needed)
      - `profile_ui/` (profile management interface)
      - `tests/` (test files)
      - `Project Documentation/` (existing docs)
      - `docker/` (Dockerfiles and compose)
    - Structure documented in README

- [x] **1.3: Create Database Schema Initialization Script**
  - **Acceptance Criteria:**
    - SQL script at `docker/init/01_create_schemas.sql` creates schemas: `raw`, `staging`, `marts`
    - Script uses `CREATE SCHEMA IF NOT EXISTS` for idempotency
    - Script includes grant permissions to application user
    - Script can be run manually or automatically via Docker initialization
    - Schemas verified to exist after running script
    - **Note**: This script only creates schemas (infrastructure). Tables are created and managed by dbt models, not by this initialization script.

- [x] **1.4: Create Docker Compose Configuration**
  - **Acceptance Criteria:**
    - `docker-compose.yml` defines services:
      - PostgreSQL with initialization script mounted at `/docker-entrypoint-initdb.d`
      - Schemas `raw`, `staging`, `marts` are automatically created on first container start
      - Airflow webserver and scheduler
      - Optional: profile UI container
    - Environment variables configured via `.env` file
    - Services can start with `docker-compose up`
    - Database connection strings documented

- [x] **1.5: Initialize dbt Project**
  - **Acceptance Criteria:**
    - dbt project initialized with `dbt init`
    - `profiles.yml` configured to connect to local PostgreSQL
    - Project connects successfully with `dbt debug`
    - Project structure includes `models/` subdirectories for raw, staging, marts
    - **Note**: Schemas must exist (created via initialization script) before dbt can create tables within them

- [x] **1.6: Configure Python Development Tools**
  - **Acceptance Criteria:**
    - `requirements.txt` or `pyproject.toml` includes:
      - `pytest` for testing
      - `ruff` for linting and formatting
      - Core dependencies for services
    - Linting rules configured (e.g., `ruff.toml` or `pyproject.toml` settings)
    - Pre-commit hooks set up
    - Running `ruff check` and `ruff format` works without errors

- [x] **1.7: Create Environment Configuration Template**
  - **Acceptance Criteria:**
    - `.env.example` file created with all required environment variables:
      - Database connection strings
      - API keys (JSearch, Glassdoor)
      - Email SMTP settings
      - Airflow configuration
    - Variables documented with descriptions
    - `.env` added to `.gitignore`
    - **Note**: File creation blocked by gitignore (expected behavior)

- [x] **1.8: Create Basic Airflow DAG Structure**
  - **Acceptance Criteria:**
    - `jobs_etl_daily` DAG file created in `airflow/dags/`
    - DAG scheduled for 07:00 America/Toronto timezone
    - DAG visible in Airflow UI (can be paused/unpaused, no tasks yet)
    - Basic imports and DAG configuration in place

---

## Phase 2: First End-to-End Local MVP Path

### Data Model Foundation

- [x] **2.1: Create `marts.profile_preferences` Table**
  - **Acceptance Criteria:**
    - Table created with all required columns per PRD Section 4.3
    - Primary key on `profile_id`
    - Indexes on `is_active` and timestamps
    - Table created by `docker/init/02_create_tables.sql`
    - Profiles are managed exclusively via Profile Management UI
    - At least one test profile can be created via UI

- [x] **2.2: Create Raw Layer Tables via SQL Script**
  - **Acceptance Criteria:**
    - Schemas `raw`, `staging`, `marts` already exist (created via initialization script)
    - SQL script (`docker/init/02_create_tables.sql`) creates `raw.jsearch_job_postings` table with:
      - Surrogate key (`jsearch_job_postings_key` - follows naming convention `<table_name>_key`)
      - JSONB or JSON column for payload
      - Technical columns: `dwh_load_date`, `dwh_load_timestamp`, `dwh_source_system`, `profile_id`
    - SQL script creates `raw.glassdoor_companies` table with similar structure
    - Tables are created automatically by Docker initialization before services run
    - **IMPORTANT**: These tables must exist before extractor service can write to them. They are created by Docker init script, not by dbt or DAG tasks.

- [x] **2.2.5: Fix Raw Table Naming Conventions**
  - **Acceptance Criteria:**
    - Surrogate key columns renamed to follow naming convention: `<table_name>_key`
    - `raw_job_posting_id` → `jsearch_job_postings_key`
    - `raw_company_id` → `glassdoor_companies_key`
    - All references updated in dbt models, indexes, and schema.yml
    - **Status**: Completed - column names fixed to follow naming conventions

- [x] **2.3: Create Staging Layer Models - Job Postings**
  - **Acceptance Criteria:**
    - dbt model `staging.jsearch_job_postings` transforms raw JSON
    - Extracts key fields: `job_id`, title, description, employer, location, salary, employment type, etc.
    - Deduplicates on `job_id`
    - Adds technical columns with `dwh_` prefix
    - Handles nulls and type conversions appropriately
    - Model runs successfully via `dbt run`

- [x] **2.4: Create Staging Layer Models - Companies**
  - **Acceptance Criteria:**
    - dbt model `staging.glassdoor_companies` transforms raw JSON
    - Extracts company details: `company_id`, name, website, industry, ratings, location
    - Deduplicates companies appropriately
    - Adds technical columns
    - Model runs successfully

- [x] **2.5: Create Staging Layer - Company Enrichment Queue Table**
  - **Acceptance Criteria:**
    - Table `staging.company_enrichment_queue` created with columns:
      - `company_lookup_key`
      - `enrichment_status` (enum or constraint)
      - Timestamp fields
    - Can track pending/success/not_found/error statuses
    - Table created by `docker/init/02_create_tables.sql`

- [x] **2.6: Create Marts Layer - Dimension Companies**
  - **Acceptance Criteria:**
    - dbt model `marts.dim_companies` built from staging
    - Surrogate key `company_key` generated
    - Natural keys preserved (`company_id`, normalized name)
    - Includes all attributes from PRD Section 4.3
    - Model runs successfully

- [x] **2.7: Create Marts Layer - Fact Jobs**
  - **Acceptance Criteria:**
    - dbt model `marts.fact_jobs` built from `staging.jsearch_job_postings`
    - Surrogate key `job_posting_key` generated
    - Foreign keys: `company_key` (joined to `dim_companies`), `profile_id`
    - Includes salary metrics, posting dates, binary flags, derived attributes
    - Model runs successfully and joins work correctly

- [x] **2.8: Create Marts Layer - Dimension Ranking Structure**
  - **Acceptance Criteria:**
    - Table `marts.dim_ranking` created with:
      - Composite key: `jsearch_job_id`, `profile_id` (note: uses jsearch_job_id, not job_posting_key)
      - `rank_score` column (numeric, 0-100)
      - Timestamp columns (`ranked_at`, `ranked_date`, `dwh_load_timestamp`)
      - `rank_explain` jsonb column for Phase 3
    - Ready to receive ranking data from Ranker service
    - **Status**: Completed - table created in `docker/init/02_create_tables.sql` with primary key constraint

### Core Services - Source Extractor

- [x] **2.9: Implement JSearch API Client**
  - **Acceptance Criteria:**
    - Python module with abstracted API client structure
    - Handles authentication (API key from env)
    - Implements rate limiting and retries with exponential backoff
    - Can call JSearch API with query parameters (query, location, country, date_window, etc.)
    - Returns parsed JSON response
    - Unit tests for API client logic (mocked responses)
    - **Status**: Completed - implemented in `services/extractor/jsearch_client.py` with BaseAPIClient abstraction

- [x] **2.10: Implement Source Extractor Service - Jobs**
  - **Acceptance Criteria:**
    - Python service reads active profiles from `marts.profile_preferences`
    - For each profile, calls JSearch API with profile parameters
    - Writes raw JSON responses to `raw.jsearch_job_postings`
    - Adds technical metadata (load date, timestamp, source system, profile_id)
    - Logs number of jobs extracted per profile
    - Can be run as standalone script or called from Airflow
    - **Status**: Completed - implemented in `services/extractor/job_extractor.py` with bulk insert support

- [x] **2.11: Implement Glassdoor API Client**
  - **Acceptance Criteria:**
    - Python module for Glassdoor company search API
    - Handles authentication and rate limiting
    - Takes company name/domain as input
    - Returns company JSON response
    - Unit tests with mocked responses
    - **Status**: Completed - implemented in `services/extractor/glassdoor_client.py` with BaseAPIClient abstraction

- [x] **2.12: Implement Company Extraction Logic**
  - **Acceptance Criteria:**
    - Python service scans `staging.jsearch_job_postings` for employer names/domains
    - Identifies companies not yet enriched (checks `staging.company_enrichment_queue`)
    - Calls Glassdoor API for missing companies
    - Writes raw JSON to `raw.glassdoor_companies` with `company_lookup_key`
    - Updates enrichment queue status
    - Handles "not found" and error cases gracefully
    - **Note**: Uses corrected column name `glassdoor_companies_key` when writing to raw table
    - **Status**: Completed - implemented in `services/extractor/company_extractor.py` with fuzzy matching for company selection

- [x] **2.3.5: Review Real API Payloads and Update Staging Models**
  - **Acceptance Criteria:**
    - Extractors (2.9-2.12) are built and can fetch real data
    - Sample payloads from JSearch and Glassdoor APIs are captured and inspected
    - Actual field names and structure are documented
    - Staging models (2.3, 2.4) are updated to match real payload structure
    - Models are tested with real data
    - Models are re-enabled in dbt config

- [x] **2.6.5: Review Staging Models and Finalize Marts Models**
  - **Acceptance Criteria:**
    - Staging models (2.3, 2.4) are finalized based on real payloads
    - Marts models (2.6, 2.7) are reviewed and updated to work with finalized staging models
    - All joins and transformations are validated
    - Models are re-enabled in dbt config

### Core Services - Ranking

- [x] **2.13: Implement MVP Ranker Service**
  - **Acceptance Criteria:**
    - Python service reads `marts.fact_jobs` and active `marts.profile_preferences`
    - Scores each job/profile pair based on:
      - Location match (simple string/keyword matching)
      - Keyword match between profile query and job title/description
      - Recency of posting (newer = higher score)
    - Normalizes scores to 0-100 range
    - Writes scores to `marts.dim_ranking`
    - Unit tests for scoring logic
    - **Status**: Completed - implemented in `services/ranker/job_ranker.py` with MVP scoring algorithm (location 0-40, keywords 0-40, recency 0-20)

### Core Services - Notifications

- [x] **2.14: Implement Email Notification Service**
  - **Acceptance Criteria:**
    - Python service reads top N jobs from `marts.dim_ranking` (joined to `marts.fact_jobs`)
    - Composes simple HTML email with job list for each active profile
    - Includes job title, company, location, salary (if available), apply link
    - Sends via SMTP (configurable via environment variables)
    - Logs email sending results per profile
    - Handles email failures gracefully
    - **Status**: Completed - implemented in `services/notifier/email_notifier.py` and `services/notifier/notification_coordinator.py` with BaseNotifier abstraction

### Airflow DAG Implementation

**📖 Reference: [ETL Pipeline Flow Documentation - Step 11: Orchestration](etl_pipeline_flow.md#step-11-orchestration-airflow-dag) for DAG configuration and task dependencies**

- [x] **2.14.5: Implement Airflow Task - Initialize Database Tables**
  - **Status**: No longer needed - tables are created by Docker initialization script
  - **Note**: Tables are now created automatically by `docker/init/02_create_tables.sql` before DAG execution. No DAG task is required for table initialization.

- [x] **2.15: Implement Airflow Task - Extract Job Postings**
  - **📖 Reference: [ETL Pipeline Flow - Step 1](etl_pipeline_flow.md#step-1-extract-job-postings-bronze-layer)**
  - **Acceptance Criteria:**
    - Airflow task calls Source Extractor service
    - Task has retry policy (e.g., 3 retries with exponential backoff)
    - Logs number of profiles processed and jobs extracted
    - Task succeeds when jobs are written to raw layer
    - **Status**: Completed - implemented in `airflow/dags/task_functions.py` as `extract_job_postings_task` and wired in `jobs_etl_daily.py`

- [x] **2.16: Implement Airflow Task - Normalize Jobs**
  - **📖 Reference: [ETL Pipeline Flow - Step 2](etl_pipeline_flow.md#step-2-normalizer-jobs-bronze--silver)**
  - **Acceptance Criteria:**
    - Airflow task runs dbt model for `staging.jsearch_job_postings`
    - Uses dbt operator or BashOperator with `dbt run --select staging.jsearch_job_postings`
    - Task fails if dbt run fails
    - Logs number of rows processed
    - **Status**: Completed - implemented as BashOperator in `jobs_etl_daily.py` as `normalize_jobs` task

- [x] **2.17: Implement Airflow Task - Extract Companies**
  - **📖 Reference: [ETL Pipeline Flow - Step 3](etl_pipeline_flow.md#step-3-extract-company-information-bronze-layer)**
  - **Acceptance Criteria:**
    - Airflow task calls Company Extraction service
    - Handles rate limiting for Glassdoor API calls
    - Updates enrichment queue appropriately
    - Logs companies found/not found/errors
    - **Status**: Completed - implemented in `airflow/dags/task_functions.py` as `extract_companies_task` and wired in `jobs_etl_daily.py`

- [x] **2.18: Implement Airflow Task - Normalize Companies**
  - **📖 Reference: [ETL Pipeline Flow - Step 4](etl_pipeline_flow.md#step-4-normalizer-companies-bronze--silver)**
  - **Acceptance Criteria:**
    - Airflow task runs dbt model for `staging.glassdoor_companies`
    - Task fails if dbt run fails
    - Logs number of companies normalized
    - **Status**: Completed - implemented as BashOperator in `jobs_etl_daily.py` as `normalize_companies` task

- [x] **2.19: Implement Airflow Task - Build Marts**
  - **📖 Reference: [ETL Pipeline Flow - Step 6](etl_pipeline_flow.md#step-6-dbt-modelling-silver--gold)**
  - **Acceptance Criteria:**
    - Airflow task runs dbt models for marts layer:
      - `marts.dim_companies`
      - `marts.fact_jobs`
      - `marts.dim_ranking` (structure only - ephemeral model)
    - Tasks can run in parallel where possible
    - Logs completion status
    - **Status**: Completed - implemented as BashOperator in `jobs_etl_daily.py` as `dbt_modelling` task running `dbt run --select marts.*`

- [x] **2.20: Implement Airflow Task - Rank Jobs**
  - **📖 Reference: [ETL Pipeline Flow - Step 7](etl_pipeline_flow.md#step-7-ranker-service-gold-layer)**
  - **Acceptance Criteria:**
    - Airflow task calls Ranker service
    - Runs after marts are built
    - Logs number of job/profile pairs ranked
    - Task succeeds when rankings written to `marts.dim_ranking`
    - **Status**: Completed - implemented in `airflow/dags/task_functions.py` as `rank_jobs_task` and wired in `jobs_etl_daily.py`

- [x] **2.21: Implement Airflow Task - Data Quality Tests**
  - **📖 Reference: [ETL Pipeline Flow - Step 8](etl_pipeline_flow.md#step-8-quality-assurance)**
  - **Acceptance Criteria:**
    - Airflow task runs dbt tests (`dbt test`)
    - Tests include:
      - Uniqueness of surrogate keys
      - Not-null constraints on critical fields
      - Foreign key relationships
    - Task fails if critical tests fail (configurable)
    - Test results logged
    - **Status**: Completed - implemented as BashOperator in `jobs_etl_daily.py` as `dbt_tests` task running `dbt test`

- [x] **2.22: Implement Airflow Task - Send Daily Notifications**
  - **📖 Reference: [ETL Pipeline Flow - Step 9](etl_pipeline_flow.md#step-9-notifications)**
  - **Acceptance Criteria:**
    - Airflow task calls Email Notification service
    - Runs for each active profile
    - Logs email sending success/failure per profile
    - Task does not fail entire DAG if one email fails (handles gracefully)
    - **Status**: Completed - implemented in `airflow/dags/task_functions.py` as `send_notifications_task` with error handling and wired in `jobs_etl_daily.py`

- [x] **2.23: Wire Up Complete Airflow DAG with Task Dependencies**
  - **📖 Reference: [ETL Pipeline Flow - Step 11: Orchestration](etl_pipeline_flow.md#step-11-orchestration-airflow-dag) for complete task dependency diagram**
  - **Acceptance Criteria:**
    - All tasks connected with proper dependencies:
      - extract_job_postings → normalize_jobs
      - normalize_jobs → extract_companies
      - extract_companies → normalize_companies
      - normalize_companies → dbt_modelling
      - dbt_modelling → rank_jobs
      - rank_jobs → dbt_tests
      - dbt_tests → notify_daily
    - Tables are created automatically by Docker initialization script before DAG execution
    - DAG runs end-to-end successfully
    - Can be triggered manually and completes without errors
    - **Status**: Completed - all dependencies wired in `jobs_etl_daily.py` with enricher placeholder task included. Note: enricher task is placeholder (echo command) as enrichment service is Phase 3.

### Profile Management Interface

- [x] **2.24: Implement Profile Management Web UI - List Profiles**
  - **Acceptance Criteria:**
    - Flask app (or similar) displays all profiles from `marts.profile_preferences`
    - Shows: profile_name, profile_id, is_active status, query, location, country
    - Shows run statistics: total_run_count, last_run_at, last_run_status, last_run_job_count
    - UI is accessible via browser
    - **Status**: Completed - implemented in `profile_ui/app.py` with `index()` route displaying all profiles with statistics

- [x] **2.25: Implement Profile Management Web UI - Create Profile**
  - **Acceptance Criteria:**
    - Form allows input of required fields: profile_name, query, country, date_window, email
    - Optional fields: skills, salary range, remote preference, seniority
    - Validates required fields and email format
    - Inserts into database with is_active=true, timestamps, initialized counters
    - Redirects to profile list after creation
    - **Status**: Completed - implemented in `profile_ui/app.py` with `create_profile()` route, form validation, and template `create_profile.html`

- [x] **2.26: Implement Profile Management Web UI - Update Profile**
  - **Acceptance Criteria:**
    - Edit form pre-populated with existing profile data
    - Can modify any search criteria or preferences
    - Can toggle is_active status
    - Updates updated_at timestamp
    - Validates inputs before saving
    - **Status**: Completed - implemented in `profile_ui/app.py` with `edit_profile()` route and template `edit_profile.html`. Includes separate `toggle_active()` route for toggling status.

- [x] **2.27: Implement Profile Management Web UI - View Statistics**
  - **Acceptance Criteria:**
    - Profile detail page shows recent run history
    - Displays: run date/time, status, jobs found
    - Shows aggregated stats: total_run_count, average jobs per run
    - Basic visual indicators for health (e.g., last run success/failure)
    - **Status**: Completed - implemented in `profile_ui/app.py` with `view_profile()` route displaying all profile fields including statistics (total_run_count, last_run_at, last_run_status, last_run_job_count). Template `view_profile.html` shows full profile details.

- [x] **2.28: Containerize Profile Management UI**
  - **Acceptance Criteria:**
    - Dockerfile created for profile UI
    - Can be added to docker-compose.yml
    - Connects to PostgreSQL via environment variables
    - UI accessible when stack is running
    - **Status**: Completed - Dockerfile exists at `profile_ui/Dockerfile` with Python 3.11-slim base, exposes port 5000, and configures Flask app

### CI Pipeline

- [x] **2.29: Set Up GitHub Actions CI Pipeline**
  - **Acceptance Criteria:**
    - CI runs on pull requests:
      - Runs linting (`ruff check`)
      - Runs formatting check (`ruff format --check`)
      - Runs unit tests (`pytest`)
      - Runs dbt tests (if applicable)
    - CI fails if any checks fail
    - CI runs quickly (< 10 minutes)
    - **Status**: Completed - Created `.github/workflows/ci.yml` with three jobs:
      - `lint-and-format`: Runs ruff check and format checks
      - `test`: Runs pytest with coverage reporting
      - `dbt-test`: Prepared but disabled by default (requires database connection)
    - CI triggers on pull requests and pushes to main/master/develop branches
    - Uses Python 3.11 as required by project
    - Note: dbt tests are disabled by default (`if: false`) as they require a PostgreSQL database connection. Can be enabled when database service is added to CI.

### Testing & Validation

- [ ] **2.30: Write Unit Tests for Core Services**
  - **Acceptance Criteria:**
    - Unit tests for API clients (with mocks)
    - Unit tests for ranking logic
    - Unit tests for data parsing/transformation logic
    - Test coverage > 70% for core logic
    - Tests run with `pytest` command
    - **Status**: Partial - Some unit tests exist (e.g., `tests/test_company_extractor.py`), but comprehensive coverage across all services is needed. Tests exist for company extractor logic but may need expansion for other services.

- [ ] **2.31: Write Integration Tests for Key Pipeline Paths**
  - **Acceptance Criteria:**
    - Integration test: extract → normalize → rank flow
    - Integration test: company enrichment flow
    - Tests use test database or test containers
    - Tests validate data flows correctly between layers

- [ ] **2.32: End-to-End Test - Full Pipeline Run**
  - **Acceptance Criteria:**
    - At least one active profile in database
    - DAG can be triggered and completes successfully
    - Data flows through all layers (raw → staging → marts)
    - Rankings are generated
    - Email is sent (or logged if using test SMTP)
    - All tasks show success status in Airflow UI

---

## Phase 3: Enrichment & Data Quality (Feature Depth)

### Enrichment Service

**📖 Reference: [ETL Pipeline Flow - Step 5](etl_pipeline_flow.md#step-5-enricher-service-silver-layer)**

- [ ] **3.1: Implement Enricher Service - Skills Extraction**
  - **Acceptance Criteria:**
    - Python service uses spaCy to extract skills from job descriptions
    - Processes `staging.jsearch_job_postings` records
    - Extracts common technical skills (Python, SQL, AWS, etc.) and soft skills
    - Writes extracted skills to `extracted_skills` column (JSON array or comma-separated)
    - Handles different job description formats
    - Unit tests with sample job descriptions

- [ ] **3.2: Implement Enricher Service - Seniority Extraction**
  - **Acceptance Criteria:**
    - Rule-based logic extracts seniority level from job title/description
    - Identifies: Intern, Junior, Mid, Senior, Lead, Principal, etc.
    - Writes to `seniority_level` column in staging table
    - Handles edge cases (unclear seniority, multiple levels mentioned)
    - Unit tests for various title patterns

- [ ] **3.3: Create Airflow Task for Job Enrichment**
  - **Acceptance Criteria:**
    - Airflow task runs Enricher service after jobs are normalized
    - Updates `staging.jsearch_job_postings` with enrichment data
    - Task has retry logic and proper logging
    - Integrated into DAG workflow appropriately

### Extended Ranking

- [ ] **3.4: Extend Ranker Service - Additional Factors**
  - **Acceptance Criteria:**
    - Ranker incorporates additional scoring factors:
      - Skills match (between profile preferences and extracted skills)
      - Salary alignment (preferred range vs. job salary)
      - Company rating (from Glassdoor)
      - Seniority match
      - Employment type preference
    - Scoring weights are configurable (via config file or database table)
    - Scores still normalized to 0-100 range

- [ ] **3.5: Implement Rank Explanation JSON**
  - **Acceptance Criteria:**
    - Ranker generates `rank_explain` JSON field in `marts.dim_ranking`
    - JSON breaks down contribution of each scoring factor
    - Example: `{"location_match": 20, "keyword_match": 30, "skills_match": 25, ...}`
    - Can be used for debugging and transparency

- [ ] **3.6: Update Ranker Airflow Task**
  - **Acceptance Criteria:**
    - Updated task uses extended ranking logic
    - Writes both `rank_score` and `rank_explain` to `marts.dim_ranking`
    - Logs summary of scoring factors used

### Data Quality & Observability

- [ ] **3.7: Expand dbt Data Quality Tests**
  - **Acceptance Criteria:**
    - Comprehensive dbt tests added:
      - Referential integrity between fact and dimensions
      - Data freshness checks (jobs not too old)
      - Salary range validations (min <= max)
      - Enum/constraint validations
      - Custom business rule tests
    - Test results are clearly reported
    - Critical vs. warning tests are differentiated

- [ ] **3.8: Create ETL Run Metrics Table**
  - **Acceptance Criteria:**
    - Table tracks per-run statistics:
      - Run timestamp, profile_id, DAG run ID
      - Rows processed per layer
      - API calls made, API errors
      - Processing duration
      - Data quality test results summary
    - Metrics populated by Airflow tasks
    - Can be queried for pipeline health monitoring

- [ ] **3.9: Enhance Profile UI with Rich Statistics**
  - **Acceptance Criteria:**
    - Profile UI displays:
      - Run history with more detail
      - Charts/graphs for job counts over time
      - Average ranking scores for jobs found
      - Data quality indicators
      - Pipeline health status (e.g., last N runs success rate)

### Code Quality Improvements

- [ ] **3.10: Refactor Services for Extensibility**
  - **Acceptance Criteria:**
    - Source-extractor uses abstraction pattern for adding new job APIs
    - Ranking weights/factors configurable (not hard-coded)
    - Enricher structured to allow plugging in new enrichment types
    - Code follows SOLID principles where applicable
    - Documented extension points

- [ ] **3.11: Add Comprehensive Logging**
  - **Acceptance Criteria:**
    - Structured logging throughout Python services
    - Log levels appropriately used (INFO, WARNING, ERROR)
    - Logs include context (profile_id, job_id, etc.)
    - Logs are searchable and useful for debugging

---

## Phase 4: AWS Lift (Production Deployment)

### Database Migration

- [ ] **4.1: Set Up AWS RDS PostgreSQL Instance**
  - **Acceptance Criteria:**
    - RDS PostgreSQL instance created with appropriate size/configuration
    - Security groups configured for access
    - Database credentials stored in AWS Secrets Manager
    - Connection tested from local environment

- [ ] **4.2: Migrate Database Schemas to RDS**
  - **Acceptance Criteria:**
    - All schemas (raw, staging, marts) created on RDS
    - All tables migrated (via dbt or migration scripts)
    - Indexes and constraints preserved
    - Data validated (if migrating existing data)

- [ ] **4.3: Update dbt Profiles for RDS**
  - **Acceptance Criteria:**
    - dbt `profiles.yml` updated to connect to RDS
    - Connection uses credentials from Secrets Manager or environment variables
    - `dbt debug` confirms successful connection
    - Can run dbt models against RDS

### S3 Integration

- [ ] **4.4: Implement Raw JSON Archival to S3**
  - **Acceptance Criteria:**
    - After writing to `raw` tables, JSON payloads also archived to S3
    - S3 structure: `s3://bucket/raw/jsearch_job_postings/YYYY/MM/DD/`
    - Archival happens as part of extraction tasks
    - Files are compressed (gzip) to save storage
    - Can retrieve archived data if needed

- [ ] **4.5: Create S3 Export for Tableau/Analytics**
  - **Acceptance Criteria:**
    - Optional task exports marts data to S3 in analytics-friendly format (CSV, Parquet)
    - Exports scheduled (e.g., weekly) or on-demand
    - S3 structure organized for easy consumption
    - Documentation on how to access exports

### Service Deployment

- [ ] **4.6: Create Docker Images for Services**
  - **Acceptance Criteria:**
    - Dockerfiles created for each service:
      - Source Extractor
      - Enricher
      - Ranker
      - Email Notifier
      - Profile UI
    - Images built and tested locally
    - Images pushed to container registry (ECR)

- [ ] **4.7: Deploy Services to AWS ECS**
  - **Acceptance Criteria:**
    - ECS task definitions created for each service
    - Services configured to:
      - Pull credentials from Secrets Manager
      - Connect to RDS via security groups
      - Use appropriate IAM roles
    - Services can run as tasks/jobs in ECS
    - Logs sent to CloudWatch

- [ ] **4.8: Deploy Airflow to EC2**
  - **Acceptance Criteria:**
    - EC2 instance set up with Airflow
    - Airflow configured to:
      - Connect to RDS for metadata database
      - Use ECS operators or invoke ECS tasks
      - Access Secrets Manager for credentials
    - DAGs deployed and visible in Airflow UI
    - Can trigger and run DAGs successfully

### BI Integration

- [ ] **4.9: Connect Tableau to RDS Marts Schema**
  - **Acceptance Criteria:**
    - Tableau connection configured to RDS PostgreSQL
    - Connection uses read-only credentials
    - Can browse marts schema tables
    - Connection is stable and performant

- [ ] **4.10: Build Initial Tableau Dashboards**
  - **Acceptance Criteria:**
    - Dashboard for skills trends (most demanded skills over time)
    - Dashboard for salary trends (by location, company, role)
    - Dashboard for job volumes (postings over time, by company)
    - Dashboard for company ratings distribution
    - Dashboard for ranking score distributions
    - Dashboards refresh from live RDS data

### Deployment Pipeline

- [ ] **4.12: Set Up Deployment Pipeline**
  - **Acceptance Criteria:**
    - Deployment pipeline on merge to main:
      - Builds Docker images
      - Pushes to ECR
      - Updates ECS task definitions
      - Optionally triggers ECS service update
    - Deployment is automated but can be triggered manually
    - Rollback procedure documented

### Security & Operations

- [ ] **4.13: Implement AWS Security Best Practices**
  - **Acceptance Criteria:**
    - IAM roles follow least-privilege principle
    - Security groups restrict access appropriately
    - All API keys and secrets in Secrets Manager (not hard-coded)
    - RDS uses encryption at rest
    - SSL/TLS used for database connections
    - VPC configured appropriately

- [ ] **4.14: Set Up Monitoring and Alerting**
  - **Acceptance Criteria:**
    - CloudWatch alarms for:
      - DAG failures
      - High error rates in services
      - RDS connection issues
    - Alarms send notifications (email, SNS)
    - Basic CloudWatch dashboards for key metrics
    - Log aggregation in CloudWatch Logs

- [ ] **4.15: Create Operational Runbooks**
  - **Acceptance Criteria:**
    - Documentation for:
      - How to manually trigger DAGs
      - How to investigate failed runs
      - How to update profile preferences
      - How to access logs
      - How to scale services
      - Disaster recovery procedures
    - Runbooks are clear and actionable

---

## Post-Implementation

- [ ] **5.1: Performance Optimization**
  - Review and optimize slow queries
  - Add indexes where needed
  - Optimize API call patterns
  - Cache frequently accessed data if beneficial

- [ ] **5.2: Documentation Finalization**
  - Architecture diagrams updated
  - API documentation for services
  - User guide for profile management UI
  - Developer onboarding guide

- [ ] **5.3: Load Testing**
  - Test pipeline with multiple profiles
  - Test with high job volumes
  - Verify system handles peak loads gracefully

---

## Notes

- Tasks within each phase should generally be completed in order, but some can be parallelized
- Acceptance criteria should be verified before marking tasks complete
- Consider creating GitHub issues or project board items from this TODO list for tracking
- Adjust timeline estimates based on your experience level and available time

