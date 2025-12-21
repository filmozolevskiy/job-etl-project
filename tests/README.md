# Testing Guide

This directory contains tests for the Job Search Platform, organized into unit tests and integration tests.

## Test Structure

```
tests/
├── conftest.py                    # Root pytest configuration (shared setup)
├── unit/                          # Unit tests (fast, isolated)
│   ├── __init__.py
│   ├── conftest.py               # Unit test fixtures
│   └── test_company_extractor.py # Unit tests for company extractor service
└── integration/                   # Integration tests (require database)
    ├── __init__.py
    ├── conftest.py               # Integration test fixtures (database setup, etc.)
    ├── test_extract_normalize_rank.py  # Extract → normalize → rank flow tests
    └── test_company_enrichment.py      # Company enrichment flow tests
```

### Unit Tests (`tests/unit/`)

Fast, isolated tests that don't require external dependencies. These tests use mocks and stubs.

- **`test_company_extractor.py`** - Unit tests for company extractor service
  - Fuzzy matching tests
  - SQL injection prevention tests
  - Existing company check tests

### Integration Tests (`tests/integration/`)

Tests that require external dependencies (database, dbt). These tests validate data flows through all layers.

- **`test_extract_normalize_rank.py`** - Integration tests for extract → normalize → rank flow
  - Job extraction to raw layer
  - Normalization via dbt staging models
  - Building marts (fact_jobs)
  - Job ranking and writing to dim_ranking
  - End-to-end data flow validation

- **`test_company_enrichment.py`** - Integration tests for company enrichment flow
  - Company identification from job postings
  - Company extraction to raw layer
  - Company normalization via dbt staging models
  - Building marts (dim_companies)
  - Enrichment queue tracking
  - End-to-end data flow validation

## Running Tests

### Prerequisites

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. For integration tests, set up test environment variables (create `.env.test` or export):
   ```bash
   TEST_DB_CONNECTION_STRING=postgresql://postgres:postgres@localhost:5432/job_search_test
   GLASSDOOR_API_KEY=test_key
   JSEARCH_API_KEY=test_key
   ```

### Unit Tests

Run all unit tests:
```bash
pytest tests/unit/ -v
```

Run with coverage:
```bash
pytest tests/unit/ --cov=services --cov-report=html --cov-report=term-missing
```

Run specific test file:
```bash
pytest tests/unit/test_company_extractor.py -v
```

### Integration Tests

Integration tests require a running PostgreSQL database. Use Docker:

```bash
# Start test database
docker-compose up -d postgres

# Run all integration tests
pytest tests/integration/ -v

# Or use the marker
pytest tests/ -m integration -v
```

**Integration Test Requirements:**
1. PostgreSQL database running (use `docker-compose up -d postgres`)
2. Test database connection string set via `TEST_DB_CONNECTION_STRING` environment variable
   - Default: `postgresql://postgres:postgres@localhost:5432/job_search_test`
3. dbt configured and available in PATH
4. dbt profiles.yml configured to connect to test database

**Note:** Integration tests use mocked API clients (JSearch, Glassdoor) to avoid making real API calls during testing. The tests validate the data flow through all layers (raw → staging → marts) using sample payload data.

### Running All Tests

Run both unit and integration tests:
```bash
pytest tests/ -v
```

Run only unit tests (fast):
```bash
pytest tests/unit/ -v
```

Run only integration tests:
```bash
pytest tests/integration/ -v
```

### dbt Model Tests

Test dbt models separately:
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

Tests are automatically categorized by directory:

- **Unit Tests** (`tests/unit/`): Fast, isolated tests using mocks
- **Integration Tests** (`tests/integration/`, `@pytest.mark.integration`): Tests requiring database and external dependencies

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
1. Unit tests (fast) - `pytest tests/unit/`
2. Linting (ruff)
3. dbt tests
4. Integration tests (if database available) - `pytest tests/integration/`

## Adding New Tests

When adding new tests:

1. **Unit tests** → Add to `tests/unit/`
   - Use mocks for external dependencies
   - Should be fast (< 1 second per test)
   - Can use fixtures from `tests/unit/conftest.py`

2. **Integration tests** → Add to `tests/integration/`
   - Mark with `@pytest.mark.integration`
   - Can use fixtures from `tests/integration/conftest.py`
   - Require database setup (handled by `test_database` fixture)

Fixtures are automatically discovered by pytest from the appropriate `conftest.py` file in each directory.