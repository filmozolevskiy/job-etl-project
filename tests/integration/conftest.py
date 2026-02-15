"""
Pytest configuration and fixtures for integration tests.

Integration tests require external dependencies like a database.
All tests in this directory should be marked with @pytest.mark.integration
"""

import os
from pathlib import Path

import psycopg2
import pytest

# Import here to avoid circular imports when fixture runs
# close_all_pools is called at fixture start to avoid pg_terminate_backend killing pooled connections


@pytest.fixture(scope="session")
def test_db_connection_string():
    """Test database connection string."""
    return os.getenv(
        "TEST_DB_CONNECTION_STRING", "postgresql://postgres:postgres@127.0.0.1:5432/job_search_test"
    )


@pytest.fixture(scope="session")
def initialized_test_db(test_db_connection_string):
    """
    Initialize the test database schema once per test session.
    """
    project_root = Path(__file__).parent.parent.parent
    db_name = test_db_connection_string.split("/")[-1].split("?")[0]
    test_db_connection_string = test_db_connection_string.replace("@localhost", "@127.0.0.1")

    # Try to create base connection string to 'postgres' database
    parts = test_db_connection_string.split("/")
    if len(parts) >= 4:
        base_conn_str = "/".join(parts[:-1]) + "/postgres"
    else:
        base_conn_str = test_db_connection_string

    # Create test database if it doesn't exist
    import time

    max_retries = 5
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(base_conn_str)
            try:
                conn.autocommit = True
            except psycopg2.ProgrammingError:
                pass
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                if not cur.fetchone():
                    cur.execute(f'CREATE DATABASE "{db_name}"')
                cur.close()
            finally:
                conn.close()
            break
        except (psycopg2.OperationalError, psycopg2.ProgrammingError):
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                pass
        except psycopg2.errors.DuplicateDatabase:
            break

    # Connect to test database and set up schemas/tables if needed
    def run_sql(sql_list, ignore_errors=False):
        with psycopg2.connect(test_db_connection_string) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                for sql in sql_list:
                    try:
                        cur.execute(sql)
                    except psycopg2.Error as e:
                        if not conn.autocommit:
                            conn.rollback()
                        if not ignore_errors:
                            import sys
                            print(f"Warning: SQL failed: {e}\nSQL: {sql[:100]}...", file=sys.stderr)

    # 1. Create schemas
    run_sql([
        "CREATE SCHEMA IF NOT EXISTS raw",
        "CREATE SCHEMA IF NOT EXISTS staging",
        "CREATE SCHEMA IF NOT EXISTS marts"
    ])

    # 2. Create base tables
    run_sql([
        """
        CREATE TABLE IF NOT EXISTS marts.dim_companies (
            company_key varchar PRIMARY KEY,
            company_name varchar,
            company_size varchar,
            company_link varchar,
            industry varchar,
            website varchar,
            rating numeric,
            review_count integer,
            logo_url varchar,
            logo varchar,
            dwh_load_date date,
            dwh_load_timestamp timestamp,
            dwh_source_system varchar
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS staging.jsearch_job_postings (
            jsearch_job_postings_key bigint,
            jsearch_job_id varchar,
            campaign_id integer,
            job_title varchar,
            employer_name varchar,
            job_location varchar,
            dwh_load_date date,
            dwh_load_timestamp timestamp,
            dwh_source_system varchar
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS staging.chatgpt_enrichments (
            chatgpt_enrichment_key BIGSERIAL PRIMARY KEY,
            jsearch_job_postings_key BIGINT NOT NULL,
            chatgpt_enriched_at TIMESTAMP,
            chatgpt_enrichment_status JSONB,
            dwh_load_date DATE DEFAULT CURRENT_DATE,
            dwh_load_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS marts.fact_jobs (
            jsearch_job_id varchar NOT NULL,
            campaign_id integer NOT NULL,
            job_title varchar,
            job_summary text,
            employer_name varchar,
            job_location varchar,
            employment_type varchar,
            job_posted_at_datetime_utc varchar,
            apply_options jsonb,
            job_apply_link varchar,
            company_key varchar,
            extracted_skills jsonb,
            seniority_level varchar,
            remote_work_type varchar,
            job_min_salary numeric,
            job_max_salary numeric,
            job_salary_period varchar,
            job_salary_currency varchar,
            dwh_load_date date,
            dwh_load_timestamp timestamp,
            dwh_source_system varchar,
            CONSTRAINT fact_jobs_pkey PRIMARY KEY (jsearch_job_id, campaign_id)
        )
        """
    ])

    # 3. Run init scripts
    init_dir = project_root / "docker" / "init"
    if init_dir.exists():
        scripts = sorted(init_dir.glob("*.sql"))
        for script_path in scripts:
            try:
                with open(script_path, encoding="utf-8") as f:
                    sql = f.read()
            except UnicodeDecodeError:
                print(f"Warning: Could not decode {script_path} as UTF-8, falling back to latin-1")
                with open(script_path, encoding="latin-1") as f:
                    sql = f.read()
            # Run each script in its own connection with autocommit
            run_sql([sql], ignore_errors=True)

    # 4. Ensure dim_companies has columns expected by job queries (dc.company_link, dc.logo)
    run_sql([
        """
        ALTER TABLE marts.dim_companies
        ADD COLUMN IF NOT EXISTS company_link varchar
        """,
        """
        ALTER TABLE marts.dim_companies
        ADD COLUMN IF NOT EXISTS logo varchar
        """
    ], ignore_errors=True)

    # 5. Add foreign keys (after scripts might have created referenced tables)
    run_sql([
        """
        ALTER TABLE marts.fact_jobs
        ADD CONSTRAINT fk_fact_jobs_campaign FOREIGN KEY (campaign_id)
            REFERENCES marts.job_campaigns(campaign_id) ON DELETE CASCADE
        """,
        """
        ALTER TABLE marts.fact_jobs
        ADD CONSTRAINT fk_fact_jobs_company FOREIGN KEY (company_key)
            REFERENCES marts.dim_companies(company_key) ON DELETE SET NULL
        """
    ], ignore_errors=True)

    return test_db_connection_string


