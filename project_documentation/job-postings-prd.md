## Job Postings Data Platform – Product Requirement Document

### Table of Contents

- [1. Executive Summary](#1-executive-summary)
  - [1.1 Purpose](#11-purpose)
  - [1.2 Out of Scope](#12-out-of-scope)
- [2. Technologies](#2-technologies)
- [3. System Architecture](#3-system-architecture)
  - [3.1 Medallion Layers and Schemas](#31-medallion-layers-and-schemas)
  - [3.2 Core Components](#32-core-components)
  - [3.3 ETL Pipeline Flow](#33-etl-pipeline-flow)
- [4. Data Model](#4-data-model)
  - [4.1 Raw Layer (`raw` schema)](#41-raw-layer-raw-schema)
  - [4.2 Staging Layer (`staging` schema)](#42-staging-layer-staging-schema)
  - [4.3 Mart Layer (`marts` schema)](#43-mart-layer-marts-schema)
- [5. Job Profile Management Interface](#5-job-profile-management-interface)
- [6. Airflow DAG – `jobs_etl_daily`](#6-airflow-dag--jobs_etl_daily)
- [7. Phased Implementation](#7-phased-implementation)
- [8. Non-Functional Requirements and Best Practices](#8-non-functional-requirements-and-best-practices)

### 1. Executive Summary

#### 1.1 Purpose  
This document describes a **job hunting data platform** that:

- Extracts job postings from the **JSearch API**.
- Optionally enriches employers with **Glassdoor company data**.
- Normalizes, enriches, and ranks jobs in a **Medallion data warehouse** (schemas: `raw`, `staging`, `marts`) hosted on PostgreSQL.
- Sends **daily email summaries** of top ranked jobs per job profile.
- Exposes data to **Tableau** for analysis of trends (demanded skills, salaries, locations, companies, etc.).
- Provides a **simple interface to manage job profiles** and view usage statistics.

The system is designed as a **pet project for a junior data engineer**, emphasizing best practices, clear structure, and extensibility.

#### 1.2 Out of Scope  
- Full end‑user job search web application.
- Real‑time streaming ingestion.
- Advanced ML‑based ranking models.
- Multi‑tenant user authentication and authorization.

### 2. Technologies

- **Version control**: Git.
- **Language**: Python.
- **Containerization**: Docker / Docker Compose (local), ECS (AWS).
- **Database**: PostgreSQL (Medallion architecture: `raw`, `staging`, `marts`).
- **Transformations**: dbt.
- **Orchestration**: Apache Airflow.
- **Cloud**: AWS (RDS, S3, ECS, EC2, Lambda where useful).
- **Email**: SMTP server (e.g. transactional email service).
- **BI**: Tableau (connected to `marts` schema).
- **Quality**: pytest (unit and integration tests); linting and formatting with `ruff`.

---

### 3. System Architecture

#### 3.1 Medallion Layers and Schemas

The platform uses a **Medallion architecture** with three schemas, aligned with `Project Documentation/naming_conventions.md`:

- **Raw (Bronze)** – Schema: `raw`
  - Stores **raw JSON** API responses with minimal transformation.
  - Table naming: `<sourcesystem>_<entity>` (e.g. `jsearch_job_postings`, `glassdoor_companies`).

- **Staging (Silver)** – Schema: `staging`
  - Holds **normalized and cleaned** relational data derived from raw.
  - Table naming: `<sourcesystem>_<entity>` (same as raw).
  - Includes technical columns with `dwh_` prefix (e.g. `dwh_load_date`).

- **Marts (Gold)** – Schema: `marts`
  - Contains **business‑ready fact and dimension tables** plus configuration tables.
  - Table naming: `<category>_<entity>` (e.g. `fact_jobs`, `dim_companies`, `dim_ranking`).
  - Uses surrogate keys with `_key` suffix (e.g. `job_posting_key`, `company_key`).

#### 3.2 Core Components

- **Source‑extractor (Python service)**  
  Abstracted component responsible for calling external APIs (JSearch, Glassdoor, future sources), handling authentication, rate limiting, retries, and logging. Writes raw JSON into the `raw` schema.

- **Enricher (Python service)**  
  Reads normalized jobs from staging and performs NLP‑based enrichment:
  - Skills extraction using spaCy.
  - Seniority extraction using rule‑based logic.
  Writes enrichment results back into `staging.jsearch_job_postings`.

- **Ranker (Python service)**  
  Reads jobs, companies, and profile preferences from `marts` and computes relevance scores:
  - MVP: simple scoring based on location, keyword match, recency.
  - Phase 3: extended scoring including skills, salary, company rating, seniority, and employment type.
  Writes results into `marts.dim_ranking`.

- **dbt Project**  
  Implements all SQL transformations:
  - Raw → Staging normalization.
  - Staging → Marts modelling (fact and dimension tables).
  - Data quality tests (e.g. unique keys, non‑nulls, relationships).

- **Airflow DAG – `jobs_etl_daily`**  
  Main orchestration pipeline, scheduled daily at **07:00 America/Toronto**, coordinating all extract, transform, rank, test, and notify tasks.

- **Profile Management Interface**  
  Simple UI or CLI tool that lets the user:
  - Create and maintain job profiles in `marts.profile_preferences`.
  - See basic statistics per profile (active/inactive, run counts, last run time/status).

#### 3.3 ETL Pipeline Flow

For a comprehensive, step-by-step description of the entire ETL pipeline flow, see the detailed documentation:

- **[ETL Pipeline Flow Documentation](etl_pipeline_flow.md)** – Complete step-by-step flow with detailed descriptions of each pipeline step, inputs, outputs, dependencies, and technical details.
- **[ETL Pipeline Flow Diagram](etl_pipeline_flow_diagram.mmd)** – Visual Mermaid diagram showing the 11-step sequential flow and data transformations through Bronze → Silver → Gold layers.
- **[ETL Pipeline Data Flow (DBML)](etl_pipeline_data_flow.dbml)** – Database schema diagram showing all tables, relationships, and data flow between layers. Can be viewed at [dbdiagram.io](https://dbdiagram.io/).

The pipeline follows an 11-step process:
1. Extract Job Postings (Bronze Layer)
2. Normalizer Jobs (Bronze → Silver)
3. Extract Company Information (Bronze Layer)
4. Normalizer Companies (Bronze → Silver)
5. Enricher Service (Silver Layer)
6. DBT Modelling (Silver → Gold)
7. Ranker Service (Gold Layer)
8. Quality Assurance
9. Notifications
10. Data Consumption
11. Orchestration (Airflow DAG)

---

### 4. Data Model

#### 4.1 Raw Layer (`raw` schema)

- **`raw.jsearch_job_postings`**
  - **Source**: JSearch API.
  - **Grain**: One row per job posting.
  - **Content**:
    - Surrogate row identifier (e.g. `raw_job_posting_id`) used to trace lineage into `staging.jsearch_job_postings`.
    - Original JSON payload from JSearch. The only transformation is extraction of individual job postings.
    - Technical columns: `dwh_load_date`, `dwh_load_timestamp`, `dwh_source_system`, `profile_id`.

- **`raw.glassdoor_companies`**
  - **Source**: Glassdoor company search API.
  - **Grain**: One row per Glassdoor company.
  - **Content**:
    - Surrogate row identifier (e.g. `raw_company_id`) used to trace lineage into `staging.glassdoor_companies`.
    - Original JSON payload from Glassdoor. The only transformation is extraction of individual companies.
    - Lookup keys used in the request (company name/domain).
    - Technical columns: `dwh_load_date`, `dwh_load_timestamp`, `dwh_source_system`, `company_lookup_key`.

#### 4.2 Staging Layer (`staging` schema)

- **`staging.jsearch_job_postings`**
  - **Source**: `raw.jsearch_job_postings` (via dbt).
  - **Purpose**: Provide a clean, de‑duplicated view of job postings.
  - **Key columns**:
    - JSearch `job_id`.
    - Job title, description, employer name.
    - Location fields (city, state, country, latitude/longitude where available).
    - Employment type(s), date posted, work from home flag.
    - Salary fields (min, max, period) where available.
    - Apply links and publisher information.
    - Technical columns: `dwh_load_date`, `dwh_source_system`, etc.
    - Phase 3: `extracted_skills`, `seniority_level` from Enricher.

- **`staging.glassdoor_companies`**
  - **Source**: `raw.glassdoor_companies` (via dbt).
  - **Purpose**: Provide a standardized view of company information.
  - **Key columns**:
    - Glassdoor `company_id`.
    - Company name, website, industry, company size, size category.
    - Ratings (overall, compensation & benefits, culture & values, etc.).
    - Headquarters location (split into city, region, country).
    - Technical columns: `dwh_load_date`, `dwh_source_system`.

- **`staging.company_enrichment_queue`**
  - Tracks which companies derived from jobs still need Glassdoor enrichment.
  - Columns:
    - `company_lookup_key` (normalized name/domain).
    - `enrichment_status` (`pending`, `success`, `not_found`, `error`).
    - Last attempt timestamp.

#### 4.3 Mart Layer (`marts` schema)

- **`marts.fact_jobs`**
  - **Grain**: One row per job posting.
  - **Keys**:
    - `job_posting_key` (surrogate key).
    - Foreign keys: `company_key`, `profile_id` (or `profile_key`).
  - **Measures & attributes**:
    - Salary metrics (min, max, normalized).
    - Posting date, age of posting.
    - Binary flags (remote, full‑time, etc.).
    - Derived attributes (e.g. location bucket, salary band).

- **`marts.dim_companies`**
  - **Grain**: One row per distinct company.
  - **Keys**:
    - `company_key` (surrogate key).
    - Natural keys: `company_id` from Glassdoor, normalized company name.
  - **Attributes**:
    - Company name, industry, size, headquarters city/country.
    - Glassdoor ratings and counts.
    - Links to Glassdoor pages (overview, reviews, jobs, FAQ).

- **`marts.dim_ranking`**
  - **Grain**: One row per (job, profile) pair.
  - **Keys**:
    - Composite natural key: `job_posting_key`, `profile_id`.
  - **Attributes**:
    - `rank_score` (0–100).
    - Phase 3: `rank_explain` JSON (breakdown of each factor’s contribution).
    - Timestamps and technical columns.

- **`marts.profile_preferences`**
  - **Purpose**: Store job profiles that drive extraction and ranking.
  - **Populated by**: Profile Management UI exclusively.
  - **Fields**:
    - Identifiers: `profile_id`, `profile_name`.
    - Search criteria (used by Source‑extractor):
      - `query` (job title/keywords).
      - `location`, `country`, `language`.
      - `date_window` (e.g. today, week).
      - `employment_types`.
      - `work_from_home` / `remote` flag.
      - Minimum salary or salary range.
    - User preferences (used by Ranker and notifications):
      - Target email address.
      - Preferred skills (tags/keywords).
      - Preferred seniority levels.
      - Remote vs office preference.
    - Metadata and statistics:
      - `is_active` flag.
      - Timestamps: `created_at`, `updated_at`.
      - Run statistics: `last_run_at`, `last_run_status`, `last_run_job_count`, `total_run_count`.

---

### 5. Job Profile Management Interface

#### 5.1 Goals

- Make it easy to manage job profiles **without editing the database directly**.
- Provide basic visibility into how each profile is being used by the pipeline.
- Serve as a simple but realistic example of a configuration UI for a data platform.

#### 5.2 Functional Requirements

- **List profiles**
  - Display all profiles from `marts.profile_preferences`.
  - Show for each:
    - `profile_name`, `profile_id`.
    - `is_active` (active / inactive).
    - `query` and key search filters (location, country).
    - Run statistics: `total_run_count`, `last_run_at`, `last_run_status`, `last_run_job_count`.

- **Create a profile**
  - Input fields at minimum:
    - `profile_name`, `query`, `country`, `date_window`.
    - Target email address.
  - Optional fields:
    - Skills preferences, salary range, remote preference, seniority preferences.
  - Automatically sets:
    - `is_active = true`.
    - `created_at` and `updated_at`.
    - Run counters initialized to zero.

- **Update a profile**
  - Edit any search criteria or preferences.
  - Activate/deactivate profile via `is_active` toggle.
  - Update `updated_at`.

- **View profile statistics**
  - For a selected profile, show:
    - A simple history of recent runs (date/time, status, jobs found).
    - Aggregated counts: `total_run_count`, average jobs per run (if available).

#### 5.3 Technical Considerations

- Implemented as:
- A **lightweight web UI** (e.g. small Flask app)
- Connects to PostgreSQL using environment‑configured credentials.
- Validates profile data before insert/update (e.g. required fields, email format).

---

### 6. Airflow DAG – `jobs_etl_daily`

**📖 For detailed step-by-step pipeline flow documentation, see [ETL Pipeline Flow Documentation](etl_pipeline_flow.md)**

#### 6.1 Purpose

Run a complete **daily batch pipeline** that:

1. Reads active job profiles.
2. Extracts and normalizes job postings.
3. Identifies and enriches missing companies.
4. Builds marts tables for downstream use.
5. Ranks jobs per profile.
6. Runs data quality checks.
7. Sends email summaries.

#### 6.2 Task List and Order (Phase 2)

**Note**: Tables are created automatically by Docker initialization scripts (`docker/init/02_create_tables.sql`) before DAG execution. No initialization task is needed.

1. **`extract_job_postings`**
   - Calls Source‑extractor (jobs).
   - Reads active profiles from `marts.profile_preferences`.
   - For each profile, calls JSearch API using parameters based on `Project Documentation/jsearch.md`.
   - Writes raw JSON responses to `raw.jsearch_job_postings` with technical metadata.

2. **`normalize_jobs`**
   - Runs dbt models to transform `raw.jsearch_job_postings` → `staging.jsearch_job_postings`.
   - Flattens JSON, standardizes types, handles nulls, and deduplicates on `job_id`.
   - Adds `dwh_` technical columns.

3. **`extract_companies`**
   - Scans `staging.jsearch_job_postings` for employer names/domains.
   - Identifies companies that are **not yet enriched** (using `staging.company_enrichment_queue`).
   - Marks them as queued/searched to avoid duplicate work.
   - Calls Glassdoor API (see `Project Documentation/glassdoor_companies.md`) for each missing company.
   - Writes raw JSON responses to `raw.glassdoor_companies` with `company_lookup_key` and technical metadata.

4. **`normalize_companies`**
   - Runs dbt models to transform `raw.glassdoor_companies` → `staging.glassdoor_companies`.
   - Flattens JSON, standardizes fields, deduplicates companies by `company_id` or normalized name, and adds `dwh_` columns.

5. **`dbt_modelling`**
   - Runs dbt models to build marts:
     - `marts.dim_companies` from `staging.glassdoor_companies`.
     - `marts.fact_jobs` from `staging.jsearch_job_postings` joined to `dim_companies` where possible.
     - A basic `marts.dim_ranking` table structure ready to store scores.

6. **`rank_jobs`**
   - Calls Ranker service (MVP algorithm).
   - Reads `marts.fact_jobs` and active `marts.profile_preferences`.
   - Scores each job/profile pair based on:
     - Location match.
     - Keyword match between profile query and job title/description.
     - Recency of posting.
   - Normalizes scores to a 0–100 range.
   - Writes scores into `marts.dim_ranking`.

7. **`dbt_tests`**
   - Executes dbt tests for key models (e.g. uniqueness of surrogate keys, not‑null constraints).
   - Fails or flags the DAG run if critical tests fail.

8. **`notify_daily`**
   - For each active profile:
     - Reads top N jobs from `marts.dim_ranking` joined to `marts.fact_jobs`.
     - Composes a simple text/HTML email with job list.
     - Sends via SMTP.
   - Logs email sending results per profile.

#### 6.3 Scheduling and Monitoring

- DAG scheduled once daily at **07:00 America/Toronto**.
- Each task has:
  - Retry policy (retries with delay for transient failures).
  - Clear logging (e.g. number of rows processed, number of API calls).
- Basic alerting:
  - Failure notifications (email or log) when DAG or critical tasks fail.

---

### 7. Phased Implementation

#### 7.1 Phase 1 – Project Scaffold & Local Runtime

- Set up Git repository and folder structure.
- Create database schema initialization script:
  - SQL script creates schemas `raw`, `staging`, `marts`
  - Script mounted in Docker for automatic execution on first container start
  - **Note**: Schemas are infrastructure created by initialization script; dbt models create/manage all tables within those schemas
- Create `docker-compose` stack with:
  - PostgreSQL (schemas: `raw`, `staging`, `marts` automatically created via init script).
  - Airflow (webserver + scheduler).
  - Optional container for the profile management UI.
- Initialize dbt project, pointing at local PostgreSQL.
  - **Note**: Schemas are created by initialization script; dbt models create/manage all tables within those schemas.
- Configure Python tooling:
  - `pytest`, `ruff` for linting and formatting (replaces flake8/black/isort).
- Add baseline documentation and `.env.example`.

**Outcome**: A developer can start the local stack, see the `jobs_etl_daily` DAG, and run tests/linting successfully.

#### 7.2 Phase 2 – First End‑to‑End Local MVP Path

- Implement full **Phase 2 task flow** as detailed in section 6.2:
  - Jobs extracted to raw.
  - Jobs normalized to staging.
  - Companies identified from staging, extracted to raw, and normalized to staging.
  - Marts built with fact and dimension tables.
  - Basic ranking and email notifications.
- Implement `marts.profile_preferences` and the profile management interface.

**Outcome**: From one or more active profiles, the DAG runs end‑to‑end locally and sends daily job emails.

#### 7.3 Phase 3 – Enrichment & Data Quality (Feature Depth)

- Add Enricher service:
  - spaCy‑based skills extraction.
  - Seniority extraction.
  - Writes enrichment results into `staging.jsearch_job_postings`.
- Extend Ranker:
  - Incorporate skills, salary, company rating, seniority, and employment type into scoring.
  - Output `rank_explain` JSON in `marts.dim_ranking`.
- Strengthen data quality:
  - Comprehensive dbt tests and, optionally, a run metrics table for ETL statistics.
- Enhance profile UI with richer statistics and health indicators.

**Outcome**: Higher‑quality, more explainable rankings and better visibility into data quality and pipeline behavior.

#### 7.4 Phase 4 – AWS Lift

- Migrate database to **AWS RDS (PostgreSQL)**.
- Deploy services to **ECS** and Airflow to **EC2** (or later to a managed service).
- Use **S3** for:
  - Archival of raw JSON payloads.
  - Optional exports for Tableau or other analytics.
- Connect Tableau to RDS `marts` schema and build initial dashboards:
  - Skills trends, salary trends, job volumes, company ratings, ranking distributions.
- Add basic CI/CD (e.g. GitHub Actions) for tests, Docker builds, and deployments.
- Implement security best practices:
  - IAM roles, security groups, Secrets Manager for credentials, least‑privilege access.

**Outcome**: Production‑ready cloud deployment of the platform, with BI integration and basic operational monitoring.

---

### 8. Non‑Functional Requirements and Best Practices

- **Extensibility**
  - Source‑extractor built around an abstraction so additional job APIs can be added with minimal changes.
  - Ranking weights and factors configured via config or tables rather than hard‑coded.
  - Enricher structured so new enrichment types can be plugged in.

- **Code Quality**
  - Python code adheres to PEP 8 and project linting rules.
  - Unit tests cover core logic (API clients, parsing, ranking).
  - Integration tests validate key pipeline paths.

- **Data Quality**
  - dbt tests for keys, relationships, and important business rules.
  - Validation and logging at ingestion to catch malformed API responses.

- **Security**
  - API keys and DB credentials stored in environment variables.
  - No secrets committed to Git.
  - Network security for AWS resources (VPC, security groups, SSL where appropriate).

- **Observability**
  - Meaningful logging in Python services and Airflow tasks.
  - Basic metrics captured per run (rows processed, API calls, failures).
  - Ability to debug and trace issues by profile and by run.


