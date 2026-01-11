#!/usr/bin/env python3
"""
Verify FK constraints for campaign deletion are properly set up.

This script checks that all required FK constraints with CASCADE DELETE
are present in the database.

Usage:
    python scripts/verify_fk_constraints.py [--verbose]
"""

import argparse
import logging
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_db_connection() -> psycopg2.extensions.connection:
    """Get database connection from environment variables."""
    import os

    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "job_search_db")
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
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)


def verify_fk_constraints(verbose: bool = False) -> dict[str, bool]:
    """Verify FK constraints for campaign deletion.

    Args:
        verbose: If True, show detailed information about each constraint

    Returns:
        Dictionary with constraint names and their status (True if exists)
    """
    conn = get_db_connection()
    results: dict[str, bool] = {}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Expected FK constraints
            expected_constraints = [
                ("fk_dim_ranking_campaign", "marts", "dim_ranking", "campaign_id"),
                ("fk_fact_jobs_campaign", "marts", "fact_jobs", "campaign_id"),
                ("fk_etl_run_metrics_campaign", "marts", "etl_run_metrics", "campaign_id"),
                ("fk_user_job_status_campaign", "marts", "user_job_status", "campaign_id"),
                ("fk_job_notes_campaign", "marts", "job_notes", "campaign_id"),
            ]

            for constraint_name, schema, table_name, _column_name in expected_constraints:
                # Check if table exists
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = %s
                    )
                    """,
                    (schema, table_name),
                )
                result = cur.fetchone()
                table_exists = result["exists"] if result else False

                if not table_exists:
                    if verbose:
                        logger.info(
                            f"Table {schema}.{table_name} does not exist, skipping constraint check"
                        )
                    results[constraint_name] = False
                    continue

                # Check if FK constraint exists
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_constraint c
                        JOIN pg_class cl ON c.conrelid = cl.oid
                        JOIN pg_namespace n ON cl.relnamespace = n.oid
                        WHERE n.nspname = %s
                        AND cl.relname = %s
                        AND c.conname = %s
                        AND c.contype = 'f'
                    )
                    """,
                    (schema, table_name, constraint_name),
                )
                result = cur.fetchone()
                constraint_exists = result["exists"] if result else False

                # Check if constraint has CASCADE DELETE
                cascade_delete = False
                if constraint_exists:
                    cur.execute(
                        """
                        SELECT c.confdeltype = 'c' as cascade_delete
                        FROM pg_constraint c
                        JOIN pg_class cl ON c.conrelid = cl.oid
                        JOIN pg_namespace n ON cl.relnamespace = n.oid
                        WHERE n.nspname = %s
                        AND cl.relname = %s
                        AND c.conname = %s
                        AND c.contype = 'f'
                        """,
                        (schema, table_name, constraint_name),
                    )
                    result = cur.fetchone()
                    if result:
                        cascade_delete = result["cascade_delete"]

                results[constraint_name] = constraint_exists and cascade_delete

                if verbose:
                    status = "✓" if results[constraint_name] else "✗"
                    logger.info(
                        f"{status} {schema}.{table_name}.{constraint_name}: "
                        f"exists={constraint_exists}, cascade_delete={cascade_delete}"
                    )

            # Check PRIMARY KEY on campaign_id
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_constraint c
                    JOIN pg_class cl ON c.conrelid = cl.oid
                    JOIN pg_namespace n ON cl.relnamespace = n.oid
                    WHERE n.nspname = 'marts'
                    AND cl.relname = 'job_campaigns'
                    AND c.conname = 'job_campaigns_pkey'
                    AND c.contype = 'p'
                )
                """
            )
            result = cur.fetchone()
            pk_exists = result["exists"] if result else False
            results["job_campaigns_pkey"] = pk_exists

            if verbose:
                status = "✓" if pk_exists else "✗"
                logger.info(f"{status} marts.job_campaigns.job_campaigns_pkey: exists={pk_exists}")

            # Check sequence
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'marts'
                    AND c.relname = 'job_campaigns_campaign_id_seq'
                    AND c.relkind = 'S'
                )
                """
            )
            result = cur.fetchone()
            sequence_exists = result["exists"] if result else False
            results["job_campaigns_campaign_id_seq"] = sequence_exists

            if verbose:
                status = "✓" if sequence_exists else "✗"
                logger.info(
                    f"{status} Sequence marts.job_campaigns_campaign_id_seq: exists={sequence_exists}"
                )

    except Exception as e:
        logger.error(f"Error verifying FK constraints: {e}", exc_info=True)
        raise
    finally:
        conn.close()

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Verify FK constraints for campaign deletion")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed information")

    args = parser.parse_args()

    try:
        results = verify_fk_constraints(verbose=args.verbose)

        # Summary
        total = len(results)
        passed = sum(1 for v in results.values() if v)
        failed = total - passed

        logger.info(f"\nSummary: {passed}/{total} checks passed")

        if failed > 0:
            logger.warning("Failed checks:")
            for name, status in results.items():
                if not status:
                    logger.warning(f"  - {name}: MISSING")

            sys.exit(1)
        else:
            logger.info("All FK constraints are properly set up!")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
