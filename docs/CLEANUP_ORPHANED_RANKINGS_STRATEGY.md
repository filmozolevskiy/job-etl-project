# Strategy for Removing Orphaned Rankings

## Problem Statement

There are currently 159 rows in `marts.dim_ranking` that reference `jsearch_job_id` values that don't exist in `marts.fact_jobs`. This violates referential integrity and causes the dbt relationship test to fail.

## Root Cause Analysis

Orphaned rankings can occur due to several reasons:

1. **Timing Issues in ETL Pipeline**: Rankings may be created before jobs are normalized into `fact_jobs`
2. **Job Deletion**: Jobs may be removed from `fact_jobs` (e.g., during deduplication or data cleanup) but rankings are not cleaned up
3. **Failed Normalization**: Jobs may fail to be normalized into `fact_jobs` but rankings were already created
4. **Data Migration Issues**: Historical data inconsistencies from previous ETL runs

## Cleanup Strategy

### Phase 1: Analysis (TODO: cleanup_orphaned_rankings_analysis)

1. **Query to Identify Orphaned Rankings**:
   ```sql
   SELECT 
       dr.jsearch_job_id,
       dr.profile_id,
       dr.rank_score,
       dr.ranked_at,
       dr.dwh_load_timestamp
   FROM marts.dim_ranking dr
   LEFT JOIN marts.fact_jobs fj
       ON dr.jsearch_job_id = fj.jsearch_job_id
       AND dr.profile_id = fj.profile_id
   WHERE fj.jsearch_job_id IS NULL
   ORDER BY dr.ranked_at DESC;
   ```

2. **Analysis Questions**:
   - How old are these orphaned rankings? (Check `ranked_at` and `dwh_load_timestamp`)
   - Are they from specific profiles?
   - Are they from a specific time period?
   - Do the `jsearch_job_id` values exist in `staging.jsearch_job_postings` but not in `fact_jobs`?

3. **Document Findings**:
   - Create a report showing the distribution of orphaned rankings
   - Identify patterns (e.g., all from a specific date range)
   - Determine if this is a one-time issue or ongoing problem

### Phase 2: Cleanup Implementation (TODO: cleanup_orphaned_rankings_script)

#### Option A: One-Time Cleanup Script

Create a Python script or SQL script to:
1. Identify orphaned rankings (using the query above)
2. Log what will be deleted (for audit purposes)
3. Delete orphaned rankings
4. Record metrics about the cleanup

**SQL Cleanup Script**:
```sql
-- Step 1: Create backup/audit log
CREATE TABLE IF NOT EXISTS marts.dim_ranking_cleanup_audit AS
SELECT 
    dr.*,
    CURRENT_TIMESTAMP as cleanup_timestamp,
    'orphaned_ranking' as cleanup_reason
FROM marts.dim_ranking dr
LEFT JOIN marts.fact_jobs fj
    ON dr.jsearch_job_id = fj.jsearch_job_id
    AND dr.profile_id = fj.profile_id
WHERE fj.jsearch_job_id IS NULL;

-- Step 2: Delete orphaned rankings
DELETE FROM marts.dim_ranking dr
WHERE NOT EXISTS (
    SELECT 1
    FROM marts.fact_jobs fj
    WHERE dr.jsearch_job_id = fj.jsearch_job_id
      AND dr.profile_id = fj.profile_id
);

-- Step 3: Verify cleanup
SELECT COUNT(*) as remaining_orphaned_rankings
FROM marts.dim_ranking dr
LEFT JOIN marts.fact_jobs fj
    ON dr.jsearch_job_id = fj.jsearch_job_id
    AND dr.profile_id = fj.profile_id
WHERE fj.jsearch_job_id IS NULL;
```

#### Option B: Maintenance DAG Task