@pytest.fixture(scope="function")
def test_database(initialized_test_db):
    """
    Clean up test database after each test by truncating tables.
    """
    from services.shared.database import close_all_pools

    close_all_pools()

    with psycopg2.connect(initialized_test_db) as conn:
        try:
            conn.autocommit = True
        except psycopg2.ProgrammingError:
            pass
        with conn.cursor() as cur:
            # Terminate other connections to avoid lock issues
            cur.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid()
            """)

            # Truncate all tables in our schemas
            cur.execute("""
                DO $$
                DECLARE
                    r RECORD;
                BEGIN
                    -- Use a single TRUNCATE command for all tables to handle dependencies correctly
                    -- and RESTART IDENTITY to reset SERIAL counters.
                    EXECUTE (
                        SELECT 'TRUNCATE TABLE ' || string_agg(quote_ident(schemaname) || '.' || quote_ident(tablename), ', ') || ' RESTART IDENTITY CASCADE'
                        FROM pg_tables
                        WHERE schemaname IN ('raw', 'staging', 'marts')
                    );
                END $$;
            """)

    yield initialized_test_db

    # Post-test cleanup (optional, truncation happens before test)
    close_all_pools()


@pytest.fixture
def test_storage_dir():
    """Create a temporary directory for file storage."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def resume_service(test_database, test_storage_dir):
    """Create ResumeService with test database and storage."""
    from services.documents import LocalStorageService, ResumeService
    from services.shared import PostgreSQLDatabase

    storage = LocalStorageService(base_dir=test_storage_dir)
    return ResumeService(
        database=PostgreSQLDatabase(connection_string=test_database),
        storage_service=storage,
        max_file_size=5 * 1024 * 1024,
        allowed_extensions=["pdf", "docx"],
    )


@pytest.fixture
def cover_letter_service(test_database, test_storage_dir):
    """Create CoverLetterService with test database and storage."""
    from services.documents import CoverLetterService, LocalStorageService
    from services.shared import PostgreSQLDatabase

    storage = LocalStorageService(base_dir=test_storage_dir)
    return CoverLetterService(
        database=PostgreSQLDatabase(connection_string=test_database),
        storage_service=storage,
        max_file_size=5 * 1024 * 1024,
        allowed_extensions=["pdf", "docx"],
    )


