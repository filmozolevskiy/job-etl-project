"""Script to analyze orphaned rankings in marts.dim_ranking.

Orphaned rankings are rankings where the (jsearch_job_id, campaign_id) pair
does not exist in marts.fact_jobs. This script identifies and analyzes these
orphaned rankings to understand root causes.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add services directory to path
services_path = Path(__file__).parent.parent / "services"
sys.path.insert(0, str(services_path))

from shared import PostgreSQLDatabase


def build_db_connection_string() -> str:
    """Build PostgreSQL connection string from environment variables."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "job_search_db")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def analyze_orphaned_rankings(database: PostgreSQLDatabase) -> dict:
    """Analyze orphaned rankings and generate comprehensive report.

    Args:
        database: Database connection

    Returns:
        Dictionary containing analysis results
    """
    report = {
        "analysis_timestamp": datetime.now().isoformat(),
        "total_orphaned_rankings": 0,
        "distribution_by_campaign": {},
        "distribution_by_date": {},
        "staging_check": {},
        "root_cause_analysis": {},
    }

    with database.get_cursor() as cur:
        # Query 1: Get all orphaned rankings
        orphaned_query = """
            SELECT dr.*
            FROM marts.dim_ranking dr
            LEFT JOIN marts.fact_jobs fj
                ON dr.jsearch_job_id = fj.jsearch_job_id
                AND dr.campaign_id = fj.campaign_id
            WHERE fj.jsearch_job_id IS NULL
            ORDER BY dr.ranked_at DESC NULLS LAST, dr.dwh_load_timestamp DESC NULLS LAST
        """
        cur.execute(orphaned_query)
        orphaned_rankings = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        orphaned_data = [dict(zip(columns, row)) for row in orphaned_rankings]

        report["total_orphaned_rankings"] = len(orphaned_data)

        if not orphaned_data:
            print("No orphaned rankings found.")
            return report

        # Query 2: Distribution by campaign_id
        campaign_dist_query = """
            SELECT
                dr.campaign_id,
                COUNT(*) as orphaned_count,
                MIN(dr.ranked_at) as earliest_ranked,
                MAX(dr.ranked_at) as latest_ranked
            FROM marts.dim_ranking dr
            LEFT JOIN marts.fact_jobs fj
                ON dr.jsearch_job_id = fj.jsearch_job_id
                AND dr.campaign_id = fj.campaign_id
            WHERE fj.jsearch_job_id IS NULL
            GROUP BY dr.campaign_id
            ORDER BY orphaned_count DESC
        """
        cur.execute(campaign_dist_query)
        campaign_dist = cur.fetchall()
        campaign_columns = [desc[0] for desc in cur.description]

        for row in campaign_dist:
            row_dict = dict(zip(campaign_columns, row))
            campaign_id = row_dict["campaign_id"]
            report["distribution_by_campaign"][str(campaign_id)] = {
                "orphaned_count": row_dict["orphaned_count"],
                "earliest_ranked": (
                    row_dict["earliest_ranked"].isoformat() if row_dict["earliest_ranked"] else None
                ),
                "latest_ranked": (
                    row_dict["latest_ranked"].isoformat() if row_dict["latest_ranked"] else None
                ),
            }

        # Query 3: Distribution by date (ranked_at)
        date_dist_query = """
            SELECT
                DATE(dr.ranked_at) as ranked_date,
                COUNT(*) as orphaned_count
            FROM marts.dim_ranking dr
            LEFT JOIN marts.fact_jobs fj
                ON dr.jsearch_job_id = fj.jsearch_job_id
                AND dr.campaign_id = fj.campaign_id
            WHERE fj.jsearch_job_id IS NULL
                AND dr.ranked_at IS NOT NULL
            GROUP BY DATE(dr.ranked_at)
            ORDER BY ranked_date DESC
        """
        cur.execute(date_dist_query)
        date_dist = cur.fetchall()
        date_columns = [desc[0] for desc in cur.description]

        for row in date_dist:
            row_dict = dict(zip(date_columns, row))
            ranked_date = row_dict["ranked_date"]
            report["distribution_by_date"][str(ranked_date)] = row_dict["orphaned_count"]

        # Query 4: Check if orphaned jsearch_job_id values exist in staging
        orphaned_job_ids = [r["jsearch_job_id"] for r in orphaned_data]
        if orphaned_job_ids:
            # Check in batches to avoid SQL parameter limits
            batch_size = 1000
            staging_found = set()
            staging_not_found = set()

            for i in range(0, len(orphaned_job_ids), batch_size):
                batch = orphaned_job_ids[i : i + batch_size]
                placeholders = ",".join(["%s"] * len(batch))

                staging_check_query = f"""
                    SELECT DISTINCT jsearch_job_id
                    FROM staging.jsearch_job_postings
                    WHERE jsearch_job_id IN ({placeholders})
                """
                cur.execute(staging_check_query, batch)
                found_ids = {row[0] for row in cur.fetchall()}
                staging_found.update(found_ids)

            staging_not_found = set(orphaned_job_ids) - staging_found

            report["staging_check"] = {
                "total_orphaned_job_ids": len(orphaned_job_ids),
                "found_in_staging": len(staging_found),
                "not_found_in_staging": len(staging_not_found),
                "percentage_in_staging": (
                    (len(staging_found) / len(orphaned_job_ids) * 100) if orphaned_job_ids else 0
                ),
            }

            # Root cause analysis
            if len(staging_found) > 0:
                report["root_cause_analysis"]["normalization_failure"] = (
                    f"{len(staging_found)} orphaned job IDs exist in staging but not in fact_jobs. This suggests normalization or dbt modelling failures."
                )
            if len(staging_not_found) > 0:
                report["root_cause_analysis"]["deleted_jobs"] = (
                    f"{len(staging_not_found)} orphaned job IDs don't exist in staging. These may have been deleted or never extracted."
                )
        else:
            report["staging_check"] = {
                "total_orphaned_job_ids": 0,
                "found_in_staging": 0,
                "not_found_in_staging": 0,
                "percentage_in_staging": 0,
            }

        # Additional root cause analysis
        if report["total_orphaned_rankings"] > 0:
            # Check if there's a pattern in dates (timing issues)
            if report["distribution_by_date"]:
                date_counts = list(report["distribution_by_date"].values())
                max_count = max(date_counts) if date_counts else 0
                if max_count > report["total_orphaned_rankings"] * 0.5:
                    report["root_cause_analysis"]["timing_issue"] = (
                        "Most orphaned rankings are concentrated in a single date, suggesting a timing issue in the ETL pipeline."
                    )

    return report


