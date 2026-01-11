#!/usr/bin/env python3
"""
Cleanup script for orphaned campaign data.

This script removes data that references non-existent campaigns:
- Rankings without campaigns
- Fact jobs without campaigns
- ETL metrics without campaigns
- User job status without campaigns
- Job notes without campaigns
- Staging jobs without campaigns
- Raw jobs without campaigns

Usage:
    python scripts/cleanup_orphaned_campaign_data.py [--dry-run] [--verbose]
"""

import argparse
import logging
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
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


def cleanup_orphaned_data(dry_run: bool = False, verbose: bool = False) -> dict[str, int]:
    """Clean up orphaned data from deleted campaigns.

    Args:
        dry_run: If True, only report what would be deleted without actually deleting
        verbose: If True, show detailed information about each deletion

    Returns:
        Dictionary with counts of deleted records per table
    """
    conn = get_db_connection()
    results: dict[str, int] = {}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get list of existing campaign IDs
            cur.execute("SELECT campaign_id FROM marts.job_campaigns")
            existing_campaign_ids = {row["campaign_id"] for row in cur.fetchall()}

            if verbose:
                logger.info(f"Found {len(existing_campaign_ids)} existing campaigns")

            # Tables to clean up (table_name, schema, campaign_id_column)
            tables_to_clean = [
                ("dim_ranking", "marts", "campaign_id"),
                ("fact_jobs", "marts", "campaign_id"),
                ("etl_run_metrics", "marts", "campaign_id"),
                ("user_job_status", "marts", "campaign_id"),
                ("job_notes", "marts", "campaign_id"),
                ("jsearch_job_postings", "staging", "campaign_id"),
                ("jsearch_job_postings", "raw", "campaign_id"),
            ]

            for table_name, schema, campaign_id_col in tables_to_clean:
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
                        logger.info(f"Table {schema}.{table_name} does not exist, skipping")
                    continue

                # Count orphaned records
                if campaign_id_col:
                    # Check if campaign_id column exists
                    cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_schema = %s
                            AND table_name = %s
                            AND column_name = %s
                        )
                        """,
                        (schema, table_name, campaign_id_col),
                    )
                    result = cur.fetchone()
                    col_exists = result["exists"] if result else False

                    if not col_exists:
                        if verbose:
                            logger.info(
                                f"Column {campaign_id_col} does not exist in {schema}.{table_name}, skipping"
                            )
                        continue

                    cur.execute(
                        f"""
                        SELECT COUNT(*) as count
                        FROM {schema}.{table_name}
                        WHERE {campaign_id_col} IS NOT NULL
                            AND {campaign_id_col} NOT IN %s
                        """,
                        (tuple(existing_campaign_ids) if existing_campaign_ids else (None,),),
                    )
                else:
                    # For tables without campaign_id, check via joins
                    cur.execute(
                        f"""
                        SELECT COUNT(*) as count
                        FROM {schema}.{table_name} t
                        WHERE NOT EXISTS (
                            SELECT 1 FROM marts.job_campaigns jc
                            WHERE jc.campaign_id = t.{campaign_id_col}
                        )
                        """
                    )

                count_result = cur.fetchone()
                orphaned_count = count_result["count"] if count_result else 0

                if orphaned_count > 0:
                    if dry_run:
                        logger.info(
                            f"[DRY RUN] Would delete {orphaned_count} orphaned records "
                            f"from {schema}.{table_name}"
                        )
                    else:
                        # Delete orphaned records
                        if campaign_id_col:
                            cur.execute(
                                f"""
                                DELETE FROM {schema}.{table_name}
                                WHERE {campaign_id_col} IS NOT NULL
                                    AND {campaign_id_col} NOT IN %s
                                """,
                                (
                                    tuple(existing_campaign_ids)
                                    if existing_campaign_ids
                                    else (None,),
                                ),
                            )
                        else:
                            cur.execute(
                                f"""
                                DELETE FROM {schema}.{table_name} t
                                WHERE NOT EXISTS (
                                    SELECT 1 FROM marts.job_campaigns jc
                                    WHERE jc.campaign_id = t.{campaign_id_col}
                                )
                                """
                            )

                        deleted_count = cur.rowcount
                        conn.commit()
                        logger.info(
                            f"Deleted {deleted_count} orphaned records from {schema}.{table_name}"
                        )
                        results[f"{schema}.{table_name}"] = deleted_count
                else:
                    if verbose:
                        logger.info(f"No orphaned records in {schema}.{table_name}")

            # Special case: ChatGPT enrichments (via join to staging jobs)
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'staging' AND table_name = 'chatgpt_enrichments'
                ) as exists
                """
            )
            result = cur.fetchone()
            if result and result["exists"]:
                cur.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM staging.chatgpt_enrichments ce
                    WHERE EXISTS (
                        SELECT 1 FROM staging.jsearch_job_postings jp
                        WHERE jp.jsearch_job_postings_key = ce.jsearch_job_postings_key
                            AND jp.campaign_id IS NOT NULL
                            AND jp.campaign_id NOT IN %s
                    )
                    """,
                    (tuple(existing_campaign_ids) if existing_campaign_ids else (None,),),
                )
                count_result = cur.fetchone()
                orphaned_count = count_result["count"] if count_result else 0

                if orphaned_count > 0:
                    if dry_run:
                        logger.info(
                            f"[DRY RUN] Would delete {orphaned_count} orphaned enrichments "
                            "from staging.chatgpt_enrichments"
                        )
                    else:
                        cur.execute(
                            """
                            DELETE FROM staging.chatgpt_enrichments ce
                            WHERE EXISTS (
                                SELECT 1 FROM staging.jsearch_job_postings jp
                                WHERE jp.jsearch_job_postings_key = ce.jsearch_job_postings_key
                                    AND jp.campaign_id IS NOT NULL
                                    AND jp.campaign_id NOT IN %s
                            )
                            """,
                            (
                                tuple(existing_campaign_ids)
                                if existing_campaign_ids
                                else (None,),
                            ),
                        )
                        deleted_count = cur.rowcount
                        conn.commit()
                        logger.info(
                            f"Deleted {deleted_count} orphaned enrichments from "
                            "staging.chatgpt_enrichments"
                        )
                        results["staging.chatgpt_enrichments"] = deleted_count

    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean up orphaned campaign data from deleted campaigns"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed information"
    )

    args = parser.parse_args()

    try:
        results = cleanup_orphaned_data(dry_run=args.dry_run, verbose=args.verbose)

        if args.dry_run:
            logger.info("Dry run completed. No data was deleted.")
        else:
            total_deleted = sum(results.values())
            logger.info(f"Cleanup completed. Total records deleted: {total_deleted}")
            if results:
                logger.info("Breakdown by table:")
                for table, count in results.items():
                    logger.info(f"  {table}: {count}")

    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