@pytest.fixture
def document_service(test_database):
    """Create DocumentService with test database."""
    from services.documents import DocumentService
    from services.shared import PostgreSQLDatabase

    return DocumentService(database=PostgreSQLDatabase(connection_string=test_database))


@pytest.fixture
def sample_jsearch_response():
    """Sample JSearch API response for integration testing."""
    return {
        "status": "OK",
        "request_id": "test-request-id",
        "parameters": {
            "query": "Business Intelligence Engineer",
            "page": 1,
            "num_pages": 1,
            "date_posted": "week",
            "country": "ca",
        },
        "data": [
            {
                "job_id": "test-job-1",
                "job_title": "Business Intelligence Engineer",
                "employer_name": "Test Company",
                "employer_logo": None,
                "employer_website": "https://testcompany.com",
                "job_publisher": "LinkedIn",
                "job_employment_type": "Full-time",
                "job_employment_types": ["FULLTIME"],
                "job_apply_link": "https://example.com/job/1",
                "job_apply_is_direct": False,
                "job_description": "Test job description for BI Engineer role",
                "job_is_remote": False,
                "job_posted_at": "2 days ago",
                "job_posted_at_timestamp": 1764892800,
                "job_posted_at_datetime_utc": "2025-12-05T00:00:00.000Z",
                "job_location": "Toronto, ON",
                "job_city": "Toronto",
                "job_state": "Ontario",
                "job_country": "CA",
                "job_latitude": 43.6532,
                "job_longitude": -79.3832,
                "job_min_salary": 80000,
                "job_max_salary": 100000,
                "job_salary_period": "YEAR",
            },
            {
                "job_id": "test-job-2",
                "job_title": "Data Engineer",
                "employer_name": "Another Company",
                "employer_logo": None,
                "employer_website": "https://anothercompany.com",
                "job_publisher": "Indeed",
                "job_employment_type": "Full-time",
                "job_employment_types": ["FULLTIME"],
                "job_apply_link": "https://example.com/job/2",
                "job_apply_is_direct": False,
                "job_description": "Test job description for Data Engineer role",
                "job_is_remote": True,
                "job_posted_at": "1 day ago",
                "job_posted_at_timestamp": 1764979200,
                "job_posted_at_datetime_utc": "2025-12-06T00:00:00.000Z",
                "job_location": "Remote",
                "job_city": None,
                "job_state": None,
                "job_country": "CA",
                "job_min_salary": None,
                "job_max_salary": None,
                "job_salary_period": None,
            },
        ],
    }


@pytest.fixture
def sample_glassdoor_response():
    """Sample Glassdoor API response for integration testing."""
    return {
        "status": "OK",
        "request_id": "test-glassdoor-request-id",
        "parameters": {
            "query": "Test Company",
            "domain": "www.testcompany.com",
            "limit": 10,
        },
        "data": [
            {
                "company_id": 12345,
                "name": "Test Company",
                "company_link": "https://www.glassdoor.com/Overview/Working-at-Test-Company.htm",
                "rating": 4.2,
                "review_count": 1000,
                "salary_count": 5000,
                "job_count": 100,
                "headquarters_location": "Toronto, ON",
                "logo": None,
                "company_size": "1000-5000 Employees",
                "company_size_category": "LARGE",
                "company_description": "Test company description",
                "industry": "Technology",
                "website": "https://www.testcompany.com",
                "company_type": "Company - Private",
                "revenue": "$100M - $500M (USD)",
                "business_outlook_rating": 0.75,
                "career_opportunities_rating": 4.0,
                "ceo": "Test CEO",
                "ceo_rating": 0.80,
                "compensation_and_benefits_rating": 4.1,
                "culture_and_values_rating": 4.0,
                "diversity_and_inclusion_rating": 3.9,
                "recommend_to_friend_rating": 0.85,
                "senior_management_rating": 3.8,
                "work_life_balance_rating": 4.1,
                "stock": None,
                "year_founded": 2010,
            }
        ],
    }