def print_report(report: dict):
    """Print analysis report to console.

    Args:
        report: Analysis report dictionary
    """
    print("\n" + "=" * 80)
    print("ORPHANED RANKINGS ANALYSIS REPORT")
    print("=" * 80)
    print(f"\nAnalysis Timestamp: {report['analysis_timestamp']}")
    print(f"\nTotal Orphaned Rankings: {report['total_orphaned_rankings']}")

    if report["total_orphaned_rankings"] == 0:
        print("\n[OK] No orphaned rankings found. Database is clean!")
        return

    # Distribution by campaign
    print("\n" + "-" * 80)
    print("Distribution by Campaign:")
    print("-" * 80)
    if report["distribution_by_campaign"]:
        for campaign_id, data in sorted(
            report["distribution_by_campaign"].items(),
            key=lambda x: x[1]["orphaned_count"],
            reverse=True,
        ):
            print(f"  Campaign {campaign_id}: {data['orphaned_count']} orphaned rankings")
            if data["earliest_ranked"]:
                print(f"    Earliest: {data['earliest_ranked']}")
            if data["latest_ranked"]:
                print(f"    Latest: {data['latest_ranked']}")
    else:
        print("  No campaign distribution data")

    # Distribution by date
    print("\n" + "-" * 80)
    print("Distribution by Date (ranked_at):")
    print("-" * 80)
    if report["distribution_by_date"]:
        for date_str, count in sorted(report["distribution_by_date"].items(), reverse=True)[
            :20
        ]:  # Show top 20 dates
            print(f"  {date_str}: {count} orphaned rankings")
        if len(report["distribution_by_date"]) > 20:
            print(f"  ... and {len(report['distribution_by_date']) - 20} more dates")
    else:
        print("  No date distribution data")

    # Staging check
    print("\n" + "-" * 80)
    print("Staging Layer Check:")
    print("-" * 80)
    staging = report["staging_check"]
    print(f"  Total orphaned job IDs: {staging['total_orphaned_job_ids']}")
    print(f"  Found in staging: {staging['found_in_staging']}")
    print(f"  Not found in staging: {staging['not_found_in_staging']}")
    print(f"  Percentage in staging: {staging['percentage_in_staging']:.2f}%")

    # Root cause analysis
    print("\n" + "-" * 80)
    print("Root Cause Analysis:")
    print("-" * 80)
    if report["root_cause_analysis"]:
        for cause, description in report["root_cause_analysis"].items():
            print(f"  {cause.replace('_', ' ').title()}: {description}")
    else:
        print("  No specific root causes identified")

    print("\n" + "=" * 80)


def main():
    """Main entry point for the analysis script."""
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)

    print("Analyzing orphaned rankings...")
    report = analyze_orphaned_rankings(database)

    # Print to console
    print_report(report)

    # Save to JSON file
    output_file = (
        Path(__file__).parent.parent / "project_documentation" / "orphaned_rankings_analysis.json"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n[INFO] Full report saved to: {output_file}")

    return 0 if report["total_orphaned_rankings"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
