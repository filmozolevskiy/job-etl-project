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

---

## Fixed Bugs

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

