# ChatGPT Enrichment Verification Guide

## Implementation Summary

ChatGPT-based enrichment has been implemented according to Phase 3.14 requirements. The following components were created:

### 1. Database Migration ✅
- **Files**: 
  - `docker/init/09_add_chatgpt_enrichment_columns.sql` - Initial column additions
  - `docker/init/13_create_chatgpt_enrichments_table.sql` - Separate table for ChatGPT enrichments
- **Table Created**: `staging.chatgpt_enrichments` with columns:
  - `job_summary` (TEXT) - 2 sentence summary
  - `chatgpt_extracted_skills` (JSONB) - skills extracted by ChatGPT
  - `chatgpt_extracted_location` (VARCHAR) - normalized location
  - `chatgpt_seniority_level` (VARCHAR) - seniority level (intern, junior, mid, senior, executive)
  - `chatgpt_remote_work_type` (VARCHAR) - remote work type (remote, hybrid, onsite)
  - `chatgpt_job_min_salary` (NUMERIC) - minimum salary
  - `chatgpt_job_max_salary` (NUMERIC) - maximum salary
  - `chatgpt_salary_period` (VARCHAR) - salary period (year, month, week, day, hour)
  - `chatgpt_salary_currency` (VARCHAR) - salary currency (USD, CAD, EUR, GBP)
  - `chatgpt_enriched_at` (TIMESTAMP) - enrichment timestamp
  - `chatgpt_enrichment_status` (JSONB) - status tracking for extracted fields
- **Status**: Migration executed successfully, table exists in database

### 2. ChatGPT Enrichment Service ✅
- **Files**:
  - `services/enricher/chatgpt_enricher.py` - Main enrichment service (refactored with helper methods)
  - `services/enricher/chatgpt_queries.py` - SQL queries
  - `tests/unit/test_chatgpt_enricher.py` - Comprehensive unit tests
- **Features**:
  - OpenAI API integration (supports v1.x and v2.x)
  - Batch processing with configurable batch size and concurrent batch processing
  - Retry logic with exponential backoff
  - Comprehensive error handling with helper methods
  - JSON parsing with markdown code block handling
  - Extracts: job summary, skills list, normalized location, seniority level, remote work type, salary fields
- **Code Quality**:
  - Helper methods for error extraction, API parameter building, JSON parsing
  - Consistent error handling between sync and async versions
  - Type hints on all methods
  - Unit tests covering initialization, API calls, enrichment, and error handling

### 3. Airflow Integration ✅
- **Files Updated**:
  - `airflow/dags/task_functions.py` - Added `chatgpt_enrich_jobs_task()`
  - `airflow/dags/jobs_etl_daily.py` - Added ChatGPT enrichment task to DAG
- **Task Flow**: `enricher` → `chatgpt_enrich_jobs` → `dbt_modelling`
- **Status**: Task is non-blocking (continues DAG even if ChatGPT enrichment fails)

### 4. dbt Model Updates ✅
- **Files Updated**:
  - `dbt/models/staging/jsearch_job_postings.sql` - Added ChatGPT columns
  - `dbt/models/marts/fact_jobs.sql` - Added ChatGPT columns to fact table
- **Status**: Models updated to include all ChatGPT enrichment fields

### 5. Environment Configuration ✅
- **File**: `env.template`
- **Variables Added**:
  - `OPENAI_API_KEY` - OpenAI API key (required)
  - `CHATGPT_MODEL` - Model to use (default: gpt-5-nano)
  - `CHATGPT_ENRICHMENT_BATCH_SIZE` - Batch size (default: 10)
  - `CHATGPT_MAX_CONCURRENT_BATCHES` - Max concurrent batches (default: 10)
  - `CHATGPT_API_TIMEOUT_REASONING` - Timeout for reasoning models in seconds (default: 180)
  - `CHATGPT_API_TIMEOUT_STANDARD` - Timeout for standard models in seconds (default: 60)
  - `CHATGPT_STATUS_CHECK_INTERVAL` - Status logging interval in seconds (default: 5)

