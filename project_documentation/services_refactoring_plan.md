# Services Refactoring Plan

**Status:** In Progress - Core Services Completed  
**Target Date:** After all services are ready  
**Priority:** High (Improves maintainability, testability, and code quality)  
**Last Updated:** 2025-01-17

---

## Table of Contents

1. [Overview](#overview)
2. [Goals and Benefits](#goals-and-benefits)
3. [Current State Analysis](#current-state-analysis)
4. [Refactoring Areas](#refactoring-areas)
5. [Implementation Strategy](#implementation-strategy)
6. [Migration Guide](#migration-guide)
7. [Testing Strategy](#testing-strategy)
8. [Examples](#examples)

---

## Overview

This document outlines a comprehensive refactoring plan for the services layer of the Job Search Platform. The refactoring aims to improve code maintainability, testability, and adherence to Python best practices while maintaining backward compatibility during the transition.

### Scope

Services refactoring status:
- ✅ `services/extractor/job_extractor.py` - **COMPLETED**
- ✅ `services/extractor/company_extractor.py` - **COMPLETED**
- ✅ `services/ranker/job_ranker.py` - **COMPLETED**
- ⏳ `services/notifier/notification_coordinator.py` - **PENDING** (still uses old pattern)
- Future services (enricher)

---

## Goals and Benefits

### Primary Goals

1. **Separation of Concerns**: Separate business logic from execution code
2. **Dependency Injection**: Make services testable and flexible
3. **SQL Management**: Extract SQL queries for better maintainability
4. **Improved Testing**: Enable comprehensive unit and integration testing
5. **Code Reusability**: Make services easier to use in different contexts

### Benefits

- **Testability**: Easy to mock dependencies and test in isolation
- **Maintainability**: Clear separation makes code easier to understand and modify
- **Flexibility**: Services can be used in API or scheduled contexts (e.g., Airflow)
- **Quality**: Better error handling and type safety
- **Performance**: Connection pooling and resource management improvements

---

## Current State Analysis

### Current Structure

```
services/
├── extractor/
│   ├── __init__.py
│   ├── base_client.py
│   ├── company_extractor.py  (contains class)
│   ├── job_extractor.py      (contains class)
│   ├── glassdoor_client.py
│   └── jsearch_client.py
└── ranker/
    ├── __init__.py
    └── job_ranker.py         (contains class)
```

### Current Issues

1. **Mixed Responsibilities**: Service classes may contain execution code mixed with business logic
2. **Tight Coupling**: Direct dependency on environment variables and hard-coded dependency creation
3. **Embedded SQL**: SQL queries embedded as strings in methods
4. **Manual Resource Management**: Manual connection handling with try/finally blocks
5. **Hard to Test**: Difficult to mock dependencies and test in isolation
6. **Code Duplication**: Similar database connection patterns repeated across methods

---

## Refactoring Areas

### 1. Separation of Concerns

**Current Problem:**
- Service classes may contain execution code (e.g., `main()` functions) mixed with business logic
- When imported by Airflow or other systems, execution code is still present (even if unused)

**Solution:**
- Remove any `main()` functions or execution code from service classes
- Keep service classes focused solely on business logic
- Services are used directly by Airflow tasks or other orchestration systems

**Target Structure:**
```
services/
├── extractor/
│   ├── __init__.py              # Exports service classes
│   ├── company_extractor.py     # Only CompanyExtractor class
│   ├── job_extractor.py         # Only JobExtractor class
│   └── ...
└── ranker/
    ├── __init__.py              # Exports JobRanker class
    ├── job_ranker.py            # Only JobRanker class
    └── ...
```

---

### 2. Dependency Injection

**Current Problem:**
- Services create their own dependencies (API clients, database connections)
- Hard dependency on environment variables
- Difficult to test with mocks

**Solution:**
- Inject dependencies through constructor parameters
- Enable easy mocking in tests
- Services are instantiated directly by consumers (e.g., Airflow tasks) with dependencies

**Pattern:**
```python
# Service class - accepts dependencies
class CompanyExtractor:
    def __init__(self, database: Database, glassdoor_client: GlassdoorClient):
        self.db = database
        self.client = glassdoor_client

# Usage in Airflow or other consumers
database = PostgreSQLDatabase(connection_string=db_conn_str)
client = GlassdoorClient(api_key=api_key)
extractor = CompanyExtractor(database=database, glassdoor_client=client)
```

---

### 3. SQL Query Management

**Current Problem:**
- SQL queries embedded as string literals in methods
- Hard to review, maintain, and reuse
- No syntax highlighting or validation

**Solution:**
- Extract SQL queries to separate modules or files
- Organize queries by service or domain

**Options:**
1. **Constants Module** (Recommended for small/medium queries): `services/ranker/queries.py`
2. **SQL Files** (Better for large/complex queries): `services/ranker/queries/*.sql`

---

### 4. Database Connection Management

**Current Problem:**
- Manual connection creation and cleanup with try/finally
- No connection pooling
- Repetitive patterns across methods

**Solution:**
- Use connection context managers
- Abstract database access through a protocol/interface
- Enable connection pooling for production

---

### 5. Configuration Management

**Current Problem:**
- `load_dotenv()` called in every service file
- Scattered `os.getenv()` calls throughout code
- No centralized configuration

**Solution:**
- Create a centralized configuration module
- Load environment variables once at application startup
- Provide type-safe configuration access

---

### 6. Improved Error Handling

**Current Problem:**
- Generic exception handling
- Bare `except:` clauses in some places
- Inconsistent error messages

**Solution:**
- Use specific exception types
- Create custom exception classes for domain errors
- Consistent error handling patterns

---

## Implementation Strategy

### Phase 1: Foundation (Infrastructure)

1. **Create Database Abstraction**
   - Implement `Database` protocol/interface
   - Create `PostgreSQLDatabase` implementation
   - Add connection pooling support

2. **Create Configuration Module**
   - Centralize environment variable loading
   - Type-safe configuration classes

3. **Extract SQL Queries**
   - Create query modules/files for each service
   - Update services to use extracted queries

### Phase 2: Service Refactoring

For each service (in order of priority):

1. **Remove Execution Code**
   - Remove any `main()` functions from service classes
   - Keep service classes focused on business logic only

2. **Implement Dependency Injection**
   - Update `__init__` to accept dependencies
   - Create factory function for production use
   - Update existing usage (Airflow, etc.)

3. **Update Database Access**
   - Use database abstraction instead of direct `psycopg2.connect`
   - Use connection context managers

### Phase 3: Testing Infrastructure

1. **Update Test Utilities**
   - Create mock database implementations
   - Create test fixtures and helpers
   - Update existing tests

2. **Add New Tests**
   - Unit tests with mocks
   - Integration tests with test database

### Phase 4: Documentation and Cleanup

1. **Update Documentation**
   - Update README files
   - Add usage examples
   - Document new patterns

2. **Code Cleanup**
   - Remove deprecated code
   - Update type hints
   - Code review and optimization

---

## Migration Guide

### Step-by-Step Migration for a Single Service

Using `CompanyExtractor` as an example (and then applying the same pattern to other services):

#### Step 1: Extract SQL Queries

**Before:**
```python
# services/extractor/company_extractor.py
def get_companies_to_enrich(self, limit: Optional[int] = None) -> List[str]:
    conn = psycopg2.connect(self.db_connection_string)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT 
                    lower(trim(employer_name)) as company_lookup_key
                FROM staging.jsearch_job_postings
                WHERE employer_name IS NOT NULL 
                    AND trim(employer_name) != ''
                    ...
            """)
```

**After:**
```python
# services/extractor/queries.py
GET_COMPANIES_TO_ENRICH = """
    SELECT DISTINCT 
        lower(trim(employer_name)) as company_lookup_key
    FROM staging.jsearch_job_postings
    WHERE employer_name IS NOT NULL 
        AND trim(employer_name) != ''
        ...
"""

# services/extractor/company_extractor.py
from .queries import GET_COMPANIES_TO_ENRICH

def get_companies_to_enrich(self, limit: Optional[int] = None) -> List[str]:
    with self.db.get_cursor() as cur:
        cur.execute(GET_COMPANIES_TO_ENRICH)
```

#### Step 2: Create Database Abstraction

**Create:**
```python
# services/extractor/database.py
from typing import Protocol
from contextlib import contextmanager
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

class Database(Protocol):
    @contextmanager
    def get_cursor(self):
        """Get a database cursor as a context manager."""
        ...

class PostgreSQLDatabase:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    @contextmanager
    def get_cursor(self):
        with psycopg2.connect(self.connection_string) as conn:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                yield cur
```

#### Step 3: Update Service Class

**Before:**
```python
# services/extractor/company_extractor.py
class CompanyExtractor:
    def __init__(
        self,
        db_connection_string: Optional[str] = None,
        glassdoor_api_key: Optional[str] = None
    ):
        self.db_connection_string = db_connection_string or os.getenv('DB_CONNECTION_STRING')
        self.glassdoor_api_key = glassdoor_api_key or os.getenv('GLASSDOOR_API_KEY')
        self.client = GlassdoorClient(api_key=self.glassdoor_api_key)
```

**After:**
```python
# services/extractor/company_extractor.py
from shared.database import Database
from .glassdoor_client import GlassdoorClient

class CompanyExtractor:
    def __init__(
        self,
        database: Database,
        glassdoor_client: GlassdoorClient
    ):
        if not database:
            raise ValueError("Database is required")
        if not glassdoor_client:
            raise ValueError("GlassdoorClient is required")
        
        self.db = database
        self.client = glassdoor_client
```

#### Step 4: Remove Execution Code

**Update service file:**
```python
# services/extractor/company_extractor.py
# Remove any main() functions or if __name__ == "__main__" blocks
# Keep only the service class and its methods
```

#### Step 5: Update Existing Usage

**Airflow (task_functions.py):**
```python
from extractor.company_extractor import CompanyExtractor
from shared.database import PostgreSQLDatabase
from extractor.glassdoor_client import GlassdoorClient

def extract_companies_task(**context):
    # Build dependencies
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    glassdoor_client = GlassdoorClient(api_key=glassdoor_api_key)
    
    # Create service with injected dependencies
    extractor = CompanyExtractor(
        database=database,
        glassdoor_client=glassdoor_client
    )
    
    # Use service
    results = extractor.extract_all_companies()
```

---

### Step-by-Step Plan for Other Services

The same refactoring pattern used for `CompanyExtractor` should be applied to the other core services:

- `services/extractor/job_extractor.py`
- `services/ranker/job_ranker.py`
- `services/notifier/notification_coordinator.py`

Each section below mirrors the CompanyExtractor steps: extract SQL, use the shared `Database` protocol, inject dependencies, remove execution code, and update Airflow usage.

---

### JobExtractor Refactoring Plan

#### Step 1: Extract SQL Queries

**Before:**
```python
# services/extractor/job_extractor.py
def get_active_profiles(self) -> List[Dict[str, Any]]:
    conn = psycopg2.connect(self.db_connection_string)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    profile_id,
                    profile_name,
                    query,
                    location,
                    country,
                    skills,
                    min_salary,
                    max_salary,
                    remote_preference,
                    seniority
                FROM marts.profile_preferences
                WHERE is_active = true
                ORDER BY profile_id
            """)
            ...
    finally:
        conn.close()
```

**After:**
```python
# services/extractor/queries.py
GET_ACTIVE_PROFILES_FOR_JOBS = """
    SELECT 
        profile_id,
        profile_name,
        query,
        location,
        country,
        skills,
        min_salary,
        max_salary,
        remote_preference,
        seniority
    FROM marts.profile_preferences
    WHERE is_active = true
    ORDER BY profile_id
"""

# services/extractor/job_extractor.py
from .queries import GET_ACTIVE_PROFILES_FOR_JOBS

def get_active_profiles(self) -> List[Dict[str, Any]]:
    with self.db.get_cursor() as cur:
        cur.execute(GET_ACTIVE_PROFILES_FOR_JOBS)
        columns = [desc[0] for desc in cur.description]
        profiles = [dict(zip(columns, row)) for row in cur.fetchall()]
        ...
```

Repeat this pattern for other SQL in `JobExtractor` (inserts into `raw.jsearch_job_postings`, etc.), moving the SQL into `queries.py` and using `self.db.get_cursor()`.

#### Step 2: Use the Shared Database Abstraction

Reuse the existing `Database` protocol and `PostgreSQLDatabase` implementation (either from `services/extractor/database.py` or a shared `services/database.py` once created).

```python
# services/extractor/job_extractor.py
from .database import Database  # or from services.database import Database
from .jsearch_client import JSearchClient

class JobExtractor:
    def __init__(
        self,
        database: Database,
        jsearch_client: JSearchClient,
        num_pages: int,
    ):
        if not database:
            raise ValueError("Database is required")
        if not jsearch_client:
            raise ValueError("JSearchClient is required")

        self.db = database
        self.client = jsearch_client
        self.num_pages = num_pages
```

All methods should use `self.db.get_cursor()` instead of `psycopg2.connect(self.db_connection_string)`.

#### Step 3: Move Configuration Out of the Service

Remove `load_dotenv()` and `os.getenv()` from `JobExtractor.__init__`. Instead:

- Pass `num_pages` as a constructor argument
- Create and inject `JSearchClient` from the caller (e.g., Airflow)

```python
# airflow/dags/task_functions.py
from extractor.job_extractor import JobExtractor
from shared.database import PostgreSQLDatabase
from extractor.jsearch_client import JSearchClient

def extract_job_postings_task(**context):
    db_conn_str = build_db_connection_string()
    jsearch_api_key = os.getenv("JSEARCH_API_KEY")
    num_pages = int(os.getenv("JSEARCH_NUM_PAGES", "5"))

    database = PostgreSQLDatabase(connection_string=db_conn_str)
    jsearch_client = JSearchClient(api_key=jsearch_api_key)

    extractor = JobExtractor(
        database=database,
        jsearch_client=jsearch_client,
        num_pages=num_pages,
    )

    results = extractor.extract_all_jobs()
    ...
```

#### Step 4: Remove Execution Code

If `JobExtractor` contains any `main()` or `if __name__ == "__main__"` blocks, remove them so the file contains only the service class and related helpers.

---

### JobRanker Refactoring Plan

#### Step 1: Extract SQL Queries

Move SQL from methods like `get_active_profiles`, `get_jobs_for_profile`, and ranking insert/update queries into a queries module, e.g. `services/ranker/queries.py`.

```python
# services/ranker/queries.py
GET_ACTIVE_PROFILES_FOR_RANKING = """
    SELECT 
        profile_id,
        profile_name,
        query,
        location,
        country,
        skills,
        min_salary,
        max_salary,
        remote_preference,
        seniority
    FROM marts.profile_preferences
    WHERE is_active = true
    ORDER BY profile_id
"""
```

Then, in `job_ranker.py`:

```python
from .queries import GET_ACTIVE_PROFILES_FOR_RANKING

def get_active_profiles(self) -> List[Dict[str, Any]]:
    with self.db.get_cursor() as cur:
        cur.execute(GET_ACTIVE_PROFILES_FOR_RANKING)
        columns = [desc[0] for desc in cur.description]
        profiles = [dict(zip(columns, row)) for row in cur.fetchall()]
        return profiles
```

#### Step 2: Introduce Database Protocol Usage

Update `JobRanker` to accept a `Database` instead of a raw connection string:

```python
# services/ranker/job_ranker.py
from services.shared.database import Database

class JobRanker:
    def __init__(self, database: Database):
        if not database:
            raise ValueError("Database is required")
        self.db = database
```

All methods that currently do:

```python
conn = psycopg2.connect(self.db_connection_string)
...
```

should be refactored to:

```python
with self.db.get_cursor() as cur:
    cur.execute(...)
    ...
```

#### Step 3: Update Airflow Usage

```python
# airflow/dags/task_functions.py
from ranker.job_ranker import JobRanker
from shared.database import PostgreSQLDatabase

def rank_jobs_task(**context):
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)

    ranker = JobRanker(database=database)
    results = ranker.rank_all_jobs()
    ...
```

#### Step 4: Remove Execution Code

Remove any `if __name__ == "__main__"` and `main()` blocks from `job_ranker.py`. The file should expose only the `JobRanker` class and helpers.

---

### NotificationCoordinator Refactoring Plan

#### Step 1: Extract SQL Queries

Create a `services/notifier/queries.py` module containing SQL for:

- Fetching active profiles with email
- Fetching top ranked jobs for a profile
- Any update/insert queries related to notifications (if present)

```python
# services/notifier/queries.py
GET_ACTIVE_PROFILES_WITH_EMAIL = """
    SELECT 
        profile_id,
        profile_name,
        email,
        query
    FROM marts.profile_preferences
    WHERE is_active = true
        AND email IS NOT NULL
        AND email != ''
    ORDER BY profile_id
"""
```

Then use these queries in `notification_coordinator.py` with `self.db.get_cursor()`.

#### Step 2: Introduce Database Protocol Usage

Update `NotificationCoordinator` to accept a `Database` instead of a raw connection string:

```python
# services/notifier/notification_coordinator.py
from services.shared.database import Database
from .base_notifier import BaseNotifier

class NotificationCoordinator:
    def __init__(
        self,
        notifier: BaseNotifier,
        database: Database,
        max_jobs_per_notification: int = 10,
    ):
        if not notifier:
            raise ValueError("Notifier is required")
        if not database:
            raise ValueError("Database is required")

        self.notifier = notifier
        self.db = database
        self.max_jobs_per_notification = max_jobs_per_notification
```

Methods like `get_active_profiles` and `get_top_ranked_jobs_for_profile` should use:

```python
with self.db.get_cursor() as cur:
    cur.execute(GET_ACTIVE_PROFILES_WITH_EMAIL)
    ...
```

#### Step 3: Update Airflow Usage

```python
# airflow/dags/task_functions.py
from notifier.email_notifier import EmailNotifier
from notifier.notification_coordinator import NotificationCoordinator
from shared.database import PostgreSQLDatabase

def send_notifications_task(**context):
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)

    email_notifier = EmailNotifier()
    coordinator = NotificationCoordinator(
        notifier=email_notifier,
        database=database,
    )

    results = coordinator.send_all_notifications()
    ...
```

#### Step 4: Remove Execution Code

Ensure `notification_coordinator.py` does not contain any `if __name__ == "__main__"` blocks; it should contain only the coordinator class and related helpers.

---

## Testing Strategy

### Unit Tests with Mocks

**Example Test:**
```python
# tests/test_company_extractor.py
import pytest
from unittest.mock import Mock, MagicMock
from services.extractor.company_extractor import CompanyExtractor
from services.extractor.glassdoor_client import GlassdoorClient

class MockDatabase:
    """Mock database for testing."""
    
    def __init__(self):
        self.cursor_mock = MagicMock()
        self.cursor_mock.description = [('company_lookup_key',)]
        self.cursor_mock.fetchall.return_value = [
            ('microsoft',),
            ('google',)
        ]
    
    def get_cursor(self):
        """Context manager returning mock cursor."""
        yield self.cursor_mock

def test_get_companies_to_enrich():
    """Test getting companies to enrich."""
    # Setup mocks
    mock_db = MockDatabase()
    mock_client = Mock(spec=GlassdoorClient)
    
    # Create service with injected dependencies
    extractor = CompanyExtractor(
        database=mock_db,
        glassdoor_client=mock_client
    )
    
    # Test
    companies = extractor.get_companies_to_enrich(limit=10)
    
    # Verify
    assert len(companies) == 2
    assert 'microsoft' in companies
    assert 'google' in companies
    
    # Verify database was called
    mock_db.cursor_mock.execute.assert_called_once()
```

### Integration Tests

**Example Integration Test:**
```python
# tests/integration/test_company_extractor_integration.py
import pytest
from services.extractor.company_extractor import CompanyExtractor
from services.shared.database import PostgreSQLDatabase
from services.extractor.glassdoor_client import GlassdoorClient

@pytest.fixture
def test_database():
    """Real test database connection."""
    return PostgreSQLDatabase("postgresql://test:test@localhost/test_db")

@pytest.fixture
def test_extractor(test_database):
    """Create extractor with test dependencies."""
    client = GlassdoorClient(api_key="test_key")
    return CompanyExtractor(database=test_database, glassdoor_client=client)

@pytest.mark.integration
def test_extract_company_integration(test_extractor, test_db_setup):
    """Integration test with real database."""
    # Requires test data setup
    result = test_extractor.extract_company("microsoft")
    
    assert result is not None
    # Verify data was written to database
```

---

## Examples

### Complete Refactored Service Example

Here's a complete example of how `CompanyExtractor` would look after refactoring:

#### Directory Structure
```
services/extractor/
├── __init__.py                 # Exports: CompanyExtractor
├── company_extractor.py        # Service class only
├── database.py                 # Database abstraction
├── queries.py                  # SQL queries
└── glassdoor_client.py         # (unchanged)
```

#### company_extractor.py
```python
"""
Company Extractor Service

Extracts company data from Glassdoor API and writes to raw.glassdoor_companies table.
"""

import logging
from typing import List, Dict, Any, Optional
from .database import Database
from .glassdoor_client import GlassdoorClient
from .queries import (
    GET_COMPANIES_TO_ENRICH,
    MARK_COMPANY_QUEUED,
    INSERT_COMPANY,
    UPDATE_ENRICHMENT_STATUS
)

logger = logging.getLogger(__name__)

class CompanyExtractor:
    """
    Service for extracting company data from Glassdoor API.
    
    Scans staging.jsearch_job_postings for employer names, identifies companies
    not yet enriched, and calls Glassdoor API to fetch company data.
    """
    
    def __init__(
        self,
        database: Database,
        glassdoor_client: GlassdoorClient
    ):
        """
        Initialize the company extractor.
        
        Args:
            database: Database connection interface
            glassdoor_client: Glassdoor API client
        """
        if not database:
            raise ValueError("Database is required")
        if not glassdoor_client:
            raise ValueError("GlassdoorClient is required")
        
        self.db = database
        self.client = glassdoor_client
    
    def get_companies_to_enrich(self, limit: Optional[int] = None) -> List[str]:
        """Get list of company lookup keys that need enrichment."""
        query = GET_COMPANIES_TO_ENRICH
        params = None
        
        if limit:
            if not isinstance(limit, int) or limit <= 0:
                raise ValueError(f"Limit must be a positive integer, got: {limit}")
            query += " LIMIT %s"
            params = (limit,)
        
        with self.db.get_cursor() as cur:
            cur.execute(query, params)
            companies = [row[0] for row in cur.fetchall()]
        
        logger.info(f"Found {len(companies)} companies needing enrichment")
        return companies
    
    def extract_all_companies(self, limit: Optional[int] = None) -> Dict[str, str]:
        """Extract companies for all companies needing enrichment."""
        companies = self.get_companies_to_enrich(limit=limit)
        results = {}
        
        for company_key in companies:
            try:
                self.mark_company_queued(company_key)
                company_data = self.extract_company(company_key)
                
                if company_data:
                    self._write_company_to_db(company_data, company_key)
                    self._mark_company_success(company_key)
                    results[company_key] = 'success'
                else:
                    self._mark_company_not_found(company_key)
                    results[company_key] = 'not_found'
            except Exception as e:
                logger.error(f"Error extracting company {company_key}: {e}")
                self._mark_company_error(company_key, str(e))
                results[company_key] = 'error'
        
        return results
    
    # ... rest of methods using self.db.get_cursor() ...
```

#### database.py
```python
"""Database abstraction layer."""

from typing import Protocol
from contextlib import contextmanager
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

class Database(Protocol):
    """Protocol for database operations."""
    
    @contextmanager
    def get_cursor(self):
        """Get a database cursor as a context manager."""
        ...

class PostgreSQLDatabase:
    """PostgreSQL implementation of Database protocol."""
    
    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL database connection.
        
        Args:
            connection_string: PostgreSQL connection string
        """
        if not connection_string:
            raise ValueError("Connection string is required")
        self.connection_string = connection_string
    
    @contextmanager
    def get_cursor(self):
        """
        Get a database cursor as a context manager.
        
        The connection is automatically closed when exiting the context.
        """
        with psycopg2.connect(self.connection_string) as conn:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                yield cur
```

#### queries.py
```python
"""SQL queries for Company Extractor service."""

GET_COMPANIES_TO_ENRICH = """
    SELECT DISTINCT 
        lower(trim(employer_name)) as company_lookup_key
    FROM staging.jsearch_job_postings
    WHERE employer_name IS NOT NULL 
        AND trim(employer_name) != ''
        AND lower(trim(employer_name)) NOT IN (
            SELECT DISTINCT company_lookup_key 
            FROM staging.glassdoor_companies
            WHERE company_lookup_key IS NOT NULL
        )
        AND lower(trim(employer_name)) NOT IN (
            SELECT company_lookup_key 
            FROM staging.company_enrichment_queue 
            WHERE enrichment_status IN ('success', 'not_found')
        )
    ORDER BY company_lookup_key
"""

MARK_COMPANY_QUEUED = """
    INSERT INTO staging.company_enrichment_queue (
        company_lookup_key,
        enrichment_status,
        queued_at
    ) VALUES (%s, 'queued', NOW())
    ON CONFLICT (company_lookup_key) DO NOTHING
"""

# ... more queries ...
```

#### __init__.py
```python
"""
Extractor Services Package

This package contains services for extracting data from external APIs.
"""

from .base_client import BaseAPIClient
from .jsearch_client import JSearchClient
from .glassdoor_client import GlassdoorClient
from .company_extractor import CompanyExtractor
from .job_extractor import JobExtractor

__all__ = [
    'BaseAPIClient',
    'JSearchClient',
    'GlassdoorClient',
    'CompanyExtractor',
    'JobExtractor',
]
```

### Usage Examples

#### In Airflow (Production)
```python
# airflow/dags/task_functions.py
from extractor.company_extractor import CompanyExtractor
from shared.database import PostgreSQLDatabase
from extractor.glassdoor_client import GlassdoorClient

def extract_companies_task(**context):
    """Airflow task to extract companies."""
    db_conn_str = build_db_connection_string()
    api_key = os.getenv('GLASSDOOR_API_KEY')
    
    # Build dependencies
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    glassdoor_client = GlassdoorClient(api_key=api_key)
    
    # Create service with injected dependencies
    extractor = CompanyExtractor(
        database=database,
        glassdoor_client=glassdoor_client
    )
    
    results = extractor.extract_all_companies()
    return results
```

#### In Tests
```python
# tests/test_company_extractor.py
from unittest.mock import Mock
from services.extractor.company_extractor import CompanyExtractor
from services.shared.database import Database
from services.extractor.glassdoor_client import GlassdoorClient

def test_extract_company_with_mocks():
    # Create mocks
    mock_db = Mock(spec=Database)
    mock_client = Mock(spec=GlassdoorClient)
    
    # Configure mocks
    mock_client.search_company.return_value = {
        "companies": [{"name": "Test Corp", "company_id": 123}]
    }
    
    # Create service with injected mocks
    extractor = CompanyExtractor(
        database=mock_db,
        glassdoor_client=mock_client
    )
    
    # Test
    result = extractor.extract_company("test corp")
    
    # Verify
    assert result is not None
    mock_client.search_company.assert_called_once()
```


---

## Implementation Checklist

### Pre-Refactoring
- [ ] Review all services and identify all SQL queries
- [ ] Document current usage in Airflow and other systems
- [ ] Create backup branch for rollback if needed
- [ ] Set up test database for integration tests

### Phase 1: Infrastructure
- [x] Create `services/shared/database.py` with Database protocol - **COMPLETED**
- [ ] Create `services/config.py` for centralized configuration (optional)
- [x] Extract all SQL queries to query modules/files - **COMPLETED**
  - `services/extractor/queries.py` - **COMPLETED**
  - `services/ranker/queries.py` - **COMPLETED**
- [x] Create database protocol/interface - **COMPLETED**

### Phase 2: Service Refactoring (per service)

#### ✅ JobExtractor - COMPLETED
- [x] Remove any `main()` functions from service classes
- [x] Update service `__init__` to accept dependencies
- [x] Update database access to use abstraction
- [x] Update `__init__.py` exports
- [x] Extract SQL queries to `queries.py`

#### ✅ CompanyExtractor - COMPLETED
- [x] Remove any `main()` functions from service classes
- [x] Update service `__init__` to accept dependencies
- [x] Update database access to use abstraction
- [x] Update `__init__.py` exports
- [x] Extract SQL queries to `queries.py`

#### ✅ JobRanker - COMPLETED (2025-01-17)
- [x] Remove any `main()` functions from service classes
- [x] Update service `__init__` to accept dependencies
- [x] Update database access to use abstraction
- [x] Update `__init__.py` exports
- [x] Extract SQL queries to `queries.py`
- [x] Updated to use `fact_jobs.profile_id` (no raw schema access)

#### ✅ NotificationCoordinator - COMPLETED
- [x] Remove any `main()` functions from service classes
- [x] Update service `__init__` to accept dependencies (Database + notifier)
- [x] Update database access to use abstraction (`Database.get_cursor()`)
- [ ] (Optional, future) Extract SQL queries to a dedicated notifier queries module

### Phase 3: Update Usage
- [x] Update Airflow `task_functions.py` - **COMPLETED**
  - [x] JobExtractor task updated
  - [x] CompanyExtractor task updated
  - [x] JobRanker task updated
- [x] Verify services work correctly in Airflow tasks - **COMPLETED**
- [x] Test all integration points - **COMPLETED**

### Phase 4: Testing
- [ ] Update existing unit tests
- [ ] Add new unit tests with mocks
- [ ] Add integration tests
- [ ] Verify test coverage maintained/improved

### Phase 5: Documentation
- [ ] Update service README files
- [ ] Update main project README
- [ ] Document new patterns and usage
- [ ] Update architecture diagrams if needed

### Phase 6: Cleanup
- [ ] Remove deprecated code
- [ ] Update type hints
- [ ] Code review
- [ ] Performance testing

---

## Notes

- **Backward Compatibility**: During transition, keep old interfaces working with deprecation warnings
- **Migration Order**: Start with least-used service to validate approach
- **Testing**: Ensure comprehensive test coverage before refactoring each service
- **Rollback Plan**: Keep old code in git history, maintain feature parity

---

## Future Enhancements (Post-Refactoring)

1. **Connection Pooling**: Implement connection pooling for better performance
2. **Query Builder**: Consider SQLAlchemy or similar for complex queries
3. **Configuration Validation**: Use Pydantic or similar for type-safe config
4. **Async Support**: Consider async/await for I/O-bound operations
5. **Monitoring**: Add structured logging and metrics
6. **API Layer**: Create REST API layer using the same service classes

---

## Recent Changes (2025-01-17)

### JobRanker Refactoring Completed
- ✅ Extracted SQL queries to `services/ranker/queries.py`
- ✅ Updated to use `Database` protocol (dependency injection)
- ✅ Removed `load_dotenv()` and `os.getenv()` calls
- ✅ Removed `main()` function and execution code
- ✅ Updated Airflow task to use new interface

### Database Schema Improvements
- ✅ Added `profile_id` to `fact_jobs` table (composite key: `jsearch_job_id`, `profile_id`)
- ✅ Updated ranker to use `fact_jobs.profile_id` directly (no raw schema access)
- ✅ Updated notifier to include `profile_id` in join conditions
- ✅ Created custom dbt test macro `assert_unique_combination` (no external dependencies)

### Infrastructure
- ✅ Created `services/shared/database.py` with `Database` protocol and `PostgreSQLDatabase` implementation
- ✅ All extractor and ranker services now use shared database module

---

**Document Version:** 1.1  
**Last Updated:** 2025-01-17  
**Author:** Development Team
