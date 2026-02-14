"""
Pytest configuration and fixtures for integration tests.

Integration tests require external dependencies like a database.
All tests in this directory should be marked with @pytest.mark.integration
"""

import os
import re
from pathlib import Path

import psycopg2
import pytest

# Import here to avoid circular imports when fixture runs
# close_all_pools is called at fixture start to avoid pg_terminate_backend killing pooled connections


@pytest.fixture
def test_db_connection_string():
    """Test database connection string."""
    return os.getenv(
        "TEST_DB_CONNECTION_STRING", "postgresql://postgres:postgres@127.0.0.1:5432/job_search_test"
    )


@pytest.fixture(scope="function")
def test_database(test_db_connection_string):
    """
    Set up and tear down test database for integration tests.

    Creates schemas and tables, then cleans up after tests.
    This fixture requires a running PostgreSQL database.
    """
    # Read schema and table creation scripts
    project_root = Path(__file__).parent.parent.parent

    # Parse connection string to get database name
    db_name = test_db_connection_string.split("/")[-1].split("?")[0]  # Remove query params if any

    # Use 127.0.0.1 instead of localhost to avoid IPv6 issues in some environments
    test_db_connection_string = test_db_connection_string.replace("@localhost", "@127.0.0.1")

    # Try to create base connection string to 'postgres' database
    parts = test_db_connection_string.split("/")
    if len(parts) >= 4:
        base_conn_str = "/".join(parts[:-1]) + "/postgres"
    else:
        base_conn_str = test_db_connection_string

    # Create test database if it doesn't exist
    # Note: CREATE DATABASE must be executed with autocommit=True and outside context manager
    import time

    max_retries = 5
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(base_conn_str)
            # Set autocommit before using cursor
            conn.autocommit = True
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                if not cur.fetchone():
                    # CREATE DATABASE must be executed with autocommit enabled
                    cur.execute(f'CREATE DATABASE "{db_name}"')
                cur.close()
            finally:
                conn.close()
            break  # Success
        except (psycopg2.OperationalError, psycopg2.ProgrammingError) as e:
            if attempt < max_retries - 1:
                print(
                    f"Connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
            else:
                # Last attempt failed, but we might be connecting directly to an existing DB
                # Proceed and let the next connection attempt fail if it's a real issue
                pass
        except psycopg2.errors.DuplicateDatabase:
            break  # Already exists

    # Close connection pools before pg_terminate_backend - otherwise pooled connections
    # get killed and subsequent tests receive dead connections from the pool.
    from services.shared.database import close_all_pools

    close_all_pools()

    # Connect to test database and set up schemas/tables
    # Note: We use autocommit=True, so each statement executes immediately
    with psycopg2.connect(test_db_connection_string) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            # Terminate any lingering connections to avoid lock issues during cleanup
            # EXCEPT our current connection
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid()
                """
            )

            # Drop all existing tables and views in test schemas to ensure clean state
            # This prevents issues with old schema (e.g., profile_id vs campaign_id)
            try:
                # Drop views first (they may depend on tables)
                cur.execute("""
                    DO $$
                    DECLARE
                        r RECORD;
                    BEGIN
                        FOR r IN (
                            SELECT schemaname, viewname
                            FROM pg_views
                            WHERE schemaname IN ('raw', 'staging', 'marts')
                        )
                        LOOP
                            EXECUTE 'DROP VIEW IF EXISTS ' || quote_ident(r.schemaname) || '.' || quote_ident(r.viewname) || ' CASCADE';
                        END LOOP;
                    END $$;
                """)
                # Drop tables
                cur.execute("""
                    DO $$
                    DECLARE
                        r RECORD;
                    BEGIN
                        FOR r IN (
                            SELECT schemaname, tablename
                            FROM pg_tables
                            WHERE schemaname IN ('raw', 'staging', 'marts')
                        )
                        LOOP
                            EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.schemaname) || '.' || quote_ident(r.tablename) || ' CASCADE';
                        END LOOP;
                    END $$;
                """)
            except psycopg2.Error:
                # If dropping fails, that's okay - tables/views might not exist yet
                pass

            # Read and execute all scripts in docker/init in alphabetical order
            init_dir = project_root / "docker" / "init"
            if init_dir.exists():
                scripts = sorted(init_dir.glob("*.sql"))
                for script_path in scripts:
                    with open(script_path, encoding="utf-8") as f:
                        sql = f.read()
                        # Split the script into individual statements to handle errors gracefully
                        # and avoid transaction aborts for the whole script
                        statements = []
                        
                        # First, extract all dollar-quoted blocks and replace them with placeholders
                        # This handles DO blocks, CREATE FUNCTION, etc.
                        blocks = []
                        # Pattern matches: $tag$ content $tag$
                        # We use a non-greedy match for the content
                        block_pattern = r"(\$[a-zA-Z0-9_]*\$).*?\1"
                        
                        def replace_block(match):
                            block = match.group(0)
                            placeholder = f"__BLOCK_{len(blocks)}__"
                            blocks.append(block)
                            return placeholder
                        
                        # Replace dollar-quoted blocks with placeholders
                        sql_with_placeholders = re.sub(
                            block_pattern, replace_block, sql, flags=re.DOTALL | re.IGNORECASE
                        )
                        
                        # Now split by semicolons and handle placeholders
                        for stmt in sql_with_placeholders.split(";"):
                            stmt = stmt.strip()
                            if not stmt or stmt.startswith("--"):
                                continue
                            
                            # Check if this statement contains a placeholder for a block
                            # A statement might contain multiple placeholders
                            while True:
                                placeholder_match = re.search(r"__BLOCK_(\d+)__", stmt)
                                if not placeholder_match:
                                    break
                                
                                block_idx = int(placeholder_match.group(1))
                                # Replace the placeholder with the original block
                                stmt = stmt.replace(placeholder_match.group(0), blocks[block_idx])
                            
                            # Regular statement - add semicolon back if not already present
                            if not stmt.endswith(";"):
                                statements.append(stmt + ";")
                            else:
                                statements.append(stmt)
                        
                        # Execute each statement individually
                        for statement in statements:
                            if not statement.strip() or statement.strip().startswith("--"):
                                continue
                            try:
                                cur.execute(statement)
                            except (
                                psycopg2.errors.DuplicateTable,
                                psycopg2.errors.DuplicateObject,
                                psycopg2.errors.DuplicateColumn,
                                psycopg2.errors.DuplicateSchema,
                                psycopg2.errors.DuplicateFunction,
                            ):
                                # Already exists - that's fine
                                # Reset connection state in case of any lingering errors
                                try:
                                    cur.execute("SELECT 1")
                                except psycopg2.Error:
                                    cur.close()
                                    cur = conn.cursor()
                                pass
                            except psycopg2.Error as e:
                                import sys

                                # Reset connection state after error
                                try:
                                    cur.execute("SELECT 1")
                                except psycopg2.Error:
                                    cur.close()
                                    cur = conn.cursor()

                                # Only warn for non-critical errors
                                error_str = str(e)
                                if (
                                    "does not exist" in error_str
                                    or "already exists" in error_str
                                    or "duplicate key value" in error_str
                                    or "is not a view" in error_str
                                ):
                                    # These are expected in some test scenarios
                                    pass
                                else:
                                    print(
                                        f"Warning: Statement in {script_path.name} failed: {e}",
                                        file=sys.stderr,
                                    )

    # CRITICAL: Verify columns after migration using a fresh connection
    # This ensures we have a clean connection even if migration left connection in bad state
    # Do this outside the main connection context to avoid transaction issues
    import sys

    try:
        with psycopg2.connect(test_db_connection_string) as verify_conn:
            verify_conn.autocommit = True
            with verify_conn.cursor() as verify_cur:
                # Check if job_notes table exists
                verify_cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'marts'
                        AND table_name = 'job_notes'
                    )
                    """
                )
                job_notes_exists = verify_cur.fetchone()[0]

                if job_notes_exists:
                    # Check if campaign_id exists in job_notes
                    verify_cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_schema = 'marts'
                            AND table_name = 'job_notes'
                            AND column_name = 'campaign_id'
                        )
                        """
                    )
                    job_notes_has_campaign_id = verify_cur.fetchone()[0]

                    if not job_notes_has_campaign_id:
                        # Column doesn't exist, add it explicitly
                        print(
                            "INFO: campaign_id column missing in job_notes, adding it explicitly",
                            file=sys.stderr,
                        )
                        try:
                            verify_cur.execute(
                                "ALTER TABLE marts.job_notes ADD COLUMN IF NOT EXISTS campaign_id integer"
                            )
                            print(
                                "INFO: Successfully added campaign_id to job_notes",
                                file=sys.stderr,
                            )
                        except psycopg2.Error as e:
                            print(
                                f"ERROR: Failed to add campaign_id to job_notes: {e}",
                                file=sys.stderr,
                            )

                # Check if user_job_status table exists
                verify_cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'marts'
                        AND table_name = 'user_job_status'
                    )
                    """
                )
                user_job_status_exists = verify_cur.fetchone()[0]

                if user_job_status_exists:
                    # Check if campaign_id exists in user_job_status
                    verify_cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_schema = 'marts'
                            AND table_name = 'user_job_status'
                            AND column_name = 'campaign_id'
                        )
                        """
                    )
                    user_job_status_has_campaign_id = verify_cur.fetchone()[0]

                    if not user_job_status_has_campaign_id:
                        # Column doesn't exist, add it explicitly
                        print(
                            "INFO: campaign_id column missing in user_job_status, adding it explicitly",
                            file=sys.stderr,
                        )
                        try:
                            verify_cur.execute(
                                "ALTER TABLE marts.user_job_status ADD COLUMN IF NOT EXISTS campaign_id integer"
                            )
                            print(
                                "INFO: Successfully added campaign_id to user_job_status",
                                file=sys.stderr,
                            )
                        except psycopg2.Error as e:
                            print(
                                f"ERROR: Failed to add campaign_id to user_job_status: {e}",
                                file=sys.stderr,
                            )

                # CRITICAL: Verify foreign key constraint for etl_run_metrics exists
                # This ensures CASCADE DELETE works when campaigns are deleted
                try:
                    # Check if etl_run_metrics table exists
                    verify_cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = 'marts'
                            AND table_name = 'etl_run_metrics'
                        )
                        """
                    )
                    etl_metrics_exists = verify_cur.fetchone()[0]

                    if etl_metrics_exists:
                        # Check if foreign key constraint exists
                        verify_cur.execute(
                            """
                            SELECT EXISTS (
                                SELECT 1 FROM pg_constraint
                                WHERE conname = 'fk_etl_run_metrics_campaign'
                                AND conrelid = 'marts.etl_run_metrics'::regclass
                            )
                            """
                        )
                        fk_exists = verify_cur.fetchone()[0]

                        if not fk_exists:
                            # Constraint doesn't exist, add it explicitly
                            print(
                                "INFO: fk_etl_run_metrics_campaign constraint missing, adding it explicitly",
                                file=sys.stderr,
                            )
                            try:
                                verify_cur.execute(
                                    """
                                    ALTER TABLE marts.etl_run_metrics
                                    ADD CONSTRAINT fk_etl_run_metrics_campaign
                                    FOREIGN KEY (campaign_id)
                                    REFERENCES marts.job_campaigns(campaign_id)
                                    ON DELETE CASCADE
                                    """
                                )
                                print(
                                    "INFO: Successfully added fk_etl_run_metrics_campaign constraint",
                                    file=sys.stderr,
                                )
                            except psycopg2.Error as e:
                                print(
                                    f"ERROR: Failed to add fk_etl_run_metrics_campaign constraint: {e}",
                                    file=sys.stderr,
                                )
                except psycopg2.Error as e:
                    print(
                        f"WARNING: Failed to verify/add fk_etl_run_metrics_campaign constraint: {e}",
                        file=sys.stderr,
                    )
    except psycopg2.Error as e:
        # If verification fails, log but don't fail setup
        # The test itself will fail if columns are missing, which is the desired behavior
        print(
            f"WARNING: Failed to verify/add campaign_id columns: {e}",
            file=sys.stderr,
        )

    # Yield connection string for use in tests
    yield test_db_connection_string

    # Cleanup: truncate tables but keep schema
    # (We don't drop the database as it might be reused)
    try:
        # Close pools again before cleanup to avoid connection leaks during cleanup
        from services.shared.database import close_all_pools

        close_all_pools()

        with psycopg2.connect(test_db_connection_string) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                # Terminate other connections before truncate
                cur.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                      AND pid <> pg_backend_pid()
                    """
                )
                # Truncate all tables
                cur.execute("""
                    DO $$
                    DECLARE
                        r RECORD;
                    BEGIN
                        FOR r IN (SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('raw', 'staging', 'marts'))
                        LOOP
                            EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.schemaname) || '.' || quote_ident(r.tablename) || ' CASCADE';
                        END LOOP;
                    END $$;
                """)
    except psycopg2.Error:
        # If cleanup fails, that's okay - test database might be managed externally
        pass


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
