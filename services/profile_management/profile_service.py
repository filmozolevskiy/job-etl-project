"""Profile Management Service.

Service for managing job search profiles in marts.profile_preferences table.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from shared.database import Database

from .queries import (
    DELETE_PROFILE,
    GET_ALL_PROFILES,
    GET_NEXT_PROFILE_ID,
    GET_PROFILE_ACTIVE_STATUS,
    GET_PROFILE_BY_ID,
    GET_PROFILE_NAME,
    INSERT_PROFILE,
    TOGGLE_PROFILE_ACTIVE,
    UPDATE_PROFILE,
    UPDATE_PROFILE_TRACKING_FIELDS,
    UPDATE_PROFILE_TRACKING_STATUS_ONLY,
)

logger = logging.getLogger(__name__)


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

        Args:
            profile_id: Profile ID to retrieve

        Returns:
            Profile dictionary or None if not found
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_PROFILE_BY_ID, (profile_id,))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                return None

            profile = dict(zip(columns, row))
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

        with self.db.get_cursor() as cur:
            # Normalize currency to uppercase if provided
            currency_normalized = currency.upper().strip() if currency else None

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

        # Normalize currency to uppercase if provided
        currency_normalized = currency.upper().strip() if currency else None

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
                    datetime.now(),
                    profile_id,
                ),
            )

        logger.info(f"Updated profile {profile_id}: {profile_name}")

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
