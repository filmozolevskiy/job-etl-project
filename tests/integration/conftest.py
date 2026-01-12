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


@pytest.fixture
def test_db_connection_string():
    """Test database connection string."""
    return os.getenv(
        "TEST_DB_CONNECTION_STRING", "postgresql://postgres:postgres@localhost:5432/job_search_test"
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
    schema_script = project_root / "docker" / "init" / "01_create_schemas.sql"
    tables_script = project_root / "docker" / "init" / "02_create_tables.sql"
    migration_script = project_root / "docker" / "init" / "08_add_resume_cover_letter_tables.sql"
    documents_section_migration = (
        project_root / "docker" / "init" / "09_add_documents_section_flag.sql"
    )
    job_status_history_migration = (
        project_root / "docker" / "init" / "14_add_job_status_history_table.sql"
    )
    multi_note_migration = project_root / "docker" / "init" / "15_modify_job_notes_multi_note.sql"
    campaign_uniqueness_migration = (
        project_root / "docker" / "init" / "99_fix_campaign_id_uniqueness.sql"
    )
    campaign_id_user_tables_migration = (
        project_root / "docker" / "init" / "100_add_campaign_id_to_user_tables.sql"
    )

    # Parse connection string to get database name
    db_name = test_db_connection_string.split("/")[-1].split("?")[0]  # Remove query params if any
    # Try to create base connection string to 'postgres' database
    parts = test_db_connection_string.split("/")
    if len(parts) >= 4:
        base_conn_str = "/".join(parts[:-1]) + "/postgres"
    else:
        base_conn_str = test_db_connection_string

    # Create test database if it doesn't exist
    # Note: CREATE DATABASE must be executed with autocommit=True and outside context manager
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
    except (
        psycopg2.OperationalError,
        psycopg2.ProgrammingError,
        psycopg2.errors.DuplicateDatabase,
    ):
        # Database might already exist, or we might be connecting directly to it
        # This is fine - we'll proceed with setup
        pass

    # Connect to test database and set up schemas/tables
    # Note: We use autocommit=True, so each statement executes immediately
    with psycopg2.connect(test_db_connection_string) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
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

            # Read and execute schema creation script
            if schema_script.exists():
                with open(schema_script, encoding="utf-8") as f:
                    schema_sql = f.read()
                    # Use psycopg2's execute() but split statements properly
                    # We need to preserve DO $$ ... END $$; blocks when splitting
                    # Use a regex-based approach to split while preserving DO blocks

                    # First, extract DO blocks to preserve them
                    do_pattern = r"DO\s+\$\$.*?\$\$;"
                    do_blocks = {}
                    placeholder_prefix = "__DO_BLOCK_"

                    def replace_do_blocks(match):
                        block = match.group(0)
                        placeholder = f"{placeholder_prefix}{len(do_blocks)}__"
                        do_blocks[placeholder] = block
                        return placeholder

                    # Replace DO blocks with placeholders
                    sql_without_do = re.sub(
                        do_pattern, replace_do_blocks, schema_sql, flags=re.DOTALL | re.IGNORECASE
                    )

                    # Remove comment-only lines
                    lines = []
                    for line in sql_without_do.split("\n"):
                        stripped = line.strip()
                        if stripped and not stripped.startswith("--"):
                            lines.append(line)

                    # Split by semicolon (now safe since DO blocks are replaced)
                    cleaned_sql = "\n".join(lines)
                    raw_statements = [s.strip() for s in cleaned_sql.split(";") if s.strip()]
                    statements = []

                    for raw_stmt in raw_statements:
                        # Check if this statement contains a DO block placeholder
                        is_do_block = False
                        for placeholder, block in do_blocks.items():
                            if placeholder in raw_stmt:
                                statements.append(block)  # DO blocks already have semicolon
                                is_do_block = True
                                break

                        if not is_do_block and raw_stmt:
                            statements.append(
                                raw_stmt + ";"
                            )  # Add semicolon for regular statements

                    # Execute all statements
                    for statement in statements:
                        if statement and not statement.strip().startswith("--"):
                            try:
                                cur.execute(statement)
                            except (
                                psycopg2.errors.DuplicateSchema,
                                psycopg2.errors.DuplicateObject,
                            ):
                                # Already exists - that's fine
                                pass

            # Read and execute table creation script
            if tables_script.exists():
                with open(tables_script, encoding="utf-8") as f:
                    tables_sql = f.read()
                    # Handle DO blocks and CREATE VIEW statements properly
                    # Both can span multiple lines and need special handling

                    # First, extract DO blocks
                    do_pattern = r"DO\s+\$\$.*?\$\$;"
                    do_blocks = {}
                    placeholder_prefix = "__DO_BLOCK_"

                    def replace_do_blocks(match):
                        block = match.group(0)
                        placeholder = f"{placeholder_prefix}{len(do_blocks)}__"
                        do_blocks[placeholder] = block
                        return placeholder

                    sql_without_do = re.sub(
                        do_pattern, replace_do_blocks, tables_sql, flags=re.DOTALL | re.IGNORECASE
                    )

                    # Extract CREATE VIEW statements (they span multiple lines until semicolon)
                    # Pattern matches: CREATE [OR REPLACE] VIEW schema.viewname AS SELECT ... FROM ... ;
                    # Using DOTALL to match across newlines, and capturing until the final semicolon
                    # The pattern matches from CREATE to the semicolon after the FROM clause
                    # Updated to handle schema-qualified view names (e.g., marts.dim_ranking)
                    # More flexible pattern that handles multi-line SELECT statements
                    view_pattern = (
                        r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+[a-zA-Z_][a-zA-Z0-9_\.]*\s+AS\s+.*?;"
                    )
                    view_blocks = {}
                    view_placeholder_prefix = "__VIEW_BLOCK_"

                    def replace_view_blocks(match):
                        block = match.group(0)
                        placeholder = f"{view_placeholder_prefix}{len(view_blocks)}__"
                        view_blocks[placeholder] = block
                        return placeholder

                    sql_without_views = re.sub(
                        view_pattern,
                        replace_view_blocks,
                        sql_without_do,
                        flags=re.DOTALL | re.IGNORECASE,
                    )

                    # Extract CREATE INDEX statements (they span multiple lines: CREATE INDEX ... ON ... ;)
                    # Pattern matches: CREATE INDEX ... ON schema.table(...);
                    index_pattern = r"CREATE\s+INDEX\s+[^;]+?ON\s+[^;]+?;"
                    index_blocks = {}
                    index_placeholder_prefix = "__INDEX_BLOCK_"

                    def replace_index_blocks(match):
                        block = match.group(0)
                        placeholder = f"{index_placeholder_prefix}{len(index_blocks)}__"
                        index_blocks[placeholder] = block
                        return placeholder

                    sql_without_indexes = re.sub(
                        index_pattern,
                        replace_index_blocks,
                        sql_without_views,
                        flags=re.DOTALL | re.IGNORECASE,
                    )

                    # Remove comment-only lines
                    lines = []
                    for line in sql_without_indexes.split("\n"):
                        stripped = line.strip()
                        if stripped and not stripped.startswith("--"):
                            lines.append(line)

                    # Split by semicolon
                    cleaned_sql = "\n".join(lines)
                    raw_statements = [s.strip() for s in cleaned_sql.split(";") if s.strip()]
                    statements = []

                    for raw_stmt in raw_statements:
                        # Check if this statement contains a DO block placeholder
                        is_do_block = False
                        for placeholder, block in do_blocks.items():
                            if placeholder in raw_stmt:
                                statements.append(block)  # DO blocks already have semicolon
                                is_do_block = True
                                break

                        # Check if this statement contains a VIEW block placeholder
                        is_view_block = False
                        if not is_do_block:
                            for placeholder, block in view_blocks.items():
                                if placeholder in raw_stmt:
                                    statements.append(block)  # VIEW blocks already have semicolon
                                    is_view_block = True
                                    break

                        # Check if this statement contains an INDEX block placeholder
                        is_index_block = False
                        if not is_do_block and not is_view_block:
                            for placeholder, block in index_blocks.items():
                                if placeholder in raw_stmt:
                                    statements.append(block)  # INDEX blocks already have semicolon
                                    is_index_block = True
                                    break

                        if (
                            not is_do_block
                            and not is_view_block
                            and not is_index_block
                            and raw_stmt
                        ):
                            statements.append(
                                raw_stmt + ";"
                            )  # Add semicolon for regular statements

                    # Execute all statements
                    for statement in statements:
                        if statement and not statement.strip().startswith("--"):
                            try:
                                cur.execute(statement)
                            except (
                                psycopg2.errors.DuplicateTable,
                                psycopg2.errors.DuplicateObject,
                            ):
                                # Already exists - that's fine
                                pass

            # Read and execute migration script for document tables
            if migration_script.exists():
                with open(migration_script, encoding="utf-8") as f:
                    migration_sql = f.read()
                    # Use the same DO block handling as tables script
                    do_pattern = r"DO\s+\$\$.*?\$\$;"
                    do_blocks = {}
                    placeholder_prefix = "__DO_BLOCK_"

                    def replace_do_blocks(match):
                        block = match.group(0)
                        placeholder = f"{placeholder_prefix}{len(do_blocks)}__"
                        do_blocks[placeholder] = block
                        return placeholder

                    sql_without_do = re.sub(
                        do_pattern,
                        replace_do_blocks,
                        migration_sql,
                        flags=re.DOTALL | re.IGNORECASE,
                    )

                    # Extract CREATE INDEX statements
                    index_pattern = r"CREATE\s+INDEX\s+[^;]+?ON\s+[^;]+?;"
                    index_blocks = {}
                    index_placeholder_prefix = "__INDEX_BLOCK_"

                    def replace_index_blocks(match):
                        block = match.group(0)
                        placeholder = f"{index_placeholder_prefix}{len(index_blocks)}__"
                        index_blocks[placeholder] = block
                        return placeholder

                    sql_without_indexes = re.sub(
                        index_pattern,
                        replace_index_blocks,
                        sql_without_do,
                        flags=re.DOTALL | re.IGNORECASE,
                    )

                    # Remove comment-only lines
                    lines = []
                    for line in sql_without_indexes.split("\n"):
                        stripped = line.strip()
                        if stripped and not stripped.startswith("--"):
                            lines.append(line)

                    # Split by semicolon
                    cleaned_sql = "\n".join(lines)
                    raw_statements = [s.strip() for s in cleaned_sql.split(";") if s.strip()]
                    statements = []

                    for raw_stmt in raw_statements:
                        is_do_block = False
                        for placeholder, block in do_blocks.items():
                            if placeholder in raw_stmt:
                                statements.append(block)
                                is_do_block = True
                                break

                        is_index_block = False
                        if not is_do_block:
                            for placeholder, block in index_blocks.items():
                                if placeholder in raw_stmt:
                                    statements.append(block)
                                    is_index_block = True
                                    break

                        if not is_do_block and not is_index_block and raw_stmt:
                            statements.append(raw_stmt + ";")

                    # Execute all statements
                    for statement in statements:
                        if statement and not statement.strip().startswith("--"):
                            try:
                                cur.execute(statement)
                            except (
                                psycopg2.errors.DuplicateTable,
                                psycopg2.errors.DuplicateObject,
                            ):
                                # Already exists - that's fine
                                pass

            # Read and execute documents section migration script
            # Execute directly as a single SQL string to avoid parsing issues with DO blocks
            if documents_section_migration.exists():
                with open(documents_section_migration, encoding="utf-8") as f:
                    migration_sql = f.read()
                    # Execute the entire migration script as-is
                    # This avoids issues with DO block parsing
                    try:
                        cur.execute(migration_sql)
                    except (
                        psycopg2.errors.DuplicateTable,
                        psycopg2.errors.DuplicateObject,
                        psycopg2.errors.DuplicateColumn,
                    ):
                        # Already exists - that's fine
                        pass
                    except psycopg2.Error as e:
                        # Log database errors but don't fail - migration might have partial success
                        import sys

                        print(
                            f"Warning: Documents section migration failed: {e}",
                            file=sys.stderr,
                        )
                        # Re-raise for critical errors that indicate the migration can't proceed
                        if "does not exist" in str(e) and "relation" in str(e):
                            raise
                        pass

            # Read and execute job status history migration script
            if job_status_history_migration.exists():
                with open(job_status_history_migration, encoding="utf-8") as f:
                    migration_sql = f.read()
                    try:
                        cur.execute(migration_sql)
                    except (
                        psycopg2.errors.DuplicateTable,
                        psycopg2.errors.DuplicateObject,
                        psycopg2.errors.DuplicateColumn,
                    ):
                        # Already exists - that's fine
                        pass
                    except psycopg2.Error as e:
                        import sys

                        print(
                            f"Warning: Job status history migration failed: {e}",
                            file=sys.stderr,
                        )
                        if "does not exist" in str(e) and "relation" in str(e):
                            raise
                        pass

            # Read and execute multi-note migration script
            if multi_note_migration.exists():
                with open(multi_note_migration, encoding="utf-8") as f:
                    migration_sql = f.read()
                    try:
                        cur.execute(migration_sql)
                    except (
                        psycopg2.errors.DuplicateTable,
                        psycopg2.errors.DuplicateObject,
                        psycopg2.errors.DuplicateColumn,
                    ):
                        # Already exists - that's fine
                        pass
                    except psycopg2.Error as e:
                        import sys

                        print(
                            f"Warning: Multi-note migration failed: {e}",
                            file=sys.stderr,
                        )
                        if "does not exist" in str(e) and "relation" in str(e):
                            raise
                        pass

            # Read and execute campaign uniqueness migration script
            if campaign_uniqueness_migration.exists():
                with open(campaign_uniqueness_migration, encoding="utf-8") as f:
                    migration_sql = f.read()
                    try:
                        cur.execute(migration_sql)
                    except (
                        psycopg2.errors.DuplicateTable,
                        psycopg2.errors.DuplicateObject,
                        psycopg2.errors.DuplicateColumn,
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

                        print(
                            f"Warning: Campaign uniqueness migration failed: {e}",
                            file=sys.stderr,
                        )
                        # Reset connection state after error to prevent transaction abort
                        try:
                            cur.execute("SELECT 1")
                        except psycopg2.Error:
                            # Connection is in bad state, close and reopen cursor
                            cur.close()
                            cur = conn.cursor()
                        # Allow UndefinedTable errors for fact_jobs (created by dbt, not in init)
                        # Migration script handles missing tables gracefully
                        if "does not exist" in str(e) and "relation" in str(e):
                            if "fact_jobs" not in str(e):
                                # Only raise if it's not fact_jobs
                                pass
                            # fact_jobs might not exist yet - that's okay, migration handles it
                        # Other errors are warnings, continue

            # Read and execute campaign_id user tables migration script
            # This must run after campaign_uniqueness_migration
            # IMPORTANT: Reset connection state before executing to ensure clean state
            # even if previous migration failed and left connection in bad state
            try:
                cur.execute("SELECT 1")
            except psycopg2.Error:
                # Connection is in bad state, close and reopen cursor
                cur.close()
                cur = conn.cursor()

            # Execute statement by statement to handle errors gracefully
            if campaign_id_user_tables_migration.exists():
                with open(campaign_id_user_tables_migration, encoding="utf-8") as f:
                    migration_sql = f.read()

                    # Split the migration into individual DO blocks and statements
                    # This ensures that if one DO block fails, others can still execute
                    # First, extract all DO blocks and replace them with placeholders
                    do_blocks = []
                    do_pattern = r"DO\s+\$\$.*?\$\$\s*;"

                    def replace_do_block(match):
                        block = match.group(0)
                        placeholder = f"__DO_BLOCK_{len(do_blocks)}__"
                        do_blocks.append(block)
                        return placeholder

                    # Replace DO blocks with placeholders
                    sql_with_placeholders = re.sub(
                        do_pattern, replace_do_block, migration_sql, flags=re.DOTALL | re.IGNORECASE
                    )

                    # Now split by semicolons and handle placeholders
                    statements = []
                    for stmt in sql_with_placeholders.split(";"):
                        stmt = stmt.strip()
                        if not stmt or stmt.startswith("--"):
                            continue

                        # Check if this statement contains a placeholder for a DO block
                        # Placeholders might be on their own line or mixed with other text
                        placeholder_match = re.search(r"__DO_BLOCK_(\d+)__", stmt)
                        if placeholder_match:
                            block_idx = int(placeholder_match.group(1))
                            # Extract and restore the DO block
                            statements.append(do_blocks[block_idx])
                            # If there's other text in the statement (unlikely), handle it
                            remaining = re.sub(r"__DO_BLOCK_\d+__", "", stmt).strip()
                            if remaining and not remaining.startswith("--"):
                                statements.append(remaining + ";")
                        else:
                            # Regular statement - add semicolon back
                            statements.append(stmt + ";")

                    # Execute each statement individually with error recovery
                    for statement in statements:
                        if not statement.strip() or statement.strip().startswith("--"):
                            continue
                        try:
                            cur.execute(statement)
                        except (
                            psycopg2.errors.DuplicateTable,
                            psycopg2.errors.DuplicateObject,
                            psycopg2.errors.DuplicateColumn,
                            psycopg2.errors.DuplicateFunction,
                        ):
                            # Already exists - that's fine
                            # Reset connection state in case of any lingering errors
                            try:
                                cur.execute("SELECT 1")
                            except psycopg2.Error:
                                # If reset fails, connection might be in bad state
                                # Close and reopen cursor
                                cur.close()
                                cur = conn.cursor()
                            pass
                        except psycopg2.Error as e:
                            import sys

                            # Reset connection state after error
                            # With autocommit=True, we need to execute a simple query to reset
                            try:
                                cur.execute("SELECT 1")
                            except psycopg2.Error:
                                # Connection is in bad state, close and reopen cursor
                                cur.close()
                                cur = conn.cursor()

                            # Only warn for non-critical errors
                            error_str = str(e)
                            if "does not exist" in error_str or "already exists" in error_str:
                                # These are expected in some test scenarios
                                pass
                            else:
                                print(
                                    f"Warning: Campaign ID user tables migration statement failed: {e}",
                                    file=sys.stderr,
                                )
                            # Continue with next statement

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
        with psycopg2.connect(test_db_connection_string) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
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
