"""Service for querying jobs with rankings and company information."""

import logging
from typing import Any

from shared.database import Database

from .queries import GET_JOBS_FOR_PROFILE, GET_JOBS_FOR_USER

logger = logging.getLogger(__name__)


class JobService:
    """Service for querying jobs with rankings."""

    def __init__(self, database: Database):
        """Initialize the job service.

        Args:
            database: Database connection interface
        """
        if not database:
            raise ValueError("Database is required")
        self.db = database

    def get_jobs_for_profile(
        self, profile_id: int, user_id: int, limit: int | None = None, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get jobs with rankings for a specific profile.

        Args:
            profile_id: Profile ID to get jobs for
            user_id: User ID to fetch notes for
            limit: Maximum number of jobs to return (optional)
            offset: Number of jobs to skip for pagination

        Returns:
            List of job dictionaries with ranking, company, and note information

        Raises:
            ValueError: If limit or offset are negative
        """
        if limit is not None and limit < 0:
            raise ValueError("Limit must be non-negative")
        if offset < 0:
            raise ValueError("Offset must be non-negative")

        query = GET_JOBS_FOR_PROFILE
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        with self.db.get_cursor() as cur:
            cur.execute(query, (user_id, user_id, profile_id))
            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.debug(f"Retrieved {len(jobs)} job(s) for profile {profile_id}")
        return jobs

    def get_jobs_for_user(
        self, user_id: int, limit: int | None = None, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get jobs with rankings for all profiles belonging to a user.

        Args:
            user_id: User ID to get jobs for
            limit: Maximum number of jobs to return (optional)
            offset: Number of jobs to skip for pagination

        Returns:
            List of job dictionaries with ranking, company, and note information

        Raises:
            ValueError: If limit or offset are negative
        """
        if limit is not None and limit < 0:
            raise ValueError("Limit must be non-negative")
        if offset < 0:
            raise ValueError("Offset must be non-negative")

        query = GET_JOBS_FOR_USER
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        with self.db.get_cursor() as cur:
            cur.execute(query, (user_id, user_id, user_id))
            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.debug(f"Retrieved {len(jobs)} job(s) for user {user_id}")
        return jobs

