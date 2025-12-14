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

### Bug #2: Ranker ON CONFLICT Fails Due to Missing Primary Key Constraint

- **Date Found**: 2025-12-14
- **Description**: The `rank_jobs` task fails with `psycopg2.errors.InvalidColumnReference: there is no unique or exclusion constraint matching the ON CONFLICT specification` when trying to insert/update rankings in `marts.dim_ranking`. The code uses `ON CONFLICT (jsearch_job_id, profile_id)` but the table doesn't have a unique constraint on these columns. The task completes with status SUCCESS but ranks 0 jobs, effectively failing silently.
- **Location**: 
  - `services/ranker/job_ranker.py` - Line 381-399, `_write_rankings` method
  - `dbt/models/marts/dim_ranking.sql` - Table definition with post_hook that should create the primary key
- **Severity**: High
- **Status**: Open
- **Notes**: 
  - The `dim_ranking` table is created by dbt with a post_hook that should add `PRIMARY KEY (jsearch_job_id, profile_id)` as `dim_ranking_pkey`
  - The error occurs for all profiles during ranking, causing the entire ranking step to fail silently (0 jobs ranked)
  - Possible causes:
    1. dbt model hasn't been run, so the table doesn't exist or lacks the constraint
    2. Table was created manually without the primary key constraint
    3. Constraint was dropped or never created properly
  - The task reports SUCCESS even though it failed, which is misleading
  - Fix options:
    1. Ensure dbt runs before the DAG to create the table with proper constraints
    2. Add a check/creation of the constraint in the ranker service before attempting inserts
    3. Verify the table schema matches expectations and add the constraint if missing
    4. Change the error handling to fail the task when ranking fails

---

## Fixed Bugs

<!-- Move bugs here once they are resolved -->

---

## Notes

- This list should be updated as bugs are discovered during development
- Bugs should be prioritized based on severity and impact
- When fixing a bug, move it to the "Fixed Bugs" section with the resolution date

