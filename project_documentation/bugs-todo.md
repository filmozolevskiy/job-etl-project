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

### Bug #3: Missing Deduplication at Job Extractor Level for Raw Jobs

- **Date Found**: 2025-12-16
- **Description**: The job extraction service currently relies on downstream staging layer deduplication to handle duplicate job postings. A comment in `services/extractor/job_extractor.py` (around lines 149–150) notes that "Duplicates will be handled by staging layer deduplication," but there is no deduplication at the extractor/raw layer itself. This can result in unnecessary duplicate rows being written to `raw.jsearch_job_postings`, increasing storage and processing overhead.
- **Location**: 
  - `services/extractor/job_extractor.py` - Insert logic for writing to `raw.jsearch_job_postings` (comment near lines 149–150)
- **Severity**: Low
- **Status**: Open
- **Notes**:
  - Desired behavior: Add deduplication logic at the job extractor level so that only unique jobs are stored in the raw layer, in addition to any existing staging-level deduplication.
  - Implementation may involve checking for existing `jsearch_job_id` (or equivalent unique key) before inserting, or using `ON CONFLICT` logic on a suitable unique constraint.

### Bug #4: Inconsistent Field Value Casing in Database

- **Date Found**: 2025-01-17
- **Description**: Multiple fields in the database have inconsistent casing, leading to data quality issues and potential query/filtering problems. The staging layer extracts values directly from the API without normalization, while the enricher service normalizes some fields. This creates a mismatch where:
  - **Salary Period**: API returns uppercase values ("YEAR", "HOUR", "MONTH") but enricher normalizes to lowercase ("year", "hour", "month"). If enricher doesn't run or values come directly from API, they remain uppercase, creating mixed casing in the database.
  - **Employment Type**: API returns uppercase ("FULLTIME", "PARTTIME", "CONTRACTOR") which are stored as-is, but there may be inconsistencies if values come from different sources.
  - **Other fields**: Remote type and seniority level are normalized by enricher (lowercase), but if enricher doesn't run, these may be missing or inconsistent.
- **Location**: 
  - `dbt/models/staging/jsearch_job_postings.sql` - Lines 45-46, 62 (extracts values directly without normalization)
  - `services/enricher/job_enricher.py` - Normalizes salary_period to lowercase, but only if enricher runs
  - `services/ranker/job_ranker.py` - Lines 373, 660-661, 791 (normalizes for comparison but stored values may be inconsistent)
- **Severity**: Medium
- **Status**: Open
- **Notes**:
  - **Desired behavior**: All field values should be normalized to a consistent casing standard:
    - `job_salary_period`: lowercase ("year", "month", "week", "day", "hour")
    - `job_employment_type` and `employment_types`: uppercase ("FULLTIME", "PARTTIME", "CONTRACTOR", "TEMPORARY", "INTERN")
    - `remote_work_type`: lowercase ("remote", "hybrid", "onsite")
    - `seniority_level`: lowercase ("intern", "junior", "mid", "senior", "executive")
    - `job_salary_currency`: uppercase ("USD", "CAD", "EUR", "GBP")
  - **Implementation approach**: Add normalization logic in the staging dbt model (`dbt/models/staging/jsearch_job_postings.sql`) to ensure consistent casing regardless of whether enricher runs. Use PostgreSQL `LOWER()` and `UPPER()` functions or CASE statements to normalize values during extraction.
  - **Data migration**: Existing data in the database may need to be updated to match the new casing standards. Consider creating a migration script to update existing records.
  - **Impact**: This inconsistency can cause issues with filtering, grouping, and comparisons in queries. For example, `WHERE job_salary_period = 'year'` would miss records with `job_salary_period = 'YEAR'`.

### Bug #5: Incorrect Country Code for United Kingdom

- **Date Found**: 2025-01-17
- **Description**: The code uses "uk" as the country code for United Kingdom in several places, but JSearch API (and ISO 3166-1 alpha-2 standard) uses "gb" for United Kingdom. This mismatch can cause issues when:
  - Users enter "uk" in the profile UI, but JSearch API expects "gb"
  - Country-based currency detection fails for UK jobs
  - Location matching in the ranker doesn't work correctly for UK profiles
- **Location**: 
  - `services/enricher/job_enricher.py` - Line 345: `"UK": "GBP"` in country_to_currency mapping (should be "GB")
  - `services/ranker/job_ranker.py` - Line 179: `"uk": ["united kingdom", "england", "britain"]` in country_mappings (should be "gb")
  - `campaign_ui/templates/create_profile.html` - Line 34: Placeholder example shows "uk" (should be "gb")
- **Severity**: Medium
- **Status**: Open
- **Notes**:
  - **Desired behavior**: Use "gb" (ISO 3166-1 alpha-2 standard) consistently for United Kingdom throughout the codebase, matching JSearch API expectations.
  - **Implementation approach**: 
    1. Update `country_to_currency` mapping in `services/enricher/job_enricher.py` to use "GB" instead of "UK" (keep "UK" as an alias for backward compatibility if needed)
    2. Update `country_mappings` in `services/ranker/job_ranker.py` to use "gb" instead of "uk"
    3. Update UI placeholder examples to show "gb" instead of "uk"
    4. Consider adding "uk" as an alias that maps to "gb" for user input handling (normalize user input from "uk" to "gb" before API calls)
  - **Data migration**: Existing profiles with `country = 'uk'` should be updated to `country = 'gb'` in the database.
  - **Impact**: Users entering "uk" may not get correct results from JSearch API, and currency detection/location matching may fail for UK-related jobs and profiles.

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

