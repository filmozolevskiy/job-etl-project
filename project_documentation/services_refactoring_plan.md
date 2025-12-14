# Services Refactoring Plan

**Status:** Planning Phase  
**Target Date:** After all services are ready  
**Priority:** High (Improves maintainability, testability, and code quality)

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

Services to be refactored:
- `services/extractor/job_extractor.py`
- `services/extractor/company_extractor.py`
- `services/ranker/job_ranker.py`
- Future services (enricher, notifier)

---

## Goals and Benefits

### Primary Goals

1. **Separation of Concerns**: Separate business logic from execution/CLI code
2. **Dependency Injection**: Make services testable and flexible
3. **SQL Management**: Extract SQL queries for better maintainability
4. **Improved Testing**: Enable comprehensive unit and integration testing
5. **Code Reusability**: Make services easier to use in different contexts

### Benefits

- **Testability**: Easy to mock dependencies and test in isolation
- **Maintainability**: Clear separation makes code easier to understand and modify
- **Flexibility**: Services can be used in CLI, API, or scheduled contexts
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
│   ├── company_extractor.py  (contains class + main())
│   ├── job_extractor.py      (contains class + main())
│   ├── glassdoor_client.py
│   └── jsearch_client.py
└── ranker/
    ├── __init__.py
    └── job_ranker.py         (contains class + main())
```

### Current Issues

1. **Mixed Responsibilities**: Service classes contain both business logic and CLI entry points
2. **Tight Coupling**: Direct dependency on environment variables and hard-coded dependency creation
3. **Embedded SQL**: SQL queries embedded as strings in methods
4. **Manual Resource Management**: Manual connection handling with try/finally blocks
5. **Hard to Test**: Difficult to mock dependencies and test in isolation
6. **Code Duplication**: Similar database connection patterns repeated across methods

---

## Refactoring Areas

### 1. Separation of Concerns

**Current Problem:**
- Service classes contain `main()` functions for CLI execution
- When imported by Airflow or other systems, CLI code is still present (even if unused)

**Solution:**
- Move `main()` functions to separate CLI entry point files
- Keep service classes focused solely on business logic

**Target Structure:**
```
services/
├── extractor/
│   ├── __init__.py              # Exports service classes
│   ├── company_extractor.py     # Only CompanyExtractor class
│   ├── job_extractor.py         # Only JobExtractor class
│   ├── cli.py                   # CLI entry points for extractor services
│   └── ...
└── ranker/
    ├── __init__.py              # Exports JobRanker class
    ├── job_ranker.py            # Only JobRanker class
    └── cli.py                   # CLI entry point for ranker
```

---

### 2. Dependency Injection

**Current Problem:**
- Services create their own dependencies (API clients, database connections)
- Hard dependency on environment variables
- Difficult to test with mocks

**Solution:**
- Inject dependencies through constructor parameters
- Create factory functions for production use (reads from env vars)
- Enable easy mocking in tests

**Pattern:**
```python
# Service class - accepts dependencies
class CompanyExtractor:
    def __init__(self, db_connection_string: str, glassdoor_client: GlassdoorClient):
        self.db_connection_string = db_connection_string
        self.client = glassdoor_client

# Factory function - creates from env vars (production)
def create_company_extractor(...) -> CompanyExtractor:
    # Reads env vars and creates dependencies
    pass
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

1. **Extract CLI Entry Points**
   - Move `main()` to `cli.py`
   - Update service class to remove CLI code

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

Using `CompanyExtractor` as an example:

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
from .database import Database
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

#### Step 4: Create Factory Function