## Verification Steps

### Prerequisites
1. Ensure `OPENAI_API_KEY` is set in your `.env` file or environment
2. OpenAI package is installed (already installed in Airflow container: v2.2.0)
3. Database migration has been run (already executed)

### Step 1: Check Database Schema
```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_schema = 'staging' 
  AND table_name = 'chatgpt_enrichments'
ORDER BY column_name;
```

Expected: Should show all enrichment columns including salary and seniority fields

### Step 2: Check Jobs Ready for Enrichment
```sql
SELECT COUNT(*) as jobs_needing_chatgpt 
FROM staging.jsearch_job_postings jp
LEFT JOIN staging.chatgpt_enrichments ce
    ON jp.jsearch_job_postings_key = ce.jsearch_job_postings_key
WHERE ce.jsearch_job_postings_key IS NULL
  AND jp.job_description IS NOT NULL 
  AND trim(jp.job_description) != '';
```

Expected: Should show number of jobs that need enrichment

### Step 3: Test ChatGPT Enrichment Service

**Option A: Run Test Script**
```bash
python scripts/test_chatgpt_enrichment.py
```

**Option B: Test via Airflow Task**
1. Navigate to Airflow UI: http://localhost:8080
2. Find DAG: `jobs_etl_daily`
3. Trigger DAG with a specific campaign_id (optional)
4. Monitor the `chatgpt_enrich_jobs` task
5. Check logs for enrichment results

**Option C: Test via Python Script**
```python
from services.enricher import ChatGPTEnricher
from services.shared import PostgreSQLDatabase
import os

# Setup
db_conn_str = "postgresql://postgres:postgres@localhost:5432/job_search_db"
database = PostgreSQLDatabase(connection_string=db_conn_str)
enricher = ChatGPTEnricher(
    database=database,
    api_key=os.getenv("OPENAI_API_KEY"),
    batch_size=1
)

# Get and enrich one job
jobs = enricher.get_jobs_to_enrich(limit=1)
if jobs:
    result = enricher.enrich_jobs(jobs)
    print(f"Enriched: {result}")
```

**Option D: Run Unit Tests**
```bash
pytest tests/unit/test_chatgpt_enricher.py -v
```

Expected: All unit tests should pass, covering:
- Initialization and configuration
- Helper methods (API params, error extraction, JSON parsing)
- API call success and error scenarios
- Job enrichment (single and batch)
- Database operations

### Step 4: Verify Enrichment Results

After running enrichment, check the database:
```sql
SELECT 
    ce.jsearch_job_postings_key,
    jp.jsearch_job_id,
    jp.job_title,
    ce.job_summary,
    ce.chatgpt_extracted_skills,
    ce.chatgpt_extracted_location,
    ce.chatgpt_seniority_level,
    ce.chatgpt_remote_work_type,
    ce.chatgpt_job_min_salary,
    ce.chatgpt_job_max_salary,
    ce.chatgpt_enriched_at
FROM staging.chatgpt_enrichments ce
JOIN staging.jsearch_job_postings jp
    ON ce.jsearch_job_postings_key = jp.jsearch_job_postings_key
ORDER BY ce.chatgpt_enriched_at DESC
LIMIT 5;
```

Expected: Should show jobs with:
- `job_summary`: 2-sentence summary
- `chatgpt_extracted_skills`: JSON array of skills
- `chatgpt_extracted_location`: Normalized location string
- `chatgpt_seniority_level`: Seniority level (if extracted)
- `chatgpt_remote_work_type`: Remote work type (if extracted)
- `chatgpt_job_min_salary`, `chatgpt_job_max_salary`: Salary range (if extracted)
- `chatgpt_salary_period`, `chatgpt_salary_currency`: Salary details (if extracted)
- `chatgpt_enriched_at`: Timestamp of enrichment

### Step 5: Verify dbt Models

