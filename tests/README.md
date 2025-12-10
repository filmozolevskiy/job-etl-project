# Testing Guide

This directory contains tests for the Job Search Platform.

## Test Structure

- `test_company_extractor.py` - Unit tests for company extractor service
- `test_fact_jobs_schema.py` - Schema validation tests (placeholder)

## Running Tests

### Prerequisites

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up test environment variables (create `.env.test`):
   ```bash
   DB_CONNECTION_STRING=postgresql://postgres:postgres@localhost:5432/job_search_test
   GLASSDOOR_API_KEY=test_key
   JSEARCH_API_KEY=test_key
   ```

### Unit Tests

Run all unit tests:
```bash
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ --cov=services --cov-report=html --cov-report=term-missing
```

Run specific test file:
```bash
pytest tests/test_company_extractor.py -v
```

### Integration Tests

Integration tests require a running PostgreSQL database. Use Docker:

```bash
# Start test database
docker-compose up -d postgres

# Run integration tests
pytest tests/ -m integration -v
```

### dbt Model Tests

Test dbt models:
```bash
cd dbt
dbt test
```

Test specific model:
```bash
cd dbt
dbt test --select fact_jobs
```

## Test Categories

- **Unit Tests** (`@pytest.mark.unit`): Fast, isolated tests
- **Integration Tests** (`@pytest.mark.integration`): Tests requiring database
- **Slow Tests** (`@pytest.mark.slow`): Long-running tests

## Manual Testing Checklist

### 1. Test Fuzzy Matching
- [ ] Test with single API result
- [ ] Test with multiple API results
- [ ] Test with no matching results
- [ ] Verify similarity threshold (0.85) works correctly

### 2. Test SQL Injection Prevention
- [ ] Verify parameterized queries are used
- [ ] Test with invalid limit values
- [ ] Verify error messages are clear

### 3. Test Existing Company Check
- [ ] Verify companies in staging.glassdoor_companies are excluded
- [ ] Verify companies in queue with success/not_found are excluded
- [ ] Test query performance with large datasets

### 4. Test fact_jobs Model
- [ ] Run dbt model: `dbt run --select fact_jobs`
- [ ] Verify employer_name is NOT in output
- [ ] Verify company_key IS in output
- [ ] Run dbt tests: `dbt test --select fact_jobs`

### 5. Test Airflow DAG
- [ ] Verify DAG loads without errors
- [ ] Verify task dependencies are correct
- [ ] Verify enricher task can run parallel to normalize_companies

## Continuous Integration

Tests should be run in CI/CD pipeline:
1. Unit tests (fast)
2. Linting (ruff)
3. dbt tests
4. Integration tests (if database available)

