"""Reset remote_type_enriched flag for jobs that may need re-classification.

This script resets the remote_type_enriched flag to false for jobs that:
1. Have "hybrid" in description but are classified as "remote" or "onsite"
2. Have both "remote" and "on-site"/"onsite" in description but are not "hybrid"
3. Have "hybrid working environment" or similar patterns but wrong classification

This allows them to be re-enriched with improved patterns.
"""

import os
import sys
from pathlib import Path

# Add services directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from shared.database import PostgreSQLDatabase


def build_db_connection_string() -> str:
    """Build PostgreSQL connection string from environment variables."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "job_search_db")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def reset_remote_type_enrichment() -> None:
    """Reset remote_type_enriched flag for jobs that need re-classification."""
    db_conn_str = build_db_connection_string()
    try:
        db = PostgreSQLDatabase(connection_string=db_conn_str)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

    # Query to find jobs that may need re-classification
    reset_query = """
        UPDATE staging.jsearch_job_postings
        SET enrichment_status = jsonb_set(
            enrichment_status,
            '{remote_type_enriched}',
            'false'::jsonb
        )
        WHERE (
            -- Jobs with "hybrid" in description but classified as remote or onsite
            (
                (job_description ILIKE '%hybrid%'
                 OR job_description ILIKE '%hybrid working environment%'
                 OR job_description ILIKE '%hybrid work environment%'
                 OR job_description ILIKE '%both remote and on-site%'
                 OR job_description ILIKE '%both remote and onsite%'
                 OR job_description ILIKE '%remote and on-site%'
                 OR job_description ILIKE '%remote and onsite%')
                AND remote_work_type IN ('remote', 'onsite')
            )
            -- Jobs with both remote and on-site mentioned but not hybrid
            OR (
                (job_description ILIKE '%remote%'
                 AND (job_description ILIKE '%on-site%'
                      OR job_description ILIKE '%onsite%'
                      OR job_description ILIKE '%in-office%'
                      OR job_description ILIKE '%in office%'))
                AND remote_work_type != 'hybrid'
            )
        )
        AND (enrichment_status->>'remote_type_enriched')::boolean = true
        RETURNING jsearch_job_postings_key, job_title, remote_work_type,
                  LEFT(job_description, 100) as desc_preview;
    """

    with db.get_cursor() as cur:
        cur.execute(reset_query)
        results = cur.fetchall()

        if results:
            print(f"Reset remote_type_enriched for {len(results)} jobs:")
            for row in results:
                try:
                    title = str(row[1] or "").encode("ascii", "ignore").decode("ascii")
                    preview = str(row[3] or "").encode("ascii", "ignore").decode("ascii")
                    print(
                        f"  Key: {row[0]}, Title: {title[:50]}, "
                        f"Current: {row[2]}, Preview: {preview[:80]}"
                    )
                except Exception as e:
                    print(f"  Key: {row[0]}, Current: {row[2]} (error printing details: {e})")
        else:
            print("No jobs found that need re-classification.")

    print("\nThese jobs will be re-enriched on the next enrichment run.")


if __name__ == "__main__":
    reset_remote_type_enrichment()