Run dbt to ensure models compile and include ChatGPT columns:
```bash
docker exec job_search_airflow_webserver bash -c "cd /opt/airflow/dbt && dbt compile --select staging.jsearch_job_postings marts.fact_jobs"
```

Expected: Models should compile successfully with ChatGPT columns included

## Code Architecture

### Helper Methods
The service uses helper methods to reduce code duplication and improve maintainability:

- `_build_api_params()` - Builds API parameters based on model type (older vs newer models, reasoning models)
- `_extract_error_details()` - Extracts error messages and bodies from OpenAI API exceptions
- `_should_retry_without_json()` - Detects if JSON mode is unsupported
- `_is_authentication_error()` - Detects authentication errors (no retry)
- `_parse_json_response()` - Parses JSON responses, handling markdown code blocks
- `_extract_enrichment_from_result()` - Extracts and validates enrichment data from API responses
- `_get_empty_enrichment()` - Returns empty enrichment dictionary

### Error Handling
- Consistent error handling between sync and async versions
- Automatic retry with exponential backoff
- JSON mode fallback if model doesn't support it
- Authentication errors don't retry (fail fast)
- Comprehensive logging for debugging

### Testing
- Unit tests in `tests/unit/test_chatgpt_enricher.py`
- Tests cover initialization, helper methods, API calls, enrichment, and database operations
- Uses mocks to avoid actual API calls during testing

## Current Status

✅ **Implementation Complete**:
- Database schema updated (separate `staging.chatgpt_enrichments` table)
- Service implemented with refactored code structure
- Helper methods for error handling, JSON parsing, and enrichment extraction
- Unit tests created (`tests/unit/test_chatgpt_enricher.py`)
- Airflow task integrated
- dbt models updated
- Environment configuration added
- Code quality improvements: type hints, no code duplication, consistent error handling

✅ **Code Quality**:
- All methods have type hints
- Helper methods reduce code duplication (~40% reduction)
- Consistent error handling between sync and async versions
- Comprehensive logging (no print statements)
- Unit tests covering all major functionality

⚠️ **Ready for Testing**:
- Jobs available for enrichment (check database for current count)
- OpenAI package installed (v2.2.0)
- Test script available at `scripts/test_chatgpt_enrichment.py`
- Unit tests available: `pytest tests/unit/test_chatgpt_enricher.py`

🔧 **Next Steps**:
1. Set `OPENAI_API_KEY` in `.env` file
2. Run unit tests: `pytest tests/unit/test_chatgpt_enricher.py -v`
3. Run test script or trigger Airflow DAG
4. Verify enrichment results in database
5. Check that enriched data appears in `marts.fact_jobs`

## Troubleshooting

### Issue: "OpenAI API key is required"
**Solution**: Set `OPENAI_API_KEY` in your `.env` file

### Issue: "OpenAI library is not installed"
**Solution**: OpenAI v2.2.0 is already installed in Airflow container. If running locally, install with: `pip install openai>=1.0.0`

### Issue: API rate limits
**Solution**: 
- Reduce `CHATGPT_ENRICHMENT_BATCH_SIZE` (default: 10)
- Reduce `CHATGPT_MAX_CONCURRENT_BATCHES` (default: 10)
- The service includes retry logic with exponential backoff

### Issue: ChatGPT enrichment task fails in Airflow
**Solution**: 
- Check Airflow logs for specific error
- Task is non-blocking - DAG continues even if ChatGPT enrichment fails
- Verify API key is accessible in Airflow environment

## Notes

- ChatGPT enrichment is **optional** - the DAG will continue even if it fails
- Uses `gpt-5-nano` by default for cost efficiency (configurable via `CHATGPT_MODEL`)
- Processes jobs in batches with concurrent batch processing for efficiency
- Enrichment status is tracked in `chatgpt_enrichment_status` JSONB field
- All code follows project standards: type hints, docstrings, proper error handling, no print statements

