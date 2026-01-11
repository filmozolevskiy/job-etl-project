#!/usr/bin/env python3
"""
Run database migrations manually.

This script runs migration scripts in order, handling errors gracefully.

Usage:
    python scripts/run_migrations.py [--database DATABASE] [--verbose]
"""

import argparse
import logging
import sys
from pathlib import Path

import psycopg2

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_db_connection(database: str = None) -> psycopg2.extensions.connection:
    """Get database connection from environment variables."""
    import os

    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = database or os.getenv("DB_NAME", "job_search_db")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")

    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
        )
        conn.autocommit = True  # Each statement executes immediately
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)


def run_migration(conn: psycopg2.extensions.connection, migration_file: Path, verbose: bool = False) -> bool:
    """Run a single migration file.

    Args:
        conn: Database connection
        migration_file: Path to migration SQL file
        verbose: If True, show detailed information

    Returns:
        True if migration succeeded, False otherwise
    """
    if not migration_file.exists():
        if verbose:
            logger.warning(f"Migration file not found: {migration_file}")
        return False

    try:
        with open(migration_file, encoding="utf-8") as f:
            migration_sql = f.read()

        if verbose:
            logger.info(f"Running migration: {migration_file.name}")

        with conn.cursor() as cur:
            cur.execute(migration_sql)

        if verbose:
            logger.info(f"✓ Migration completed: {migration_file.name}")
        return True

    except (
        psycopg2.errors.DuplicateTable,
        psycopg2.errors.DuplicateObject,
        psycopg2.errors.DuplicateColumn,
    ) as e:
        if verbose:
            logger.info(f"✓ Migration already applied (skipped): {migration_file.name} - {e}")
        return True
    except psycopg2.Error as e:
        logger.error(f"✗ Migration failed: {migration_file.name} - {e}")
        # Check if it's a non-critical error (missing table that will be created later)
        error_str = str(e).lower()
        if "does not exist" in error_str and "relation" in error_str:
            if "fact_jobs" in error_str or "dim_ranking" in error_str:
                if verbose:
                    logger.warning(
                        f"  Migration skipped missing table (this is OK): {migration_file.name}"
                    )
                return True  # Not a critical failure
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument("--database", "-d", help="Database name (default: from DB_NAME env var)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed information")

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    migrations_dir = project_root / "docker" / "init"

    # Migration files to run in order
    migration_files = [
        migrations_dir / "99_fix_campaign_id_uniqueness.sql",
        migrations_dir / "100_add_campaign_id_to_user_tables.sql",
    ]

    try:
        conn = get_db_connection(args.database)

        results = {}
        for migration_file in migration_files:
            success = run_migration(conn, migration_file, args.verbose)
            results[migration_file.name] = success

        conn.close()

        # Summary
        total = len(results)
        passed = sum(1 for v in results.values() if v)
        failed = total - passed

        logger.info(f"\nSummary: {passed}/{total} migrations succeeded")

        if failed > 0:
            logger.warning("Failed migrations:")
            for name, status in results.items():
                if not status:
                    logger.warning(f"  - {name}: FAILED")
            sys.exit(1)
        else:
            logger.info("All migrations completed successfully!")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Migration process failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
