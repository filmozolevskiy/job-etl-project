# Bugs TODO List

This document tracks bugs that have been identified and need to be fixed later.

## Bug Tracking Format

Each bug entry should include:
- **Date Found**: When the bug was discovered
- **Description**: Clear description of the issue
- **Location**: File(s) or component(s) affected
- **Severity**: Critical / High / Medium / Low
- **Status**: Open / In Progress / Fixed / Deferred
- **Notes**: Any additional context or workarounds

---

## Open Bugs

_No open bugs at this time._

---

## Fixed Bugs

### Bug #6: Seniority Level Detection Should Prioritize Job Title Over Description

- **Date Found**: 2025-01-17
- **Date Fixed**: 2025-01-17
- **Description**: The `extract_seniority()` method was combining job title and description into a single text string and searching both simultaneously. This could lead to incorrect seniority detection when the description contained seniority indicators that conflicted with or overrode the title. For example, a "Junior Software Developer" title might be incorrectly classified as "senior" if the description mentioned "senior engineer" requirements.
- **Location**: 
  - `services/enricher/job_enricher.py` - `extract_seniority()` method (line 199-242)
- **Severity**: Medium
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: The method combined title and description into one string (`f"{job_title} {job_description}"`) and searched the combined text, which meant description matches could override title matches.
  - **Fix**: Refactored `extract_seniority()` to:
    1. First check only the job title for seniority patterns
    2. Only if no match is found in the title, then check the description
    3. Return the first match found (prioritizing title)
  - **Changes Made**:
    1. Created helper function `_check_text_for_seniority()` to check a single text string for patterns
    2. Updated logic to check title first, then description only as fallback
    3. Updated docstring to clarify the priority behavior
    4. Added test `test_extract_seniority_title_priority()` to verify title takes priority when both have seniority indicators
    5. Updated existing test `test_extract_seniority_with_description()` docstring to clarify it tests the fallback case
    6. **Pattern matching refinement**: Sorted patterns by length (longest first) within each seniority level to ensure more specific patterns (e.g., "internship") are checked before shorter ones (e.g., "intern"). This prevents potential partial matches and ensures the most specific pattern is matched first, even though word boundaries (`\b`) should prevent substring matches.
    7. Added test `test_extract_seniority_internship_vs_intern()` to verify "internship" and "intern" are both correctly matched without partial matching issues
  - The fix ensures that job titles are the primary source of truth for seniority level, with description only used as a fallback when the title doesn't contain seniority indicators. Pattern matching now prioritizes longer, more specific patterns to avoid any edge cases with partial matches.

### Bug #1: Profile Preferences Tracking Fields Not Updated by DAG

- **Date Found**: 2025-12-14
- **Date Fixed**: 2025-01-17
- **Description**: The `marts.profile_preferences` table has tracking fields (`total_run_count`, `last_run_at`, `last_run_status`, `last_run_job_count`) that are never updated when the DAG runs. The DAG reads from `profile_preferences` to get active profiles, but after processing (extraction, ranking, notifications), it does not update these tracking fields to reflect the run status and results.
- **Location**: 
  - `airflow/dags/task_functions.py` - Task functions (extract_job_postings_task, send_notifications_task)
- **Severity**: Medium
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: The DAG tasks were not updating the tracking fields after processing profiles, even though the fields existed in the schema.
  - **Fix**: Added `update_profile_tracking_fields()` helper function to `airflow/dags/task_functions.py` that updates all tracking fields. The function is called:
    1. After `extract_job_postings_task` completes successfully - updates `last_run_at`, `last_run_status` ('success'), `last_run_job_count` (number of jobs extracted), and increments `total_run_count`
    2. After `extract_job_postings_task` fails - updates all profiles with 'error' status and job_count=0
    3. After `send_notifications_task` completes - updates `last_run_at` and `last_run_status` based on notification success (without incrementing `total_run_count` again)
  - **Changes Made**:
    1. Added `update_profile_tracking_fields()` function with optional `increment_run_count` parameter
    2. Integrated tracking field updates into `extract_job_postings_task` (both success and error paths)
    3. Integrated tracking field updates into `send_notifications_task` (final status update)
  - The fix ensures that profile tracking fields are updated after each DAG run, enabling the Profile UI to display accurate run history and statistics.

### Bug #3: Missing Deduplication at Job Extractor Level for Raw Jobs

- **Date Found**: 2025-12-16
- **Date Fixed**: 2026-01-02
- **Description**: The job extraction service currently relied on downstream staging layer deduplication to handle duplicate job postings. A comment in `services/extractor/job_extractor.py` noted that "Duplicates will be handled by staging layer deduplication," but there was no deduplication at the extractor/raw layer itself. This could result in unnecessary duplicate rows being written to `raw.jsearch_job_postings`, increasing storage and processing overhead.
- **Location**: 
  - `services/extractor/job_extractor.py` - Insert logic for writing to `raw.jsearch_job_postings`
  - `services/extractor/queries.py` - Query for checking existing jobs