**Create:**
```python
# services/extractor/factory.py
import os
from typing import Optional
from .company_extractor import CompanyExtractor
from .database import PostgreSQLDatabase
from .glassdoor_client import GlassdoorClient

def create_company_extractor(
    db_connection_string: Optional[str] = None,
    glassdoor_api_key: Optional[str] = None
) -> CompanyExtractor:
    """
    Factory function to create CompanyExtractor with dependencies from env vars.
    
    Args:
        db_connection_string: Optional DB connection string (reads from env if None)
        glassdoor_api_key: Optional API key (reads from env if None)
    
    Returns:
        Configured CompanyExtractor instance
    
    Raises:
        ValueError: If required configuration is missing
    """
    conn_str = db_connection_string or os.getenv('DB_CONNECTION_STRING')
    api_key = glassdoor_api_key or os.getenv('GLASSDOOR_API_KEY')
    
    if not conn_str:
        raise ValueError("Database connection string is required")
    if not api_key:
        raise ValueError("Glassdoor API key is required")
    
    database = PostgreSQLDatabase(connection_string=conn_str)
    client = GlassdoorClient(api_key=api_key)
    
    return CompanyExtractor(database=database, glassdoor_client=client)
```

#### Step 5: Extract CLI Entry Point

**Create:**
```python
# services/extractor/cli.py
"""
CLI entry points for extractor services.
"""

import sys
import logging
from .factory import create_company_extractor

logger = logging.getLogger(__name__)

def main_company_extractor():
    """CLI entry point for company extractor."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        extractor = create_company_extractor()
        results = extractor.extract_all_companies()
        
        print("\n=== Extraction Summary ===")
        for company, status in results.items():
            print(f"{company}: {status}")
        
        sys.exit(0)
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main_company_extractor()
```

**Update service file:**
```python
# services/extractor/company_extractor.py
# Remove the main() function entirely
```

#### Step 6: Update Existing Usage

**Airflow (task_functions.py):**
```python
# Before:
from extractor.company_extractor import CompanyExtractor

def extract_companies_task(**context):
    extractor = CompanyExtractor(
        db_connection_string=db_conn_str,
        glassdoor_api_key=glassdoor_api_key
    )

# After:
from extractor.factory import create_company_extractor

def extract_companies_task(**context):
    extractor = create_company_extractor(
        db_connection_string=db_conn_str,
        glassdoor_api_key=glassdoor_api_key
    )
```

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
from services.extractor.database import PostgreSQLDatabase
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
├── __init__.py                 # Exports: CompanyExtractor, create_company_extractor
├── company_extractor.py        # Service class only
├── database.py                 # Database abstraction
├── factory.py                  # Factory functions
├── queries.py                  # SQL queries
├── cli.py                      # CLI entry points
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

#### factory.py
```python
"""Factory functions for creating service instances."""

import os
from typing import Optional
from .company_extractor import CompanyExtractor
from .job_extractor import JobExtractor
from .database import PostgreSQLDatabase
from .glassdoor_client import GlassdoorClient
from .jsearch_client import JSearchClient

def create_company_extractor(
    db_connection_string: Optional[str] = None,
    glassdoor_api_key: Optional[str] = None
) -> CompanyExtractor:
    """
    Factory function to create CompanyExtractor with dependencies from env vars.
    
    Args:
        db_connection_string: Optional DB connection string (reads from env if None)
        glassdoor_api_key: Optional API key (reads from env if None)
    
    Returns:
        Configured CompanyExtractor instance
    
    Raises:
        ValueError: If required configuration is missing
    """
    conn_str = db_connection_string or os.getenv('DB_CONNECTION_STRING')
    api_key = glassdoor_api_key or os.getenv('GLASSDOOR_API_KEY')
    
    if not conn_str:
        raise ValueError("Database connection string is required (DB_CONNECTION_STRING env var)")
    if not api_key:
        raise ValueError("Glassdoor API key is required (GLASSDOOR_API_KEY env var)")
    
    database = PostgreSQLDatabase(connection_string=conn_str)
    client = GlassdoorClient(api_key=api_key)
    
    return CompanyExtractor(database=database, glassdoor_client=client)

def create_job_extractor(
    db_connection_string: Optional[str] = None,
    jsearch_api_key: Optional[str] = None,
    num_pages: Optional[int] = None
) -> JobExtractor:
    """Factory function to create JobExtractor."""
    # Similar pattern...
    pass
```

