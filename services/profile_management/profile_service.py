"""Profile Management Service.

Service for managing job search profiles in marts.profile_preferences table.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from shared.database import Database

from .queries import (
    DELETE_PROFILE,
    GET_ALL_PROFILES,
    GET_JOB_COUNTS_OVER_TIME,
    GET_NEXT_PROFILE_ID,
    GET_PROFILE_ACTIVE_STATUS,
    GET_PROFILE_BY_ID,
    GET_PROFILE_NAME,
    GET_PROFILE_STATISTICS,
    GET_RUN_HISTORY,
    INSERT_PROFILE,
    TOGGLE_PROFILE_ACTIVE,
    UPDATE_PROFILE,
    UPDATE_PROFILE_TRACKING_FIELDS,
    UPDATE_PROFILE_TRACKING_STATUS_ONLY,
)

logger = logging.getLogger(__name__)

# Ranking weights validation constants
WEIGHT_SUM_TOLERANCE = 0.1
MIN_WEIGHT = 0.0
MAX_WEIGHT = 100.0


class ProfileService:
    """Service for managing job search profiles."""

    def __init__(self, database: Database):
        """Initialize the profile service.

        Args:
            database: Database connection interface (implements Database protocol)
        """
        if not database:
            raise ValueError("Database is required")
        self.db = database

    def get_all_profiles(self) -> list[dict[str, Any]]:
        """Get all profiles from the database.

        Returns:
            List of profile dictionaries
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_ALL_PROFILES)
            columns = [desc[0] for desc in cur.description]
            profiles = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.debug(f"Retrieved {len(profiles)} profile(s)")
        return profiles

    def get_profile_by_id(self, profile_id: int) -> dict[str, Any] | None:
        """Get a single profile by ID.

        Normalizes ranking_weights JSONB field to dict if it's a string.

        Args:
            profile_id: Profile ID to retrieve

        Returns:
            Profile dictionary or None if not found. ranking_weights field is normalized to dict or None.
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_PROFILE_BY_ID, (profile_id,))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                return None

            profile = dict(zip(columns, row))

            # Normalize ranking_weights: convert JSON string to dict if needed
            ranking_weights = profile.get("ranking_weights")
            if ranking_weights:
                if isinstance(ranking_weights, str):
                    try:
                        profile["ranking_weights"] = json.loads(ranking_weights)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(
                            f"Failed to parse ranking_weights JSON for profile {profile_id}, setting to None"
                        )
                        profile["ranking_weights"] = None
                elif not isinstance(ranking_weights, dict):
                    logger.warning(
                        f"Invalid ranking_weights type for profile {profile_id}, setting to None"
                    )
                    profile["ranking_weights"] = None

            return profile

    def get_next_profile_id(self) -> int:
        """Get the next available profile_id.

        Returns:
            Next profile_id to use
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_NEXT_PROFILE_ID)
            result = cur.fetchone()
            return result[0] if result else 1

    def create_profile(
        self,
        profile_name: str,
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
    ) -> int:
        """Create a new profile.

        Args:
            profile_name: Name of the profile
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
            ranking_weights: Dictionary of ranking weights as percentages (optional, defaults to config values)
                Format: {"location_match": 15.0, "salary_match": 15.0, ...}
            is_active: Whether profile is active (default: True)

        Returns:
            Created profile_id

        Raises:
            ValueError: If required fields are missing
        """
        if not profile_name:
            raise ValueError("Profile name is required")
        if not query:
            raise ValueError("Search query is required")
        if not country:
            raise ValueError("Country is required")

        profile_id = self.get_next_profile_id()
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
                INSERT_PROFILE,
                (
                    profile_id,
                    profile_name,
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

        logger.info(f"Created profile {profile_id}: {profile_name}")
        return profile_id

    def update_profile(
        self,
        profile_id: int,
        profile_name: str,
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
        """Update an existing profile.

        Args:
            profile_id: Profile ID to update
            profile_name: Name of the profile
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
            is_active: Whether profile is active

        Raises:
            ValueError: If required fields are missing or profile not found
        """
        if not profile_name:
            raise ValueError("Profile name is required")
        if not query:
            raise ValueError("Search query is required")
        if not country:
            raise ValueError("Country is required")

        # Check if profile exists
        if not self.get_profile_by_id(profile_id):
            raise ValueError(f"Profile {profile_id} not found")

        # Validate ranking weights if provided
        if ranking_weights:
            self._validate_ranking_weights(ranking_weights)

        # Normalize currency to uppercase if provided
        currency_normalized = currency.upper().strip() if currency else None

        # Convert ranking_weights dict to JSON string if provided
        ranking_weights_json = json.dumps(ranking_weights) if ranking_weights else None

        with self.db.get_cursor() as cur:
            cur.execute(
                UPDATE_PROFILE,
                (
                    profile_name,
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
                    profile_id,
                ),
            )

        logger.info(f"Updated profile {profile_id}: {profile_name}")

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

    def toggle_active(self, profile_id: int) -> bool:
        """Toggle is_active status of a profile.

        Args:
            profile_id: Profile ID to toggle

        Returns:
            New is_active status (True or False)

        Raises:
            ValueError: If profile not found
        """
        # Get current status
        with self.db.get_cursor() as cur:
            cur.execute(GET_PROFILE_ACTIVE_STATUS, (profile_id,))
            result = cur.fetchone()

            if not result:
                raise ValueError(f"Profile {profile_id} not found")

            new_status = not result[0]

            # Update status
            cur.execute(TOGGLE_PROFILE_ACTIVE, (new_status, datetime.now(), profile_id))

        logger.info(f"Toggled profile {profile_id} active status to {new_status}")
        return new_status

    def delete_profile(self, profile_id: int) -> str:
        """Delete a profile.

        Args:
            profile_id: Profile ID to delete

        Returns:
            Deleted profile name

        Raises:
            ValueError: If profile not found
        """
        # Get profile name for return value
        with self.db.get_cursor() as cur:
            cur.execute(GET_PROFILE_NAME, (profile_id,))
            result = cur.fetchone()

            if not result:
                raise ValueError(f"Profile {profile_id} not found")

            profile_name = result[0]

            # Delete profile
            cur.execute(DELETE_PROFILE, (profile_id,))

        logger.info(f"Deleted profile {profile_id}: {profile_name}")
        return profile_name

    def update_tracking_fields(
        self,
        profile_id: int,
        status: str,
        job_count: int,
        increment_run_count: bool = True,
    ) -> None:
        """Update profile preferences tracking fields after a DAG run.

        Updates:
        - last_run_at: Current timestamp
        - last_run_status: 'success' or 'error'
        - last_run_job_count: Number of jobs extracted/ranked (if increment_run_count=True)
        - total_run_count: Incremented by 1 (if increment_run_count=True)

        Args:
            profile_id: Profile ID to update
            status: Run status ('success' or 'error')
            job_count: Number of jobs processed for this profile
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
                        UPDATE_PROFILE_TRACKING_FIELDS,
                        (status, job_count, profile_id),
                    )
                else:
                    cur.execute(
                        UPDATE_PROFILE_TRACKING_STATUS_ONLY,
                        (status, profile_id),
                    )

            logger.debug(
                f"Updated tracking fields for profile {profile_id}: "
                f"status={status}, job_count={job_count if increment_run_count else 'preserved'}"
            )
        except Exception as e:
            logger.error(
                f"Failed to update tracking fields for profile {profile_id}: {e}",
                exc_info=True,
            )
            # Don't raise - tracking field updates shouldn't fail the DAG
            raise

    def get_profile_statistics(self, profile_id: int) -> dict[str, Any] | None:
        """Get statistics for a profile.

        Args:
            profile_id: Profile ID to get statistics for

        Returns:
            Dictionary with statistics or None if profile not found
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_PROFILE_STATISTICS, (profile_id,))
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

    def get_run_history(self, profile_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """Get run history for a profile.

        Args:
            profile_id: Profile ID to get run history for
            limit: Maximum number of runs to return (default: 20)

        Returns:
            List of run history dictionaries
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_RUN_HISTORY, (profile_id,))
            columns = [desc[0] for desc in cur.description]
            runs = [dict(zip(columns, row)) for row in cur.fetchall()]

            return runs

    def get_job_counts_over_time(self, profile_id: int, days: int = 30) -> list[dict[str, Any]]:
        """Get job counts over time for a profile.

        Args:
            profile_id: Profile ID to get job counts for
            days: Number of days to look back (default: 30)

        Returns:
            List of dictionaries with run_date and job_count
        """
        with self.db.get_cursor() as cur:
            # Modify query to use days parameter
            query = GET_JOB_COUNTS_OVER_TIME.replace("30 days", f"{days} days")
            cur.execute(query, (profile_id,))
            columns = [desc[0] for desc in cur.description]
            counts = [dict(zip(columns, row)) for row in cur.fetchall()]

            return counts