- **Severity**: Low
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: The extractor service was inserting all jobs from the API response without checking for existing duplicates in the raw table.
  - **Fix**: Added deduplication logic at the extractor level:
    1. Created `CHECK_EXISTING_JOBS` query in `services/extractor/queries.py` to check for existing jobs by `job_id` and `campaign_id`
    2. Updated `_write_jobs_to_db()` method in `services/extractor/job_extractor.py` to:
       - Check for existing jobs before inserting
       - Filter out duplicates from the jobs list
       - Only insert unique jobs
       - Log the number of duplicates skipped
  - **Changes Made**:
    1. Added `CHECK_EXISTING_JOBS` query to check for existing jobs in raw table
    2. Updated `_write_jobs_to_db()` to perform deduplication before bulk insert
    3. Added logging to track duplicate jobs skipped
    4. Removed comment about relying on staging layer deduplication
  - The fix ensures that only unique jobs are stored in the raw layer, reducing storage and processing overhead while maintaining data integrity.

### Bug #4: Inconsistent Field Value Casing in Database

- **Date Found**: 2025-01-17
- **Date Fixed**: 2026-01-02
- **Description**: Multiple fields in the database had inconsistent casing, leading to data quality issues and potential query/filtering problems. The staging layer extracted values directly from the API without normalization, while the enricher service normalized some fields. This created a mismatch where:
  - **Salary Period**: API returns uppercase values ("YEAR", "HOUR", "MONTH") but enricher normalizes to lowercase ("year", "hour", "month"). If enricher doesn't run or values come directly from API, they remain uppercase, creating mixed casing in the database.
  - **Employment Type**: API returns uppercase ("FULLTIME", "PARTTIME", "CONTRACTOR") which are stored as-is, but there may be inconsistencies if values come from different sources.
  - **Other fields**: Remote type and seniority level are normalized by enricher (lowercase), but if enricher doesn't run, these may be missing or inconsistent.
- **Location**: 
  - `dbt/models/staging/jsearch_job_postings.sql` - Extracts values directly without normalization
  - `services/enricher/job_enricher.py` - Normalizes salary_period to lowercase, but only if enricher runs
  - `services/ranker/job_ranker.py` - Normalizes for comparison but stored values may be inconsistent
- **Severity**: Medium
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: The staging dbt model extracted field values directly from the API without normalization, while the enricher service normalized some fields. This created inconsistent casing depending on whether the enricher ran.
  - **Fix**: Added normalization logic in the staging dbt model to ensure consistent casing regardless of whether enricher runs:
    1. Normalized `job_salary_period` to lowercase using `LOWER()` function
    2. Normalized `job_employment_type` to uppercase using `UPPER()` function
    3. Normalized `employment_types` (comma-separated string) to uppercase by splitting, uppercasing each value, and rejoining
  - **Changes Made**:
    1. Updated `dbt/models/staging/jsearch_job_postings.sql` to normalize field casing during extraction
    2. Created migration script `docker/init/12_normalize_field_casing.sql` to update existing data
    3. Migration script normalizes all affected fields: `job_salary_period`, `job_employment_type`, `employment_types`, `remote_work_type`, `seniority_level`, and `job_salary_currency`
  - The fix ensures consistent casing standards throughout the database, preventing filtering and comparison issues.

### Bug #5: Incorrect Country Code for United Kingdom

- **Date Found**: 2025-01-17
- **Date Fixed**: 2026-01-02
- **Description**: The code used "uk" as the country code for United Kingdom in several places, but JSearch API (and ISO 3166-1 alpha-2 standard) uses "gb" for United Kingdom. This mismatch could cause issues when:
  - Users enter "uk" in the profile UI, but JSearch API expects "gb"
  - Country-based currency detection fails for UK jobs
  - Location matching in the ranker doesn't work correctly for UK profiles
- **Location**: 
  - `services/enricher/job_enricher.py` - `"UK": "GBP"` in country_to_currency mapping
  - `services/ranker/job_ranker.py` - `"uk": ["united kingdom", "england", "britain"]` in country_mappings
  - `campaign_ui/templates/create_campaign.html` - Placeholder example shows "uk"
- **Severity**: Medium
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: The codebase used "uk" instead of "gb" (ISO 3166-1 alpha-2 standard) for United Kingdom, which doesn't match JSearch API expectations.
  - **Fix**: Updated all references to use "gb" consistently:
    1. Updated `country_mappings` in `services/ranker/job_ranker.py` to use "gb" instead of "uk"
    2. Updated UI placeholder in `campaign_ui/templates/create_campaign.html` to show "gb" instead of "uk"
    3. Added normalization in `campaign_ui/app.py` to convert user input "uk" to "gb" in both create and edit campaign routes
    4. Note: `services/enricher/job_enricher.py` already had "GB" as primary key with "UK" as alias (kept for backward compatibility)
  - **Changes Made**:
    1. Updated `country_mappings` in `services/ranker/job_ranker.py`
    2. Updated placeholder in `campaign_ui/templates/create_campaign.html`
    3. Added normalization logic in `campaign_ui/app.py` for both create and edit routes
    4. Created migration script `docker/init/11_fix_uk_country_code.sql` to update existing campaigns
  - The fix ensures consistent use of "gb" (ISO 3166-1 alpha-2 standard) throughout the codebase, matching JSearch API expectations while maintaining backward compatibility.

