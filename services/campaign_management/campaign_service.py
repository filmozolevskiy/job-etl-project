"""Campaign Management Service.

Service for managing job search campaigns in marts.job_campaigns table.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from shared.database import Database

from .queries import (
    DELETE_CAMPAIGN,
    GET_ALL_CAMPAIGNS,
    GET_ALL_CAMPAIGNS_BY_USER,
    GET_CAMPAIGN_ACTIVE_STATUS,
    GET_CAMPAIGN_BY_ID,
    GET_CAMPAIGN_NAME,
    GET_CAMPAIGN_STATISTICS,
    GET_JOB_COUNTS_OVER_TIME,
    GET_NEXT_CAMPAIGN_ID,
    GET_RUN_HISTORY,
    INSERT_CAMPAIGN,
    TOGGLE_CAMPAIGN_ACTIVE,
    UPDATE_CAMPAIGN,
    UPDATE_CAMPAIGN_TRACKING_FIELDS,
    UPDATE_CAMPAIGN_TRACKING_STATUS_ONLY,
    UPDATE_LAST_NOTIFICATION_SENT,
)

logger = logging.getLogger(__name__)

# Ranking weights validation constants
WEIGHT_SUM_TOLERANCE = 0.1
MIN_WEIGHT = 0.0
MAX_WEIGHT = 100.0


class CampaignService:
    """Service for managing job search campaigns."""

    def __init__(self, database: Database):
        """Initialize the campaign service.

        Args:
            database: Database connection interface (implements Database protocol)
        """
        if not database:
            raise ValueError("Database is required")
        self.db = database

    def get_all_campaigns(self, user_id: int | None = None) -> list[dict[str, Any]]:
        """Get all campaigns from the database.

        Args:
            user_id: If provided, only returns campaigns for this user. If None, returns all campaigns.

        Returns:
            List of campaign dictionaries
        """
        with self.db.get_cursor() as cur:
            if user_id is not None:
                cur.execute(GET_ALL_CAMPAIGNS_BY_USER, (user_id,))
            else:
                cur.execute(GET_ALL_CAMPAIGNS)
            columns = [desc[0] for desc in cur.description]
            campaigns = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.debug(f"Retrieved {len(campaigns)} campaign(s)")
        return campaigns

    def get_campaign_by_id(self, campaign_id: int) -> dict[str, Any] | None:
        """Get a single campaign by ID.

        Normalizes ranking_weights JSONB field to dict if it's a string.

        Args:
            campaign_id: Campaign ID to retrieve

        Returns:
            Campaign dictionary or None if not found. ranking_weights field is normalized to dict or None.
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_CAMPAIGN_BY_ID, (campaign_id,))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                return None

            campaign = dict(zip(columns, row))

            # Normalize ranking_weights: convert JSON string to dict if needed
            ranking_weights = campaign.get("ranking_weights")
            if ranking_weights:
                if isinstance(ranking_weights, str):
                    try:
                        campaign["ranking_weights"] = json.loads(ranking_weights)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(
                            f"Failed to parse ranking_weights JSON for campaign {campaign_id}, setting to None"
                        )
                        campaign["ranking_weights"] = None
                elif not isinstance(ranking_weights, dict):
                    logger.warning(
                        f"Invalid ranking_weights type for campaign {campaign_id}, setting to None"
                    )
                    campaign["ranking_weights"] = None

            return campaign

    def get_next_campaign_id(self) -> int:
        """Get the next available campaign_id.

        Uses sequence if available, otherwise falls back to MAX+1 for backwards compatibility.

        Returns:
            Next campaign_id to use
        """
        try:
            # Try to use sequence (preferred method)
            with self.db.get_cursor() as cur:
                cur.execute(GET_NEXT_CAMPAIGN_ID)
                result = cur.fetchone()
                return result[0] if result else 1
        except Exception as e:
            # Fallback to old method if sequence doesn't exist yet
            logger.warning(
                f"Sequence not available, falling back to MAX+1 method: {e}. "
                "Run migration script 99_fix_campaign_id_uniqueness.sql to fix."
            )
            with self.db.get_cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(campaign_id), 0) + 1 FROM marts.job_campaigns")
                result = cur.fetchone()
                return result[0] if result else 1

    def create_campaign(
        self,
        campaign_name: str,
        query: str,
        country: str,
        user_id: int,
        location: str | None = None,
        date_window: str = "week",
        email: str | None = None,
        skills: str | None = None,
        min_salary: float | int | None = None,  # Accept float/int, stored as integer (yearly)
        max_salary: float | int | None = None,  # Accept float/int, stored as integer (yearly)
        currency: str | None = None,
        remote_preference: str | None = None,
        seniority: str | None = None,
        company_size_preference: str | None = None,
        employment_type_preference: str | None = None,
        ranking_weights: dict[str, float] | None = None,
        is_active: bool = True,
    ) -> int:
        """Create a new campaign.

        Args:
            campaign_name: Name of the campaign
            query: Search query string
            country: Country code (lowercase)
            user_id: User ID who owns this campaign
            location: Location string (optional)
            date_window: Date window for job postings (default: "week")
            email: Email address (optional)
            skills: Skills string (optional)
            min_salary: Minimum salary (optional)
            max_salary: Maximum salary (optional)
            currency: Currency code for salary (e.g., 'USD', 'CAD', 'EUR') (optional)
            remote_preference: Remote preference (optional)
            seniority: Seniority level (optional)
            company_size_preference: Company size preference (optional)
            employment_type_preference: Employment type preference (optional)
            ranking_weights: Dictionary of ranking weights as percentages (optional, defaults to config values)
                Format: {"location_match": 15.0, "salary_match": 15.0, ...}
            is_active: Whether campaign is active (default: True)

        Returns:
            Created campaign_id

        Raises:
            ValueError: If required fields are missing
        """
        if not campaign_name:
            raise ValueError("Campaign name is required")
        if not query:
            raise ValueError("Search query is required")
        if not country:
            raise ValueError("Country is required")
        if not user_id:
            raise ValueError("User ID is required")

        campaign_id = self.get_next_campaign_id()
        now = datetime.now()

        # Validate ranking weights if provided
        if ranking_weights:
            self._validate_ranking_weights(ranking_weights)

        with self.db.get_cursor() as cur:
            # Normalize currency to uppercase if provided
            currency_normalized = currency.upper().strip() if currency else None

            # Convert ranking_weights dict to JSON string if provided
            ranking_weights_json = json.dumps(ranking_weights) if ranking_weights else None

            # Convert salaries to integers (yearly amounts)
            min_salary_int = int(round(min_salary)) if min_salary is not None else None
            max_salary_int = int(round(max_salary)) if max_salary is not None else None

            cur.execute(
                INSERT_CAMPAIGN,
                (
                    campaign_id,
                    user_id,
                    campaign_name,
                    is_active,
                    query,
                    location,
                    country.lower(),
                    date_window,
                    email if email else None,
                    skills if skills else None,
                    min_salary_int,
                    max_salary_int,
                    currency_normalized,
                    remote_preference if remote_preference else None,
                    seniority if seniority else None,
                    company_size_preference if company_size_preference else None,
                    employment_type_preference if employment_type_preference else None,
                    ranking_weights_json,
                    now,
                    now,
                ),
            )
            # Get the actual campaign_id that was inserted (in case SERIAL was used)
            result = cur.fetchone()
            if result and result[0]:
                campaign_id = result[0]

        logger.info(f"Created campaign {campaign_id}: {campaign_name}")
        return campaign_id

    def update_campaign(
        self,
        campaign_id: int,
        campaign_name: str,
        query: str,
        country: str,
        location: str | None = None,
        date_window: str = "week",
        email: str | None = None,
        skills: str | None = None,
        min_salary: float | int | None = None,  # Accept float/int, stored as integer (yearly)
        max_salary: float | int | None = None,  # Accept float/int, stored as integer (yearly)
        currency: str | None = None,
        remote_preference: str | None = None,
        seniority: str | None = None,
        company_size_preference: str | None = None,
        employment_type_preference: str | None = None,
        ranking_weights: dict[str, float] | None = None,
        is_active: bool = True,
    ) -> None:
        """Update an existing campaign.

        Args:
            campaign_id: Campaign ID to update
            campaign_name: Name of the campaign
            query: Search query string
            country: Country code (lowercase)
            location: Location string (optional)
            date_window: Date window for job postings (default: "week")
            email: Email address (optional)
            skills: Skills string (optional)
            min_salary: Minimum salary (optional)
            max_salary: Maximum salary (optional)
            currency: Currency code for salary (e.g., 'USD', 'CAD', 'EUR') (optional)
            remote_preference: Remote preference (optional)
            seniority: Seniority level (optional)
            company_size_preference: Company size preference (optional)
            employment_type_preference: Employment type preference (optional)
            ranking_weights: Dictionary of ranking weights as percentages (optional)
                Format: {"location_match": 15.0, "salary_match": 15.0, ...}
            is_active: Whether campaign is active

        Raises:
            ValueError: If required fields are missing or campaign not found
        """
        if not campaign_name:
            raise ValueError("Campaign name is required")
        if not query:
            raise ValueError("Search query is required")
        if not country:
            raise ValueError("Country is required")

        # Check if campaign exists
        if not self.get_campaign_by_id(campaign_id):
            raise ValueError(f"Campaign {campaign_id} not found")

        # Validate ranking weights if provided
        if ranking_weights:
            self._validate_ranking_weights(ranking_weights)

        # Normalize currency to uppercase if provided
        currency_normalized = currency.upper().strip() if currency else None

        # Convert ranking_weights dict to JSON string if provided
        ranking_weights_json = json.dumps(ranking_weights) if ranking_weights else None

        # Convert salaries to integers (yearly amounts)
        min_salary_int = int(round(min_salary)) if min_salary is not None else None
        max_salary_int = int(round(max_salary)) if max_salary is not None else None

        with self.db.get_cursor() as cur:
            cur.execute(
                UPDATE_CAMPAIGN,
                (
                    campaign_name,
                    is_active,
                    query,
                    location,
                    country.lower(),
                    date_window,
                    email if email else None,
                    skills if skills else None,
                    min_salary_int,
                    max_salary_int,
                    currency_normalized,
                    remote_preference if remote_preference else None,
                    seniority if seniority else None,
                    company_size_preference if company_size_preference else None,
                    employment_type_preference if employment_type_preference else None,
                    ranking_weights_json,
                    datetime.now(),
                    campaign_id,
                ),
            )

        logger.info(f"Updated campaign {campaign_id}: {campaign_name}")

    def get_dashboard_stats(self, user_id: int | None = None) -> dict[str, Any]:
        """Get overall dashboard statistics.

        Args:
            user_id: If provided, only returns stats for this user. If None, returns all stats.

        Returns:
            Dictionary with dashboard statistics
        """
        with self.db.get_cursor() as cur:
            # Base query for counts
            if user_id is not None:
                cur.execute(
                    "SELECT COUNT(*), SUM(CASE WHEN is_active THEN 1 ELSE 0 END) FROM marts.job_campaigns WHERE user_id = %s",
                    (user_id,),
                )
            else:
                cur.execute(
                    "SELECT COUNT(*), SUM(CASE WHEN is_active THEN 1 ELSE 0 END) FROM marts.job_campaigns"
                )

            total_campaigns, active_campaigns = cur.fetchone()

            # Jobs processed count (total ranked jobs)
            if user_id is not None:
                cur.execute(
                    "SELECT COUNT(*) FROM marts.dim_ranking dr JOIN marts.job_campaigns jc ON dr.campaign_id = jc.campaign_id WHERE jc.user_id = %s",
                    (user_id,),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM marts.dim_ranking")
            jobs_processed = cur.fetchone()[0]

            # Success rate (applied / total)
            if user_id is not None:
                cur.execute(
                    "SELECT COUNT(*), SUM(CASE WHEN status != 'waiting' THEN 1 ELSE 0 END) FROM marts.user_job_status WHERE user_id = %s",
                    (user_id,),
                )
            else:
                cur.execute(
                    "SELECT COUNT(*), SUM(CASE WHEN status != 'waiting' THEN 1 ELSE 0 END) FROM marts.user_job_status"
                )
            total_jobs, applied_jobs = cur.fetchone()
            success_rate = (
                round((applied_jobs / total_jobs * 100), 1) if total_jobs and total_jobs > 0 else 0
            )

            # Activity data (last 7 days)
            activity_data = []
            if user_id is not None:
                cur.execute(
                    """
                    SELECT
                        d.date,
                        COALESCE(f.found, 0) as found,
                        COALESCE(a.applied, 0) as applied
                    FROM (
                        SELECT CURRENT_DATE - i as date
                        FROM generate_series(0, 6) i
                    ) d
                    LEFT JOIN (
                        SELECT DATE(run_timestamp) as date, SUM(rows_processed_raw) as found
                        FROM marts.etl_run_metrics erm
                        JOIN marts.job_campaigns jc ON erm.campaign_id = jc.campaign_id
                        WHERE jc.user_id = %s AND erm.task_name = 'extract_job_postings'
                        GROUP BY 1
                    ) f ON d.date = f.date
                    LEFT JOIN (
                        SELECT DATE(created_at) as date, COUNT(*) as applied
                        FROM marts.user_job_status
                        WHERE user_id = %s AND status != 'waiting'
                        GROUP BY 1
                    ) a ON d.date = a.date
                    ORDER BY d.date ASC
                    """,
                    (user_id, user_id),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        d.date,
                        COALESCE(f.found, 0) as found,
                        COALESCE(a.applied, 0) as applied
                    FROM (
                        SELECT CURRENT_DATE - i as date
                        FROM generate_series(0, 6) i
                    ) d
                    LEFT JOIN (
                        SELECT DATE(run_timestamp) as date, SUM(rows_processed_raw) as found
                        FROM marts.etl_run_metrics erm
                        WHERE erm.task_name = 'extract_job_postings'
                        GROUP BY 1
                    ) f ON d.date = f.date
                    LEFT JOIN (
                        SELECT DATE(created_at) as date, COUNT(*) as applied
                        FROM marts.user_job_status
                        WHERE status != 'waiting'
                        GROUP BY 1
                    ) a ON d.date = a.date
                    ORDER BY d.date ASC
                    """
                )

            rows = cur.fetchall()
            activity_data = [
                {"date": r[0].isoformat(), "found": int(r[1]), "applied": int(r[2])} for r in rows
            ]

            return {
                "total_campaigns": total_campaigns or 0,
                "active_campaigns": active_campaigns or 0,
                "jobs_processed": jobs_processed or 0,
                "success_rate": success_rate,
                "activity_data": activity_data,
            }

    def _validate_ranking_weights(self, ranking_weights: dict[str, float]) -> None:
        """Validate ranking weights dictionary.

        Args:
            ranking_weights: Dictionary of weights to validate

        Raises:
            ValueError: If weights are invalid (invalid keys, out of range, or don't sum to 100%)
        """
        if not ranking_weights:
            return

        # Get expected keys from default scoring weights
        # We need to load them to check, but we'll use a simple check
        expected_keys = {
            "location_match",
            "salary_match",
            "company_size_match",
            "skills_match",
            "keyword_match",
            "employment_type_match",
            "seniority_match",
            "remote_type_match",
            "recency",
        }
        provided_keys = set(ranking_weights.keys())

        if not provided_keys.issubset(expected_keys):
            invalid_keys = provided_keys - expected_keys
            raise ValueError(
                f"Invalid ranking weight keys: {', '.join(sorted(invalid_keys))}. "
                f"Allowed keys: {', '.join(sorted(expected_keys))}"
            )

        # Validate values are in range
        for key, value in ranking_weights.items():
            if not isinstance(value, int | float):
                raise ValueError(
                    f"Ranking weight for '{key}' must be numeric, got {type(value).__name__}"
                )
            if value < MIN_WEIGHT or value > MAX_WEIGHT:
                raise ValueError(
                    f"Ranking weight for '{key}' must be between {MIN_WEIGHT} and {MAX_WEIGHT}, got {value}"
                )

        # Validate sum
        total = sum(ranking_weights.values())
        if abs(total - 100.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"Ranking weights must sum to 100%. Current total: {total:.1f}%")

    def toggle_active(self, campaign_id: int) -> bool:
        """Toggle is_active status of a campaign.

        Args:
            campaign_id: Campaign ID to toggle

        Returns:
            New is_active status (True or False)

        Raises:
            ValueError: If campaign not found
        """
        # Get current status
        with self.db.get_cursor() as cur:
            cur.execute(GET_CAMPAIGN_ACTIVE_STATUS, (campaign_id,))
            result = cur.fetchone()

            if not result:
                raise ValueError(f"Campaign {campaign_id} not found")

            new_status = not result[0]

            # Update status
            cur.execute(TOGGLE_CAMPAIGN_ACTIVE, (new_status, datetime.now(), campaign_id))

        logger.info(f"Toggled campaign {campaign_id} active status to {new_status}")
        return new_status

    def delete_campaign(self, campaign_id: int) -> str:
        """Delete a campaign and all related data.

        This method ensures complete cleanup of campaign-related data:
        - Rankings (deleted via CASCADE DELETE if FK constraint exists)
        - Fact jobs (manually deleted since dbt table may not have FK)
        - ETL metrics (deleted via CASCADE DELETE if FK constraint exists)
        - User job status (deleted via CASCADE DELETE if FK constraint exists)
        - Job notes (deleted via CASCADE DELETE if FK constraint exists)
        - Staging jobs (deleted via campaign_id filter)
        - Raw jobs (deleted via campaign_id filter)
        - ChatGPT enrichments (deleted via join to staging jobs)

        Args:
            campaign_id: Campaign ID to delete

        Returns:
            Deleted campaign name

        Raises:
            ValueError: If campaign not found
        """
        # Get campaign name for return value
        with self.db.get_cursor() as cur:
            cur.execute(GET_CAMPAIGN_NAME, (campaign_id,))
            result = cur.fetchone()

            if not result:
                raise ValueError(f"Campaign {campaign_id} not found")

            campaign_name = result[0]

            # Manual cleanup for tables without FK constraints or CASCADE DELETE
            # This ensures data is removed even if FK constraints aren't set up yet
            # Handle missing tables gracefully (e.g., fact_jobs created by dbt)
            # Use savepoints to handle errors without aborting the entire transaction

            fact_jobs_deleted = 0
            staging_jobs_deleted = 0
            enrichments_deleted = 0
            raw_jobs_deleted = 0

            # Delete fact_jobs for this campaign (dbt table, may not exist)
            cur.execute("SAVEPOINT before_fact_jobs_delete")
            try:
                cur.execute(
                    "DELETE FROM marts.fact_jobs WHERE campaign_id = %s",
                    (campaign_id,),
                )
                fact_jobs_deleted = cur.rowcount
                cur.execute("RELEASE SAVEPOINT before_fact_jobs_delete")
            except Exception as e:
                # Table might not exist (created by dbt) - that's okay
                cur.execute("ROLLBACK TO SAVEPOINT before_fact_jobs_delete")
                logger.debug(f"Could not delete fact_jobs (table may not exist): {e}")

            # Delete staging jobs for this campaign
            cur.execute("SAVEPOINT before_staging_jobs_delete")
            try:
                cur.execute(
                    "DELETE FROM staging.jsearch_job_postings WHERE campaign_id = %s",
                    (campaign_id,),
                )
                staging_jobs_deleted = cur.rowcount
                cur.execute("RELEASE SAVEPOINT before_staging_jobs_delete")
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT before_staging_jobs_delete")
                logger.debug(f"Could not delete staging jobs (table may not exist): {e}")

            # Delete staging ChatGPT enrichments for jobs in this campaign
            # (via join to staging.jsearch_job_postings)
            cur.execute("SAVEPOINT before_enrichments_delete")
            try:
                cur.execute(
                    """
                    DELETE FROM staging.chatgpt_enrichments ce
                    WHERE EXISTS (
                        SELECT 1 FROM staging.jsearch_job_postings jp
                        WHERE jp.jsearch_job_postings_key = ce.jsearch_job_postings_key
                        AND jp.campaign_id = %s
                    )
                    """,
                    (campaign_id,),
                )
                enrichments_deleted = cur.rowcount
                cur.execute("RELEASE SAVEPOINT before_enrichments_delete")
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT before_enrichments_delete")
                logger.debug(f"Could not delete enrichments (table may not exist): {e}")

            # Delete raw jobs for this campaign
            cur.execute("SAVEPOINT before_raw_jobs_delete")
            try:
                cur.execute(
                    "DELETE FROM raw.jsearch_job_postings WHERE campaign_id = %s",
                    (campaign_id,),
                )
                raw_jobs_deleted = cur.rowcount
                cur.execute("RELEASE SAVEPOINT before_raw_jobs_delete")
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT before_raw_jobs_delete")
                logger.debug(f"Could not delete raw jobs (table may not exist): {e}")

            # Delete campaign (this will CASCADE DELETE:
            # - marts.dim_ranking (if FK constraint exists)
            # - marts.etl_run_metrics (if FK constraint exists)
            cur.execute(DELETE_CAMPAIGN, (campaign_id,))

            logger.info(
                f"Deleted campaign {campaign_id}: {campaign_name}. "
                f"Cleanup: {fact_jobs_deleted} fact_jobs, {staging_jobs_deleted} staging_jobs, "
                f"{enrichments_deleted} enrichments, {raw_jobs_deleted} raw_jobs"
            )

        return campaign_name

    def update_tracking_fields(
        self,
        campaign_id: int,
        status: str,
        job_count: int,
        increment_run_count: bool = True,
    ) -> None:
        """Update campaign tracking fields after a DAG run.

        Updates:
        - last_run_at: Current timestamp
        - last_run_status: 'success' or 'error'
        - last_run_job_count: Number of jobs extracted/ranked (if increment_run_count=True)
        - total_run_count: Incremented by 1 (if increment_run_count=True)

        Args:
            campaign_id: Campaign ID to update
            status: Run status ('success' or 'error')
            job_count: Number of jobs processed for this campaign
            increment_run_count: Whether to increment total_run_count (default: True)

        Raises:
            ValueError: If status is not 'success' or 'error'
        """
        if status not in ("success", "error"):
            raise ValueError(f"Status must be 'success' or 'error', got: {status}")

        try:
            with self.db.get_cursor() as cur:
                if increment_run_count:
                    cur.execute(
                        UPDATE_CAMPAIGN_TRACKING_FIELDS,
                        (status, job_count, campaign_id),
                    )
                else:
                    cur.execute(
                        UPDATE_CAMPAIGN_TRACKING_STATUS_ONLY,
                        (status, campaign_id),
                    )

            logger.debug(
                f"Updated tracking fields for campaign {campaign_id}: "
                f"status={status}, job_count={job_count if increment_run_count else 'preserved'}"
            )
        except Exception as e:
            logger.error(
                f"Failed to update tracking fields for campaign {campaign_id}: {e}",
                exc_info=True,
            )
            # Don't raise - tracking field updates shouldn't fail the DAG
            raise

    def update_last_notification_sent(self, campaign_id: int) -> None:
        """Update last_notification_sent_at timestamp for a campaign.

        Args:
            campaign_id: Campaign ID to update
        """
        try:
            with self.db.get_cursor() as cur:
                cur.execute(UPDATE_LAST_NOTIFICATION_SENT, (campaign_id,))
            logger.debug(f"Updated last_notification_sent_at for campaign {campaign_id}")
        except Exception as e:
            logger.error(
                f"Failed to update last_notification_sent_at for campaign {campaign_id}: {e}",
                exc_info=True,
            )
            # Don't raise - tracking field updates shouldn't fail the DAG
            raise

    def get_campaign_statistics(self, campaign_id: int) -> dict[str, Any] | None:
        """Get statistics for a campaign.

        Args:
            campaign_id: Campaign ID to get statistics for

        Returns:
            Dictionary with statistics or None if campaign not found
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_CAMPAIGN_STATISTICS, (campaign_id,))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                return None

            stats = dict(zip(columns, row))
            # Calculate success rate
            total_runs = stats.get("total_etl_runs", 0) or 0
            successful_runs = stats.get("successful_runs", 0) or 0
            if total_runs > 0:
                stats["success_rate"] = round((successful_runs / total_runs) * 100, 1)
            else:
                stats["success_rate"] = 0.0

            return stats

    def get_run_history(self, campaign_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """Get run history for a campaign.

        Args:
            campaign_id: Campaign ID to get run history for
            limit: Maximum number of runs to return (default: 20)

        Returns:
            List of run history dictionaries
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_RUN_HISTORY, (campaign_id,))
            columns = [desc[0] for desc in cur.description]
            runs = [dict(zip(columns, row)) for row in cur.fetchall()]

            return runs

    def get_job_counts_over_time(self, campaign_id: int, days: int = 30) -> list[dict[str, Any]]:
        """Get job counts over time for a campaign.

        Args:
            campaign_id: Campaign ID to get job counts for
            days: Number of days to look back (default: 30)

        Returns:
            List of dictionaries with run_date and job_count
        """
        with self.db.get_cursor() as cur:
            # Modify query to use days parameter
            query = GET_JOB_COUNTS_OVER_TIME.replace("30 days", f"{days} days")
            cur.execute(query, (campaign_id,))
            columns = [desc[0] for desc in cur.description]
            counts = [dict(zip(columns, row)) for row in cur.fetchall()]

            return counts

    def get_campaign_status_from_metrics(
        self, campaign_id: int, dag_run_id: str | None = None
    ) -> dict[str, Any]:
        """Get campaign status by querying etl_run_metrics.

        Derives status from the most recent DAG run's task statuses.
        Returns 'success' if all critical tasks succeeded, 'error' if any failed,
        'running' if some tasks are in progress, or 'pending' if no tasks have run.

        Args:
            campaign_id: Campaign ID
            dag_run_id: Optional specific DAG run ID (uses most recent if None)

        Returns:
            Dictionary with:
            - status: 'success', 'error', 'pending', or 'running'
            - completed_tasks: list of completed task names
            - failed_tasks: list of failed task names (if any)
            - dag_run_id: the DAG run ID being checked
            - is_complete: boolean indicating if DAG run is finished
            - jobs_available: boolean indicating if jobs are available (rank_jobs completed)
        """
        # Critical tasks that determine campaign success
        # Note: send_notifications is no longer critical - jobs are available after rank_jobs
        critical_tasks = [
            "extract_job_postings",
            "normalize_jobs",
            "rank_jobs",
        ]

        if dag_run_id:
            # Query specific DAG run
            # Build IN clause with placeholders for better psycopg2 compatibility
            placeholders = ",".join(["%s"] * len(critical_tasks))
            query = f"""
                SELECT DISTINCT ON (task_name) task_name, task_status
                FROM marts.etl_run_metrics
                WHERE campaign_id = %s
                    AND dag_run_id = %s
                    AND task_name IN ({placeholders})
                ORDER BY task_name, run_timestamp DESC
            """
            params = (campaign_id, dag_run_id) + tuple(critical_tasks)
        else:
            # Query most recent DAG run
            placeholders = ",".join(["%s"] * len(critical_tasks))
            query = f"""
                WITH latest_run AS (
                    SELECT dag_run_id
                    FROM marts.etl_run_metrics
                    WHERE campaign_id = %s
                    GROUP BY dag_run_id
                    ORDER BY MAX(run_timestamp) DESC
                    LIMIT 1
                )
                SELECT DISTINCT ON (task_name) task_name, task_status
                FROM marts.etl_run_metrics
                WHERE campaign_id = %s
                    AND dag_run_id = (SELECT dag_run_id FROM latest_run)
                    AND dag_run_id IS NOT NULL
                    AND task_name IN ({placeholders})
                ORDER BY task_name, run_timestamp DESC
            """
            params = (campaign_id, campaign_id) + tuple(critical_tasks)

        try:
            # Query for task statuses directly
            logger.info(
                f"Querying status for campaign {campaign_id}, dag_run_id: {dag_run_id}, "
                f"critical_tasks: {critical_tasks}"
            )
            logger.info(f"Query: {query}")
            logger.info(f"Params: {params}")
            with self.db.get_cursor() as cur:
                try:
                    cur.execute(query, params)
                    task_statuses = cur.fetchall()
                    logger.info(
                        f"Query executed successfully. Found {len(task_statuses)} task statuses for campaign {campaign_id}, dag_run_id: {dag_run_id}"
                    )
                    if task_statuses:
                        logger.info(f"Task statuses: {task_statuses}")
                    else:
                        logger.warning(
                            f"No task statuses found! Query returned empty for campaign {campaign_id}, "
                            f"dag_run_id: {dag_run_id}. Query: {query}, Params: {params}"
                        )
                        # Try a direct query to verify data exists
                        cur.execute(
                            "SELECT task_name, task_status FROM marts.etl_run_metrics WHERE campaign_id = %s AND dag_run_id = %s LIMIT 5",
                            (campaign_id, dag_run_id),
                        )
                        all_tasks = cur.fetchall()
                        logger.warning(f"All tasks for this dag_run_id: {all_tasks}")
                except Exception as query_error:
                    logger.error(
                        f"Error executing query for campaign {campaign_id}: {query_error}",
                        exc_info=True,
                    )
                    # If query fails, check if metrics exist at all
                    task_statuses = []

                # If no tasks found, check if metrics exist
                if not task_statuses:
                    if dag_run_id:
                        # Check if this specific dag_run_id has any data (might be too early)
                        cur.execute(
                            "SELECT COUNT(*) FROM marts.etl_run_metrics WHERE campaign_id = %s AND dag_run_id = %s",
                            (campaign_id, dag_run_id),
                        )
                        metrics_count = cur.fetchone()[0]
                        if metrics_count == 0:
                            # DAG was triggered but metrics not written yet - return pending with dag_run_id
                            logger.debug(
                                f"DAG {dag_run_id} triggered but no metrics written yet for campaign {campaign_id}"
                            )
                            return {
                                "status": "pending",
                                "completed_tasks": [],
                                "failed_tasks": [],
                                "dag_run_id": dag_run_id,
                                "is_complete": False,
                                "jobs_available": False,
                            }
                    else:
                        # Check if there's any metrics data for this campaign
                        cur.execute(
                            "SELECT COUNT(*) FROM marts.etl_run_metrics WHERE campaign_id = %s",
                            (campaign_id,),
                        )
                        metrics_count = cur.fetchone()[0]

                        # If no metrics data exists at all, return pending status
                        if metrics_count == 0:
                            logger.debug(
                                f"No metrics data found for campaign {campaign_id} - DAG has not been run yet"
                            )
                            return {
                                "status": "pending",
                                "completed_tasks": [],
                                "failed_tasks": [],
                                "dag_run_id": None,
                                "is_complete": False,
                                "jobs_available": False,
                            }

                # If no tasks found for critical tasks, but metrics exist, return pending
                if not task_statuses:
                    logger.debug(
                        f"No critical tasks found for campaign {campaign_id}, dag_run {dag_run_id or 'latest'}"
                    )
                    return {
                        "status": "pending",
                        "completed_tasks": [],
                        "failed_tasks": [],
                        "dag_run_id": dag_run_id,  # Preserve the provided dag_run_id
                        "is_complete": False,
                        "jobs_available": False,
                    }

                # Extract task information (deduplicate by task_name)
                completed_tasks = []
                failed_tasks = []
                found_dag_run_id = dag_run_id
                seen_tasks = set()  # Track seen tasks to avoid duplicates

                for task_name, task_status in task_statuses:
                    # Skip if we've already seen this task (shouldn't happen with DISTINCT ON, but safety check)
                    if task_name in seen_tasks:
                        continue
                    seen_tasks.add(task_name)

                    if task_status == "success":
                        completed_tasks.append(task_name)
                    elif task_status == "failed":
                        failed_tasks.append(task_name)

                # Get dag_run_id from query if not provided
                if not found_dag_run_id:
                    # Re-query to get dag_run_id from the latest run
                    try:
                        with self.db.get_cursor() as cur2:
                            cur2.execute(
                                """
                                SELECT dag_run_id
                                FROM marts.etl_run_metrics
                                WHERE campaign_id = %s
                                    AND dag_run_id IS NOT NULL
                                GROUP BY dag_run_id
                                ORDER BY MAX(run_timestamp) DESC
                                LIMIT 1
                            """,
                                (campaign_id,),
                            )
                            result = cur2.fetchone()
                            if result:
                                found_dag_run_id = result[0]
                                logger.info(
                                    f"Retrieved dag_run_id {found_dag_run_id} for campaign {campaign_id}"
                                )
                    except Exception as e:
                        logger.warning(
                            f"Could not retrieve dag_run_id for campaign {campaign_id}: {e}"
                        )
                        # Continue with None - it's not critical

                # Check if jobs are available (rank_jobs completed)
                jobs_available = "rank_jobs" in completed_tasks

                # Determine overall status
                if failed_tasks:
                    status = "error"
                    is_complete = True
                elif len(completed_tasks) == len(critical_tasks):
                    # All critical tasks completed successfully
                    status = "success"
                    is_complete = True
                elif len(completed_tasks) > 0:
                    # Some tasks complete, others still pending
                    status = "running"
                    is_complete = False
                else:
                    # No tasks have completed yet
                    status = "pending"
                    is_complete = False

                logger.debug(
                    f"Campaign {campaign_id} status: {status} "
                    f"(completed: {len(completed_tasks)}, failed: {len(failed_tasks)}, "
                    f"jobs_available: {jobs_available})"
                )

                return {
                    "status": status,
                    "completed_tasks": completed_tasks,
                    "failed_tasks": failed_tasks,
                    "dag_run_id": found_dag_run_id
                    or dag_run_id,  # Preserve provided dag_run_id if found_dag_run_id is None
                    "is_complete": is_complete,
                    "jobs_available": jobs_available,
                }

        except Exception as e:
            # Log the error and return appropriate status
            logger.debug(
                f"Could not get campaign status from metrics for campaign {campaign_id}: {e}"
            )
            # Only log as error if it's a real database issue, not just missing data
            if "relation" in str(e).lower() or "does not exist" in str(e).lower():
                logger.error(
                    f"Database error getting campaign status: {e}",
                    exc_info=True,
                )
                return {
                    "status": "error",
                    "completed_tasks": [],
                    "failed_tasks": [],
                    "dag_run_id": dag_run_id,
                    "is_complete": False,
                    "jobs_available": False,
                }
            # For other exceptions (likely no data or connection issues), return error status
            logger.warning(
                f"Exception getting campaign status for campaign {campaign_id}: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "completed_tasks": [],
                "failed_tasks": [],
                "dag_run_id": dag_run_id,
                "is_complete": False,
                "jobs_available": False,
            }