#### cli.py
```python
"""CLI entry points for extractor services."""

import sys
import logging
from .factory import create_company_extractor, create_job_extractor

logger = logging.getLogger(__name__)

def setup_logging():
    """Configure logging for CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main_company_extractor():
    """CLI entry point for company extractor."""
    setup_logging()
    
    try:
        extractor = create_company_extractor()
        results = extractor.extract_all_companies()
        
        print("\n=== Extraction Summary ===")
        for company, status in results.items():
            print(f"{company}: {status}")
        
        success_count = sum(1 for v in results.values() if v == 'success')
        not_found_count = sum(1 for v in results.values() if v == 'not_found')
        error_count = sum(1 for v in results.values() if v == 'error')
        
        print(f"\nSuccess: {success_count}, Not Found: {not_found_count}, Errors: {error_count}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        sys.exit(1)

def main_job_extractor():
    """CLI entry point for job extractor."""
    setup_logging()
    
    try:
        extractor = create_job_extractor()
        results = extractor.extract_all_jobs()
        
        print("\n=== Extraction Summary ===")
        for profile_id, count in results.items():
            print(f"Profile {profile_id}: {count} jobs")
        print(f"Total: {sum(results.values())} jobs")
        
        sys.exit(0 if all(count > 0 for count in results.values()) else 1)
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # Default to company extractor, but could use argparse for selection
    main_company_extractor()
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
from .factory import create_company_extractor, create_job_extractor

__all__ = [
    'BaseAPIClient',
    'JSearchClient',
    'GlassdoorClient',
    'CompanyExtractor',
    'JobExtractor',
    'create_company_extractor',
    'create_job_extractor',
]
```

### Usage Examples

#### In Airflow (Production)
```python
# airflow/dags/task_functions.py
from extractor.factory import create_company_extractor
from extractor.factory import create_job_extractor
from ranker.factory import create_job_ranker

def extract_companies_task(**context):
    """Airflow task to extract companies."""
    db_conn_str = build_db_connection_string()
    api_key = os.getenv('GLASSDOOR_API_KEY')
    
    # Use factory function
    extractor = create_company_extractor(
        db_connection_string=db_conn_str,
        glassdoor_api_key=api_key
    )
    
    results = extractor.extract_all_companies()
    return results
```

#### In Tests
```python
# tests/test_company_extractor.py
from unittest.mock import Mock
from services.extractor.company_extractor import CompanyExtractor
from services.extractor.database import Database
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

#### CLI Usage
```bash
# Run company extractor
python -m services.extractor.cli

# Or make it executable with proper entry points in setup.py
```

---

## Implementation Checklist

### Pre-Refactoring
- [ ] Review all services and identify all SQL queries
- [ ] Document current usage in Airflow, CLI, and other systems
- [ ] Create backup branch for rollback if needed
- [ ] Set up test database for integration tests

### Phase 1: Infrastructure
- [ ] Create `services/database.py` or per-service database modules
- [ ] Create `services/config.py` for centralized configuration
- [ ] Extract all SQL queries to query modules/files
- [ ] Create database protocol/interface

### Phase 2: Service Refactoring (per service)
- [ ] Extract `main()` functions to `cli.py`
- [ ] Update service `__init__` to accept dependencies
- [ ] Create factory function for service
- [ ] Update database access to use abstraction
- [ ] Update `__init__.py` exports

### Phase 3: Update Usage
- [ ] Update Airflow `task_functions.py`
- [ ] Update any other service consumers
- [ ] Update CLI entry points/setup.py if needed
- [ ] Test all integration points

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

**Document Version:** 1.0  
**Last Updated:** 2025-01-12  
**Author:** Development Team
