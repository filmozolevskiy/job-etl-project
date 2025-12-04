# Job Postings Data Platform - Implementation TODO List

This document provides a phased implementation checklist for the Job Postings Data Platform project. Each task includes clear acceptance criteria and is ordered from easy to hard within each phase.

**Quick Progress Checklist**

- [ ] [Phase 1: Project Scaffold & Local Runtime](#phase-1-project-scaffold--local-runtime)
  - [ ] [Infrastructure & Setup](#infrastructure--setup)
- [ ] [Phase 2: First End-to-End Local MVP Path](#phase-2-first-end-to-end-local-mvp-path)
  - [ ] [CI Pipeline](#ci-pipeline)
  - [ ] [Data Model Foundation](#data-model-foundation)
  - [ ] [Core Services - Source Extractor](#core-services---source-extractor)
  - [ ] [Core Services - Ranking](#core-services---ranking)
  - [ ] [Core Services - Notifications](#core-services---notifications)
  - [ ] [Airflow DAG Implementation](#airflow-dag-implementation)
  - [ ] [Profile Management Interface](#profile-management-interface)
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

- [ ] **1.1: Initialize Git Repository**
  - **Acceptance Criteria:**
    - Git repository initialized with appropriate `.gitignore` for Python, Docker, and database files
    - Initial commit created with project structure
    - README.md created with basic project description

- [ ] **1.2: Create Project Folder Structure**
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

- [ ] **1.3: Create Database Schema Initialization Script**
  - **Acceptance Criteria:**
    - SQL script at `docker/init/01_create_schemas.sql` creates schemas: `raw`, `staging`, `marts`
    - Script uses `CREATE SCHEMA IF NOT EXISTS` for idempotency
    - Script includes grant permissions to application user
    - Script can be run manually or automatically via Docker initialization
    - Schemas verified to exist after running script
    - **Note**: This script only creates schemas (infrastructure). Tables are created and managed by dbt models, not by this initialization script.

- [ ] **1.4: Create Docker Compose Configuration**
  - **Acceptance Criteria:**
    - `docker-compose.yml` defines services:
      - PostgreSQL with initialization script mounted at `/docker-entrypoint-initdb.d`
      - Schemas `raw`, `staging`, `marts` are automatically created on first container start
      - Airflow webserver and scheduler
      - Optional: profile UI container
    - Environment variables configured via `.env` file
    - Services can start with `docker-compose up`
    - Database connection strings documented

- [ ] **1.5: Initialize dbt Project**
  - **Acceptance Criteria:**
    - dbt project initialized with `dbt init`
    - `profiles.yml` configured to connect to local PostgreSQL
    - Project connects successfully with `dbt debug`
    - Project structure includes `models/` subdirectories for raw, staging, marts
    - **Note**: Schemas must exist (created via initialization script) before dbt can create tables within them

- [ ] **1.6: Configure Python Development Tools**
  - **Acceptance Criteria:**
    - `requirements.txt` or `pyproject.toml` includes:
      - `pytest` for testing
      - `ruff` for linting and formatting
      - Core dependencies for services
    - Linting rules configured (e.g., `ruff.toml` or `pyproject.toml` settings)
    - Pre-commit hooks set up
    - Running `ruff check` and `ruff format` works without errors

- [ ] **1.7: Create Environment Configuration Template**
  - **Acceptance Criteria:**
    - `.env.example` file created with all required environment variables:
      - Database connection strings
      - API keys (JSearch, Glassdoor)
      - Email SMTP settings
      - Airflow configuration
    - Variables documented with descriptions
    - `.env` added to `.gitignore`

- [ ] **1.8: Create Basic Airflow DAG Structure**
  - **Acceptance Criteria:**
    - `jobs_etl_daily` DAG file created in `airflow/dags/`
    - DAG scheduled for 07:00 America/Toronto timezone
    - DAG visible in Airflow UI (can be paused/unpaused, no tasks yet)
    - Basic imports and DAG configuration in place

---

## Phase 2: First End-to-End Local MVP Path

### Data Model Foundation

- [ ] **2.1: Create `marts.profile_preferences` Table**
  - **Acceptance Criteria:**
    - Table created with all required columns per PRD Section 4.3
    - Primary key on `profile_id`
    - Indexes on `is_active` and timestamps
    - At least one test profile can be inserted manually
    - dbt model created to manage this table (seed or model)
    - Table will be created/verified by the DAG initialization task (see task 2.14.5)

- [ ] **2.2: Create Raw Layer Tables via dbt**
  - **Acceptance Criteria:**
    - Schemas `raw`, `staging`, `marts` already exist (created via initialization script)
    - dbt models create `raw.jsearch_job_postings` table with:
      - Surrogate key (`raw_job_posting_id`)
      - JSONB or JSON column for payload
      - Technical columns: `dwh_load_date`, `dwh_load_timestamp`, `dwh_source_system`, `profile_id`
    - dbt models create `raw.glassdoor_companies` table with similar structure
    - Tables can be created via `dbt run --select raw.*`
    - **IMPORTANT**: These tables must exist before extractor service can write to them. They will be created/verified by the DAG initialization task (see task 2.14.5)

- [ ] **2.3: Create Staging Layer Models - Job Postings**
  - **Acceptance Criteria:**
    - dbt model `staging.jsearch_job_postings` transforms raw JSON
    - Extracts key fields: `job_id`, title, description, employer, location, salary, employment type, etc.
    - Deduplicates on `job_id`
    - Adds technical columns with `dwh_` prefix
    - Handles nulls and type conversions appropriately
    - Model runs successfully via `dbt run`

- [ ] **2.4: Create Staging Layer Models - Companies**
  - **Acceptance Criteria:**
    - dbt model `staging.glassdoor_companies` transforms raw JSON
    - Extracts company details: `company_id`, name, website, industry, ratings, location
    - Deduplicates companies appropriately
    - Adds technical columns
    - Model runs successfully

- [ ] **2.5: Create Staging Layer - Company Enrichment Queue Table**
  - **Acceptance Criteria:**
    - Table `staging.company_enrichment_queue` created with columns:
      - `company_lookup_key`
      - `enrichment_status` (enum or constraint)
      - Timestamp fields
    - Can track pending/success/not_found/error statuses
    - Table will be created/verified by the DAG initialization task (see task 2.14.5)

- [ ] **2.6: Create Marts Layer - Dimension Companies**
  - **Acceptance Criteria:**
    - dbt model `marts.dim_companies` built from staging
    - Surrogate key `company_key` generated
    - Natural keys preserved (`company_id`, normalized name)
    - Includes all attributes from PRD Section 4.3
    - Model runs successfully

- [ ] **2.7: Create Marts Layer - Fact Jobs**
  - **Acceptance Criteria:**
    - dbt model `marts.fact_jobs` built from `staging.jsearch_job_postings`
    - Surrogate key `job_posting_key` generated
    - Foreign keys: `company_key` (joined to `dim_companies`), `profile_id`
    - Includes salary metrics, posting dates, binary flags, derived attributes
    - Model runs successfully and joins work correctly

- [ ] **2.8: Create Marts Layer - Dimension Ranking Structure**
  - **Acceptance Criteria:**
    - Table `marts.dim_ranking` created with:
      - Composite key: `job_posting_key`, `profile_id`
      - `rank_score` column (numeric, 0-100)
      - Timestamp columns
    - Ready to receive ranking data from Ranker service

### Core Services - Source Extractor

- [ ] **2.9: Implement JSearch API Client**
  - **Acceptance Criteria:**
    - Python module with abstracted API client structure
    - Handles authentication (API key from env)
    - Implements rate limiting and retries with exponential backoff
    - Can call JSearch API with query parameters (query, location, country, date_window, etc.)
    - Returns parsed JSON response
    - Unit tests for API client logic (mocked responses)

- [ ] **2.10: Implement Source Extractor Service - Jobs**
  - **Acceptance Criteria:**
    - Python service reads active profiles from `marts.profile_preferences`
    - For each profile, calls JSearch API with profile parameters
    - Writes raw JSON responses to `raw.jsearch_job_postings`
    - Adds technical metadata (load date, timestamp, source system, profile_id)
    - Logs number of jobs extracted per profile
    - Can be run as standalone script or called from Airflow

- [ ] **2.11: Implement Glassdoor API Client**
  - **Acceptance Criteria:**
    - Python module for Glassdoor company search API
    - Handles authentication and rate limiting
    - Takes company name/domain as input
    - Returns company JSON response
    - Unit tests with mocked responses

- [ ] **2.12: Implement Company Extraction Logic**
  - **Acceptance Criteria:**
    - Python service scans `staging.jsearch_job_postings` for employer names/domains
    - Identifies companies not yet enriched (checks `staging.company_enrichment_queue`)
    - Calls Glassdoor API for missing companies
    - Writes raw JSON to `raw.glassdoor_companies` with `company_lookup_key`
    - Updates enrichment queue status
    - Handles "not found" and error cases gracefully

### Core Services - Ranking

- [ ] **2.13: Implement MVP Ranker Service**
  - **Acceptance Criteria:**
    - Python service reads `marts.fact_jobs` and active `marts.profile_preferences`
    - Scores each job/profile pair based on:
      - Location match (simple string/keyword matching)
      - Keyword match between profile query and job title/description
      - Recency of posting (newer = higher score)
    - Normalizes scores to 0-100 range
    - Writes scores to `marts.dim_ranking`
    - Unit tests for scoring logic

### Core Services - Notifications

- [ ] **2.14: Implement Email Notification Service**
  - **Acceptance Criteria:**
    - Python service reads top N jobs from `marts.dim_ranking` (joined to `marts.fact_jobs`)
    - Composes simple HTML email with job list for each active profile
    - Includes job title, company, location, salary (if available), apply link
    - Sends via SMTP (configurable via environment variables)
    - Logs email sending results per profile
    - Handles email failures gracefully

### Airflow DAG Implementation

- [ ] **2.14.5: Implement Airflow Task - Initialize Database Tables**
  - **Acceptance Criteria:**
    - Airflow task `initialize_tables` runs at the start of DAG execution
    - Task runs `dbt run --select raw.* staging.company_enrichment_queue marts.profile_preferences`
    - Uses dbt operator or BashOperator with proper dbt configuration
    - Task is idempotent (safe to run multiple times - dbt handles CREATE IF NOT EXISTS)
    - Verifies all required tables exist: `raw.jsearch_job_postings`, `raw.glassdoor_companies`, `staging.company_enrichment_queue`, `marts.profile_preferences`
    - Task logs which tables were created/verified
    - Task fails if critical tables cannot be created
    - **Purpose**: Ensures all tables exist before extractor service attempts to write data

- [ ] **2.15: Implement Airflow Task - Extract Job Postings**
  - **Acceptance Criteria:**
    - Airflow task calls Source Extractor service
    - Task has retry policy (e.g., 3 retries with exponential backoff)
    - Logs number of profiles processed and jobs extracted
    - Task succeeds when jobs are written to raw layer

- [ ] **2.16: Implement Airflow Task - Normalize Jobs**
  - **Acceptance Criteria:**
    - Airflow task runs dbt model for `staging.jsearch_job_postings`
    - Uses dbt operator or BashOperator with `dbt run --select staging.jsearch_job_postings`
    - Task fails if dbt run fails
    - Logs number of rows processed

- [ ] **2.17: Implement Airflow Task - Extract Companies**
  - **Acceptance Criteria:**
    - Airflow task calls Company Extraction service
    - Handles rate limiting for Glassdoor API calls
    - Updates enrichment queue appropriately
    - Logs companies found/not found/errors

- [ ] **2.18: Implement Airflow Task - Normalize Companies**
  - **Acceptance Criteria:**
    - Airflow task runs dbt model for `staging.glassdoor_companies`
    - Task fails if dbt run fails
    - Logs number of companies normalized

- [ ] **2.19: Implement Airflow Task - Build Marts**
  - **Acceptance Criteria:**
    - Airflow task runs dbt models for marts layer:
      - `marts.dim_companies`
      - `marts.fact_jobs`
      - `marts.dim_ranking` (structure only)
    - Tasks can run in parallel where possible
    - Logs completion status

- [ ] **2.20: Implement Airflow Task - Rank Jobs**
  - **Acceptance Criteria:**
    - Airflow task calls Ranker service
    - Runs after marts are built
    - Logs number of job/profile pairs ranked
    - Task succeeds when rankings written to `marts.dim_ranking`

- [ ] **2.21: Implement Airflow Task - Data Quality Tests**
  - **Acceptance Criteria:**
    - Airflow task runs dbt tests (`dbt test`)
    - Tests include:
      - Uniqueness of surrogate keys
      - Not-null constraints on critical fields
      - Foreign key relationships
    - Task fails if critical tests fail (configurable)
    - Test results logged

- [ ] **2.22: Implement Airflow Task - Send Daily Notifications**
  - **Acceptance Criteria:**
    - Airflow task calls Email Notification service
    - Runs for each active profile
    - Logs email sending success/failure per profile
    - Task does not fail entire DAG if one email fails (handles gracefully)

- [ ] **2.23: Wire Up Complete Airflow DAG with Task Dependencies**
  - **Acceptance Criteria:**
    - All tasks connected with proper dependencies:
      - initialize_tables → extract_job_postings (ensures tables exist before extraction)
      - extract_job_postings → normalize_jobs
      - normalize_jobs → extract_companies
      - extract_companies → normalize_companies
      - normalize_companies → dbt_modelling
      - dbt_modelling → rank_jobs
      - rank_jobs → dbt_tests
      - dbt_tests → notify_daily
    - Initialization task runs first, ensuring all required tables exist
    - DAG runs end-to-end successfully
    - Can be triggered manually and completes without errors

### Profile Management Interface

- [ ] **2.24: Implement Profile Management Web UI - List Profiles**
  - **Acceptance Criteria:**
    - Flask app (or similar) displays all profiles from `marts.profile_preferences`
    - Shows: profile_name, profile_id, is_active status, query, location, country
    - Shows run statistics: total_run_count, last_run_at, last_run_status, last_run_job_count
    - UI is accessible via browser

- [ ] **2.25: Implement Profile Management Web UI - Create Profile**
  - **Acceptance Criteria:**
    - Form allows input of required fields: profile_name, query, country, date_window, email
    - Optional fields: skills, salary range, remote preference, seniority
    - Validates required fields and email format
    - Inserts into database with is_active=true, timestamps, initialized counters
    - Redirects to profile list after creation

- [ ] **2.26: Implement Profile Management Web UI - Update Profile**
  - **Acceptance Criteria:**
    - Edit form pre-populated with existing profile data
    - Can modify any search criteria or preferences
    - Can toggle is_active status
    - Updates updated_at timestamp
    - Validates inputs before saving

- [ ] **2.27: Implement Profile Management Web UI - View Statistics**
  - **Acceptance Criteria:**
    - Profile detail page shows recent run history
    - Displays: run date/time, status, jobs found
    - Shows aggregated stats: total_run_count, average jobs per run
    - Basic visual indicators for health (e.g., last run success/failure)

- [ ] **2.28: Containerize Profile Management UI**
  - **Acceptance Criteria:**
    - Dockerfile created for profile UI
    - Can be added to docker-compose.yml
    - Connects to PostgreSQL via environment variables
    - UI accessible when stack is running

### CI Pipeline

- [ ] **2.29: Set Up GitHub Actions CI Pipeline**
  - **Acceptance Criteria:**
    - CI runs on pull requests:
      - Runs linting (`ruff check`)
      - Runs formatting check (`ruff format --check`)
      - Runs unit tests (`pytest`)
      - Runs dbt tests (if applicable)
    - CI fails if any checks fail
    - CI runs quickly (< 10 minutes)

### Testing & Validation

- [ ] **2.30: Write Unit Tests for Core Services**
  - **Acceptance Criteria:**
    - Unit tests for API clients (with mocks)
    - Unit tests for ranking logic
    - Unit tests for data parsing/transformation logic
    - Test coverage > 70% for core logic
    - Tests run with `pytest` command

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