### Bug #7: "Job Not Found" Error When Clicking Jobs from Campaign Details

- **Date Found**: 2026-01-02
- **Date Fixed**: 2026-01-02
- **Description**: When viewing campaign details and clicking on a job to view its details, users encountered an error: "Job {job_id} not found." The job existed in the database (verified by running the `GET_JOBS_FOR_CAMPAIGN` query), appeared in the campaign jobs list, but when clicked, the `GET_JOB_BY_ID` query failed to retrieve it, resulting in the "Job not found" error.
- **Location**: 
  - `services/jobs/queries.py` - `GET_JOB_BY_ID` query: Used `INNER JOIN marts.job_campaigns` and filtered by `jc.user_id`
  - `services/jobs/queries.py` - `GET_JOBS_FOR_CAMPAIGN` query: Returned jobs that may not be retrievable by `GET_JOB_BY_ID`
  - `services/jobs/job_service.py` - `get_job_by_id()` method: Returned None when query found no matching job
- **Severity**: Medium
- **Status**: Fixed
- **Resolution**:
  - **Root Cause**: `GET_JOB_BY_ID` enforced `jc.user_id = %s` via an `INNER JOIN marts.job_campaigns`. When a user (possibly an admin) viewed jobs that belonged to a different user's campaign, the query filtered them out, even though the job existed and showed up in the list produced by `GET_JOBS_FOR_CAMPAIGN` (which does not join `job_campaigns`).
  - **Fix**: Changed `GET_JOB_BY_ID` query to match `GET_JOBS_FOR_CAMPAIGN` behavior:
    1. Changed `INNER JOIN marts.job_campaigns` to `LEFT JOIN marts.job_campaigns`
    2. Removed `AND jc.user_id = %s` filter from WHERE clause
    3. Updated query parameter count in `job_service.py` from 4 to 3 parameters
  - **Changes Made**:
    1. Updated `GET_JOB_BY_ID` query in `services/jobs/queries.py` to use `LEFT JOIN` instead of `INNER JOIN` and removed user_id filter
    2. Updated `get_job_by_id()` method in `services/jobs/job_service.py` to pass correct number of parameters
  - The fix ensures that jobs displayed in the campaign jobs list are retrievable when clicked, regardless of who owns the campaign. Notes and status are still filtered by the requesting user via LEFT JOINs with user_id filters.

### Bug #2: Ranker ON CONFLICT Fails Due to Missing Primary Key Constraint

- **Date Found**: 2025-12-14
- **Date Fixed**: 2025-12-14
- **Description**: The `rank_jobs` task fails with `psycopg2.errors.InvalidColumnReference: there is no unique or exclusion constraint matching the ON CONFLICT specification` when trying to insert/update rankings in `marts.dim_ranking`. The code uses `ON CONFLICT (jsearch_job_id, profile_id)` but the table doesn't have a unique constraint on these columns. The task completes with status SUCCESS but ranks 0 jobs, effectively failing silently.
- **Location**: 
  - `services/ranker/job_ranker.py` - Line 381-399, `_write_rankings` method
  - `dbt/models/marts/dim_ranking.sql` - Table definition with post_hook that should create the primary key
- **Severity**: High
- **Status**: Fixed
- **Resolution**: 
  - **Root Cause**: The `dim_ranking` table was supposed to be created by dbt, but dbt is not run automatically in the Docker setup. The table was either missing or existed without the primary key constraint.
  - **Fix**: Added `dim_ranking` table creation to `docker/init/02_create_tables.sql` with the primary key constraint `(jsearch_job_id, profile_id)` defined inline. This ensures the table is created during database initialization, consistent with other tables like `profile_preferences`.
  - **Changes Made**:
    1. Added `CREATE TABLE IF NOT EXISTS marts.dim_ranking` with primary key constraint to `docker/init/02_create_tables.sql`
    2. Updated GRANT permissions to include `dim_ranking` table
    3. Removed `_ensure_dim_ranking_table()` workaround method from `services/ranker/job_ranker.py`
    4. Updated dbt model comments to note that table is primarily created by init script
  - The fix ensures the table and constraint exist from database initialization, preventing the `ON CONFLICT` error. The ranker no longer needs to check/create the table at runtime.

---

## Notes

- This list should be updated as bugs are discovered during development
- Bugs should be prioritized based on severity and impact
- When fixing a bug, move it to the "Fixed Bugs" section with the resolution date

