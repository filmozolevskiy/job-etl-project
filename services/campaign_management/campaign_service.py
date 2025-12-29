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

        Returns:
            Next campaign_id to use
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_NEXT_CAMPAIGN_ID)
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
        min_salary: float | None = None,
        max_salary: float | None = None,
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
                    min_salary,
                    max_salary,
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
        min_salary: float | None = None,
        max_salary: float | None = None,
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
                    min_salary,
                    max_salary,
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
            if not isinstance(value, (int, float)):
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
        """Delete a campaign.

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

            # Delete campaign
            cur.execute(DELETE_CAMPAIGN, (campaign_id,))

        logger.info(f"Deleted campaign {campaign_id}: {campaign_name}")
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
