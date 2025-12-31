"""Service for querying jobs with rankings and company information."""

import logging
from typing import Any

from shared.database import Database

from .queries import (
    GET_JOB_BY_ID,
    GET_JOB_COUNTS_FOR_CAMPAIGNS,
    GET_JOBS_FOR_CAMPAIGN,
    GET_JOBS_FOR_USER,
)

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

    def get_jobs_for_campaign(
        self, campaign_id: int, user_id: int, limit: int | None = None, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get jobs with rankings for a specific campaign.

        Args:
            campaign_id: Campaign ID to get jobs for
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

        query = GET_JOBS_FOR_CAMPAIGN
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        with self.db.get_cursor() as cur:
            cur.execute(query, (user_id, user_id, campaign_id))
            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.debug(f"Retrieved {len(jobs)} job(s) for campaign {campaign_id}")
        return jobs

    def get_jobs_for_user(
        self, user_id: int, limit: int | None = None, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get jobs with rankings for all campaigns belonging to a user.

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

    def get_job_counts_for_campaigns(self, campaign_ids: list[int]) -> dict[int, int]:
        """Get job counts for multiple campaigns in a single query.

        Args:
            campaign_ids: List of campaign IDs to get counts for

        Returns:
            Dictionary mapping campaign_id to job count
        """
        if not campaign_ids:
            return {}

        with self.db.get_cursor() as cur:
            cur.execute(GET_JOB_COUNTS_FOR_CAMPAIGNS, (campaign_ids,))
            results = cur.fetchall()

        # Convert to dictionary
        counts = {row[0]: row[1] for row in results}
        logger.debug(f"Retrieved job counts for {len(counts)} campaign(s)")
        return counts

    def get_job_by_id(self, jsearch_job_id: str, user_id: int) -> dict[str, Any] | None:
        """Get a single job by ID for a specific user.

        Args:
            jsearch_job_id: JSearch job ID to lookup
            user_id: User ID to verify ownership and fetch notes

        Returns:
            Job dictionary or None if not found
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_JOB_BY_ID, (user_id, user_id, jsearch_job_id, user_id))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                logger.debug(f"Job {jsearch_job_id} not found for user {user_id}")
                return None

            job = dict(zip(columns, row))
            logger.debug(f"Retrieved job {jsearch_job_id} for user {user_id}")
            return job