Add a new Airflow task to the ETL pipeline that:
1. Runs periodically (e.g., daily or weekly)
2. Identifies and deletes orphaned rankings
3. Records metrics in `marts.etl_run_metrics`
4. Sends alerts if a large number of orphaned rankings are found

**Implementation Location**: `airflow/dags/task_functions.py`

```python
def cleanup_orphaned_rankings_task(**context) -> dict[str, Any]:
    """
    Cleanup task to remove orphaned rankings from dim_ranking.
    
    Orphaned rankings are rankings that reference jsearch_job_id values
    that don't exist in fact_jobs (violates referential integrity).
    """
    # Implementation here
    pass
```

### Phase 3: Prevention (TODO: cleanup_orphaned_rankings_prevention)

#### 3.1: Update Ranker Service

Modify `services/ranker/job_ranker.py` to:
1. **Validate before ranking**: Check that jobs exist in `fact_jobs` before creating rankings
2. **Use transactions**: Ensure rankings are only created if jobs exist
3. **Add logging**: Log when rankings are skipped due to missing jobs

**Example validation**:
```python
def rank_jobs_for_profile(self, profile: dict[str, Any]) -> int:
    # Get jobs for this profile
    jobs = self.get_jobs_for_profile(profile_id)
    
    # Validate jobs exist in fact_jobs
    valid_jobs = self._validate_jobs_exist_in_fact_jobs(jobs)
    
    if len(valid_jobs) < len(jobs):
        logger.warning(
            f"Skipping {len(jobs) - len(valid_jobs)} jobs that don't exist in fact_jobs"
        )
    
    # Only rank valid jobs
    for job in valid_jobs:
        # ... ranking logic ...
```

#### 3.2: Update ETL Pipeline Order

Ensure the pipeline order is correct:
1. `extract_job_postings` - Extract jobs
2. `normalize_jobs` - Normalize into `staging.jsearch_job_postings`
3. `dbt_modelling` - Build `fact_jobs` from staging
4. `rank_jobs` - **Only after fact_jobs is built**
5. `dbt_tests` - Validate referential integrity

#### 3.3: Add Database Constraints (Optional)

Consider adding a foreign key constraint (if not already present):
```sql
ALTER TABLE marts.dim_ranking
ADD CONSTRAINT fk_dim_ranking_fact_jobs
FOREIGN KEY (jsearch_job_id, profile_id)
REFERENCES marts.fact_jobs(jsearch_job_id, profile_id)
ON DELETE CASCADE;
```

**Note**: This would require ensuring all existing data is clean first, and may impact performance.

### Phase 4: Testing (TODO: cleanup_orphaned_rankings_testing)

1. **Test Cleanup Script**:
   - Run on a test/staging database first
   - Verify no valid rankings are deleted
   - Check that the cleanup query correctly identifies orphaned rankings

2. **Test Prevention Measures**:
   - Run ETL pipeline and verify no new orphaned rankings are created
   - Test the ranker validation logic
   - Verify dbt tests pass after cleanup

3. **Monitor After Implementation**:
   - Track metrics to see if orphaned rankings continue to appear
   - Set up alerts if orphaned rankings exceed a threshold

## Implementation Priority

1. **High Priority**: Phase 1 (Analysis) - Understand the scope and root cause
2. **High Priority**: Phase 2 (Cleanup) - Remove existing orphaned rankings
3. **Medium Priority**: Phase 3 (Prevention) - Prevent future orphaned rankings
4. **Low Priority**: Phase 4 (Testing) - Ongoing monitoring and validation

## Metrics to Track

- Number of orphaned rankings found
- Number of orphaned rankings deleted
- Number of rankings skipped during ranking (due to validation)
- Time taken for cleanup
- Frequency of orphaned rankings appearing (should decrease to zero)

## Rollback Plan

If cleanup causes issues:
1. Restore from `marts.dim_ranking_cleanup_audit` table (if backup was created)
2. Re-run ranking for affected profiles
3. Investigate root cause before re-attempting cleanup

