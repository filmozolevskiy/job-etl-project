# Campaign ID Uniqueness Fix

## Problem
Campaign IDs were not guaranteed to be unique, and when campaigns were deleted, their related data (jobs, rankings) remained orphaned. This caused issues where:
- Deleted campaign IDs could be reused
- Old jobs from deleted campaigns appeared in newly created campaigns with the same ID
- No cascade deletion of related data

## Solution

### 1. Database Schema Changes
- Changed `campaign_id` from `integer` to `SERIAL PRIMARY KEY` in `job_campaigns` table
- Added foreign key constraints with `ON DELETE CASCADE` for:
  - `marts.dim_ranking` → `marts.job_campaigns(campaign_id)`
  - `marts.etl_run_metrics` → `marts.job_campaigns(campaign_id)`
- Manual cleanup implemented for `marts.fact_jobs` (dbt table, no FK constraint)

### 2. ID Generation
- Changed from `MAX(campaign_id) + 1` (not thread-safe) to sequence-based generation
- Sequence: `marts.job_campaigns_campaign_id_seq`
- Falls back to old method if sequence doesn't exist (backwards compatibility)

### 3. Campaign Deletion
- Implemented comprehensive cleanup in `delete_campaign()` method:
  - Deletes `marts.fact_jobs` for the campaign
  - Deletes `staging.jsearch_job_postings` for the campaign
  - Deletes `staging.chatgpt_enrichments` for the campaign's jobs
  - Deletes `raw.jsearch_job_postings` for the campaign
  - Deletes campaign (triggers CASCADE DELETE for rankings and metrics)

### 4. Job Queries
- Updated queries to join with `marts.job_campaigns` to ensure campaign exists
- Prevents displaying jobs for deleted campaigns

## Migration

The migration script `docker/init/99_fix_campaign_id_uniqueness.sql` is automatically run during test setup (via `tests/integration/conftest.py`) and will be run when Docker containers are initialized.

**To run manually:**
```bash
# For test database
PGPASSWORD=postgres psql -h localhost -U postgres -d job_search_test -f docker/init/99_fix_campaign_id_uniqueness.sql

# For production database
PGPASSWORD=postgres psql -h localhost -U postgres -d job_search_db -f docker/init/99_fix_campaign_id_uniqueness.sql
```

**What the migration does:**
1. Cleans up existing orphaned data (handles missing tables gracefully)
2. Creates sequence if it doesn't exist
3. Adds PRIMARY KEY constraint to `campaign_id`
4. Sets default value for `campaign_id` to use sequence
5. Adds foreign key constraints with CASCADE DELETE for:
   - `marts.dim_ranking` → `marts.job_campaigns(campaign_id)`
   - `marts.etl_run_metrics` → `marts.job_campaigns(campaign_id)`
   - `marts.fact_jobs` → `marts.job_campaigns(campaign_id)` (if table exists)

**Note:** The migration script is idempotent and safe to run multiple times. It handles missing tables (like `fact_jobs` which is created by dbt) gracefully.

## Files Changed
- `docker/init/02_create_tables.sql` - Updated table definitions (campaign_id is SERIAL PRIMARY KEY)
- `docker/init/99_fix_campaign_id_uniqueness.sql` - Migration script
- `tests/integration/conftest.py` - Added migration script to test setup
- `services/campaign_management/campaign_service.py` - Updated deletion (savepoints for error handling) and ID generation
- `services/campaign_management/queries.py` - Updated queries
- `services/jobs/queries.py` - Added campaign existence checks (INNER JOIN)
- `tests/integration/test_campaign_deletion.py` - Comprehensive integration tests

## Testing

Integration tests are available in `tests/integration/test_campaign_deletion.py`:

**To run tests:**
```bash
# Run all campaign deletion tests
pytest tests/integration/test_campaign_deletion.py -v

# Run specific test class
pytest tests/integration/test_campaign_deletion.py::TestCampaignUniqueness -v
pytest tests/integration/test_campaign_deletion.py::TestCampaignDeletion -v
```

**Tests verify:**
1. Campaign IDs are unique and increment properly
2. PRIMARY KEY constraint prevents duplicate IDs
3. Deleting a campaign removes all related data (rankings, fact_jobs, staging jobs, ETL metrics)
4. New campaigns don't show old jobs from deleted campaigns
5. Job queries only return jobs for existing campaigns

**Manual verification after migration:**
1. Verify campaign IDs are unique
2. Create and delete a campaign - verify all related data is removed
3. Create a new campaign - verify it doesn't show old jobs
4. Verify job queries only return jobs for existing campaigns
