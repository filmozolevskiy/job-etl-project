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

### Bug #1: Profile Preferences Tracking Fields Not Updated by DAG

- **Date Found**: 2025-12-14
- **Description**: The `marts.profile_preferences` table has tracking fields (`total_run_count`, `last_run_at`, `last_run_status`, `last_run_job_count`) that are never updated when the DAG runs. The DAG reads from `profile_preferences` to get active profiles, but after processing (extraction, ranking, notifications), it does not update these tracking fields to reflect the run status and results.
- **Location**: 
  - `airflow/dags/jobs_etl_daily.py` - Main DAG definition
  - `airflow/dags/task_functions.py` - Task functions (extract_job_postings_task, rank_jobs_task, send_notifications_task)
  - `services/extractor/job_extractor.py` - Job extraction service
  - `services/ranker/job_ranker.py` - Job ranking service
  - `services/notifier/notification_coordinator.py` - Notification service
- **Severity**: Medium
- **Status**: Open
- **Notes**: 
  - The tracking fields exist in the table schema (defined in `docker/init/02_create_tables.sql`)
  - Currently only the Profile Management UI (`profile_ui/app.py`) updates `profile_preferences`, but only for CRUD operations
  - Expected behavior: After each DAG run, for each processed profile, update:
    - `last_run_at` = current timestamp
    - `last_run_status` = 'success' or 'error' based on task results
    - `last_run_job_count` = number of jobs extracted/ranked for that profile
    - `total_run_count` = increment by 1
  - This would enable tracking of DAG execution history per profile in the UI

---

## Fixed Bugs

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

