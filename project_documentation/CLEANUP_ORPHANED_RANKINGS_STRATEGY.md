# Cleanup Orphaned Rankings Strategy

## Overview

This document outlines the strategy for identifying, analyzing, cleaning up, and preventing orphaned rankings in the `marts.dim_ranking` table.

## Problem Definition

**Orphaned rankings** are rankings in `marts.dim_ranking` where the `(jsearch_job_id, campaign_id)` pair does not exist in `marts.fact_jobs`. This creates data integrity issues and can lead to:

- Incorrect job recommendations
- Broken foreign key relationships (logical)
- Wasted storage and query performance issues
- Confusion in reporting and analytics

## Root Causes

Based on analysis, orphaned rankings can occur due to:

1. **Normalization Failures**: Jobs exist in `staging.jsearch_job_postings` but fail to reach `marts.fact_jobs` due to:
   - dbt model failures
   - Data quality issues preventing fact table insertion
   - Incremental model logic excluding valid jobs

2. **Deleted Jobs**: Jobs that were ranked but later deleted from `fact_jobs`:
   - Manual data cleanup
   - Incremental model removing old jobs
   - Data refresh operations

3. **Timing Issues**: Race conditions in the ETL pipeline:
   - Rankings created before `fact_jobs` is fully populated
   - Parallel task execution causing inconsistencies
   - DAG task order violations

4. **Data Inconsistencies**: Historical data issues from:
   - Schema migrations
   - Data model changes
   - Manual database operations

## Analysis Approach

### Step 1: Identify Orphaned Rankings

Query to find orphaned rankings:

```sql
SELECT dr.*
FROM marts.dim_ranking dr
LEFT JOIN marts.fact_jobs fj
    ON dr.jsearch_job_id = fj.jsearch_job_id
    AND dr.campaign_id = fj.campaign_id
WHERE fj.jsearch_job_id IS NULL
```

### Step 2: Analyze Distribution

- **By Campaign**: Identify which campaigns have the most orphaned rankings
- **By Date**: Identify when orphaned rankings were created (timing patterns)
- **By Staging**: Check if orphaned job IDs exist in staging layer (normalization failure indicator)

### Step 3: Root Cause Identification

- If job IDs exist in staging but not in fact_jobs → Normalization failure
- If job IDs don't exist in staging → Deleted jobs or extraction failure
- If concentrated in specific dates → Timing issues
- If spread across all dates → General data inconsistency

## Cleanup Strategy

### Phase 1: Audit Before Deletion

Before deleting any orphaned rankings, create an audit trail:

1. **Create Audit Table**: `marts.dim_ranking_cleanup_audit`
   - Stores all deleted rankings with metadata
   - Includes cleanup timestamp and reason
   - Allows for recovery if needed

2. **Backup Orphaned Rankings**: Insert all orphaned rankings into audit table before deletion

### Phase 2: Safe Deletion

1. **Batch Processing**: Delete in batches (e.g., 1000 rows) to avoid long-running transactions
2. **Transaction Safety**: Use transactions with rollback on error
3. **Verification**: After cleanup, verify no orphaned rankings remain
4. **Idempotency**: Script should be safe to run multiple times

### Phase 3: Metrics Recording

Record cleanup metrics in `marts.etl_run_metrics`:
- Number of rankings deleted
- Execution time
- Campaign distribution
- Root cause breakdown

## Prevention Strategy

### 1. Validation in Ranker Service

Add validation to `JobRanker.rank_jobs_for_campaign()`:

- Before creating rankings, validate that each job exists in `fact_jobs`
- Skip jobs that don't exist (log warning)
- Only create rankings for validated jobs

**Implementation**:
```python
def _validate_job_exists_in_fact_jobs(self, jsearch_job_id: str, campaign_id: int) -> bool:
    """Validate that job exists in fact_jobs before ranking."""
    # Query fact_jobs to verify existence
    # Return True if exists, False otherwise
```

### 2. Pipeline Order Verification

Ensure correct DAG task order:

```
normalize_jobs → dbt_modelling → rank_jobs
```

- `dbt_modelling` must complete before `rank_jobs` runs
- This ensures `fact_jobs` is populated before ranking
- Add DAG validation tests to enforce this order

### 3. Database Constraints (Future Consideration)

Consider adding a foreign key constraint:

```sql
ALTER TABLE marts.dim_ranking
ADD CONSTRAINT fk_dim_ranking_fact_jobs
FOREIGN KEY (jsearch_job_id, campaign_id)
REFERENCES marts.fact_jobs(jsearch_job_id, campaign_id)
ON DELETE CASCADE;
```

**Note**: This requires careful consideration as it may impact:
- Incremental model behavior
- Data refresh operations
- Performance on large datasets

## Implementation Tasks

1. ✅ **Task 3.9.5**: Analyze orphaned rankings
   - Create analysis script
   - Generate comprehensive report
   - Document findings

2. ✅ **Task 3.9.6**: Implement cleanup script
   - Create audit table
   - Implement safe deletion logic
   - Add metrics recording

3. ✅ **Task 3.9.7**: Add validation to ranker service
   - Add job existence validation
   - Skip invalid jobs with logging
   - Add unit and integration tests

4. ✅ **Task 3.9.8**: Verify ETL pipeline order
   - Verify DAG task dependencies
   - Add pipeline order tests
   - Update documentation

## Success Criteria

- All orphaned rankings identified and analyzed
- Cleanup script safely removes orphaned rankings with full audit trail
- Ranker service validates jobs before creating rankings
- DAG task order ensures no new orphaned rankings from timing issues
- No new orphaned rankings created after implementation

## Maintenance

- Run analysis script periodically (e.g., monthly) to monitor for new orphaned rankings
- Review cleanup audit table to identify patterns
- Monitor ranker service logs for validation warnings
- Update strategy document as new root causes are identified

