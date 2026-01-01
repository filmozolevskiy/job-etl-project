"""Script to clean up orphaned rankings from marts.dim_ranking.

Orphaned rankings are rankings where the (jsearch_job_id, campaign_id) pair
does not exist in marts.fact_jobs. This script safely removes them with full
audit trail and metrics recording.
"""

import argparse
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

# Add services directory to path
services_path = Path(__file__).parent.parent / "services"
sys.path.insert(0, str(services_path))

from shared import MetricsRecorder, PostgreSQLDatabase


def build_db_connection_string() -> str:
    """Build PostgreSQL connection string from environment variables."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "job_search_db")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def ensure_audit_table_exists(database: PostgreSQLDatabase):
    """Ensure the audit table exists, create if it doesn't.

    Args:
        database: Database connection
    """
    create_audit_table_sql = """
        CREATE TABLE IF NOT EXISTS marts.dim_ranking_cleanup_audit (
            audit_id SERIAL PRIMARY KEY,
            jsearch_job_id varchar NOT NULL,
            campaign_id integer NOT NULL,
            rank_score numeric,
            rank_explain jsonb,
            ranked_at timestamp,
            ranked_date date,
            dwh_load_timestamp timestamp,
            dwh_source_system varchar,
            cleanup_timestamp timestamp DEFAULT CURRENT_TIMESTAMP,
            cleanup_reason varchar DEFAULT 'orphaned_ranking',
            cleanup_batch_id varchar,
            CONSTRAINT dim_ranking_cleanup_audit_pkey UNIQUE (jsearch_job_id, campaign_id, cleanup_timestamp)
        )
    """
    with database.get_cursor() as cur:
        cur.execute(create_audit_table_sql)


def get_orphaned_rankings(database: PostgreSQLDatabase) -> list[dict]:
    """Get all orphaned rankings.

    Args:
        database: Database connection

    Returns:
        List of orphaned ranking dictionaries
    """
    query = """
        SELECT dr.*
        FROM marts.dim_ranking dr
        LEFT JOIN marts.fact_jobs fj
            ON dr.jsearch_job_id = fj.jsearch_job_id
            AND dr.campaign_id = fj.campaign_id
        WHERE fj.jsearch_job_id IS NULL
        ORDER BY dr.ranked_at DESC NULLS LAST, dr.dwh_load_timestamp DESC NULLS LAST
    """
    with database.get_cursor() as cur:
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]


def backup_to_audit_table(
    database: PostgreSQLDatabase, orphaned_rankings: list[dict], batch_id: str
) -> int:
    """Backup orphaned rankings to audit table before deletion.

    Args:
        database: Database connection
        orphaned_rankings: List of orphaned ranking dictionaries
        batch_id: Unique batch ID for this cleanup operation

    Returns:
        Number of rankings backed up
    """
    if not orphaned_rankings:
        return 0

    insert_query = """
        INSERT INTO marts.dim_ranking_cleanup_audit (
            jsearch_job_id,
            campaign_id,
            rank_score,
            rank_explain,
            ranked_at,
            ranked_date,
            dwh_load_timestamp,
            dwh_source_system,
            cleanup_timestamp,
            cleanup_reason,
            cleanup_batch_id
        ) VALUES %s
        ON CONFLICT (jsearch_job_id, campaign_id, cleanup_timestamp)
        DO NOTHING
    """

    from psycopg2.extras import execute_values

    rows = []
    for ranking in orphaned_rankings:
        rows.append(
            (
                ranking["jsearch_job_id"],
                ranking["campaign_id"],
                ranking.get("rank_score"),
                ranking.get("rank_explain"),
                ranking.get("ranked_at"),
                ranking.get("ranked_date"),
                ranking.get("dwh_load_timestamp"),
                ranking.get("dwh_source_system"),
                datetime.now(),
                "orphaned_ranking",
                batch_id,
            )
        )

    with database.get_cursor() as cur:
        execute_values(cur, insert_query, rows)

    return len(rows)


def delete_orphaned_rankings(database: PostgreSQLDatabase, batch_size: int = 1000) -> int:
    """Delete orphaned rankings in batches.

    Args:
        database: Database connection
        batch_size: Number of rows to delete per batch

    Returns:
        Total number of rankings deleted
    """
    total_deleted = 0

    while True:
        # Get batch of orphaned rankings
        query = """
            DELETE FROM marts.dim_ranking
            WHERE (jsearch_job_id, campaign_id) IN (
                SELECT dr.jsearch_job_id, dr.campaign_id
                FROM marts.dim_ranking dr
                LEFT JOIN marts.fact_jobs fj
                    ON dr.jsearch_job_id = fj.jsearch_job_id
                    AND dr.campaign_id = fj.campaign_id
                WHERE fj.jsearch_job_id IS NULL
                LIMIT %s
            )
        """
        with database.get_cursor() as cur:
            cur.execute(query, (batch_size,))
            deleted_count = cur.rowcount
            total_deleted += deleted_count

            if deleted_count == 0:
                break

    return total_deleted


def verify_no_orphaned_rankings(database: PostgreSQLDatabase) -> bool:
    """Verify that no orphaned rankings remain.

    Args:
        database: Database connection

    Returns:
        True if no orphaned rankings found, False otherwise
    """
    query = """
        SELECT COUNT(*) as orphaned_count
        FROM marts.dim_ranking dr
        LEFT JOIN marts.fact_jobs fj
            ON dr.jsearch_job_id = fj.jsearch_job_id
            AND dr.campaign_id = fj.campaign_id
        WHERE fj.jsearch_job_id IS NULL
    """
    with database.get_cursor() as cur:
        cur.execute(query)
        result = cur.fetchone()
        return result[0] == 0


def cleanup_orphaned_rankings(
    database: PostgreSQLDatabase,
    metrics_recorder: MetricsRecorder,
    dry_run: bool = False,
    batch_size: int = 1000,
) -> dict:
    """Clean up orphaned rankings with full audit trail.

    Args:
        database: Database connection
        metrics_recorder: Metrics recorder for logging cleanup metrics
        dry_run: If True, only show what would be deleted without actually deleting
        batch_size: Number of rows to process per batch

    Returns:
        Dictionary with cleanup results
    """
    start_time = time.time()
    batch_id = str(uuid.uuid4())

    print("=" * 80)
    print("ORPHANED RANKINGS CLEANUP")
    print("=" * 80)
    print(f"Batch ID: {batch_id}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Batch Size: {batch_size}")
    print()

    # Ensure audit table exists
    ensure_audit_table_exists(database)

    # Get orphaned rankings
    print("Identifying orphaned rankings...")
    orphaned_rankings = get_orphaned_rankings(database)
    total_orphaned = len(orphaned_rankings)

    print(f"Found {total_orphaned} orphaned ranking(s)")

    if total_orphaned == 0:
        print("\n✅ No orphaned rankings to clean up.")
        return {
            "status": "success",
            "total_orphaned": 0,
            "backed_up": 0,
            "deleted": 0,
            "duration_seconds": time.time() - start_time,
        }

    # Backup to audit table
    if not dry_run:
        print("\nBacking up orphaned rankings to audit table...")
        backed_up = backup_to_audit_table(database, orphaned_rankings, batch_id)
        print(f"✅ Backed up {backed_up} ranking(s) to audit table")
    else:
        print("\n[DRY RUN] Would backup to audit table...")
        backed_up = total_orphaned

    # Delete orphaned rankings
    if not dry_run:
        print("\nDeleting orphaned rankings...")
        deleted = delete_orphaned_rankings(database, batch_size=batch_size)
        print(f"✅ Deleted {deleted} ranking(s)")

        # Verify cleanup
        print("\nVerifying cleanup...")
        is_clean = verify_no_orphaned_rankings(database)
        if is_clean:
            print("✅ Verification passed: No orphaned rankings remain")
        else:
            print("⚠️  Warning: Some orphaned rankings may still exist")
    else:
        print("\n[DRY RUN] Would delete orphaned rankings...")
        deleted = total_orphaned
        is_clean = True

    duration = time.time() - start_time

    # Record metrics
    if not dry_run:
        try:
            metrics_recorder.record_task_metrics(
                dag_run_id=f"cleanup_orphaned_rankings_{batch_id}",
                task_name="cleanup_orphaned_rankings",
                task_status="success",
                campaign_id=None,
                rows_processed_marts=deleted,
                processing_duration_seconds=duration,
                metadata={
                    "batch_id": batch_id,
                    "total_orphaned": total_orphaned,
                    "backed_up": backed_up,
                    "deleted": deleted,
                    "batch_size": batch_size,
                    "dry_run": dry_run,
                },
            )
        except Exception as e:
            print(f"⚠️  Warning: Failed to record metrics: {e}")

    result = {
        "status": "success" if is_clean else "warning",
        "total_orphaned": total_orphaned,
        "backed_up": backed_up,
        "deleted": deleted,
        "duration_seconds": duration,
        "batch_id": batch_id,
    }

    print("\n" + "=" * 80)
    print("CLEANUP SUMMARY")
    print("=" * 80)
    print(f"Total Orphaned: {result['total_orphaned']}")
    print(f"Backed Up: {result['backed_up']}")
    print(f"Deleted: {result['deleted']}")
    print(f"Duration: {result['duration_seconds']:.2f} seconds")
    print(f"Status: {result['status']}")
    print("=" * 80)

    return result


def main():
    """Main entry point for the cleanup script."""
    parser = argparse.ArgumentParser(
        description="Clean up orphaned rankings from marts.dim_ranking"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of rows to delete per batch (default: 1000)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only run verification query, don't delete anything",
    )

    args = parser.parse_args()

    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    metrics_recorder = MetricsRecorder(database=database)

    if args.verify_only:
        print("Running verification only...")
        is_clean = verify_no_orphaned_rankings(database)
        if is_clean:
            print("✅ No orphaned rankings found.")
            return 0
        else:
            print("⚠️  Orphaned rankings found. Run cleanup script to remove them.")
            return 1

    result = cleanup_orphaned_rankings(
        database=database,
        metrics_recorder=metrics_recorder,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
    )

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
