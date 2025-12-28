"""Service for managing job status."""

import logging
from typing import Any

from shared.database import Database

from .queries import GET_JOB_STATUS, UPSERT_JOB_STATUS

logger = logging.getLogger(__name__)


class JobStatusService:
    """Service for managing job status."""

    def __init__(self, database: Database):
        """Initialize the job status service.

        Args:
            database: Database connection interface
        """
        if not database:
            raise ValueError("Database is required")
        self.db = database

    def get_status(self, jsearch_job_id: str, user_id: int) -> dict[str, Any] | None:
        """Get status for a job and user.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID

        Returns:
            Status dictionary or None if not found (defaults to 'waiting')
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_JOB_STATUS, (jsearch_job_id, user_id))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                return None

            return dict(zip(columns, row))

    def upsert_status(self, jsearch_job_id: str, user_id: int, status: str) -> int:
        """Insert or update status for a job and user.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID
            status: Application status (waiting, applied, rejected, interview, offer, archived)

        Returns:
            Status ID
        """
        valid_statuses = ["waiting", "applied", "rejected", "interview", "offer", "archived"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

        try:
            with self.db.get_cursor() as cur:
                cur.execute(UPSERT_JOB_STATUS, (jsearch_job_id, user_id, status))
                result = cur.fetchone()
                if result:
                    status_id = result[0]
                    logger.info(
                        f"Upserted status {status} for job {jsearch_job_id} by user {user_id}"
                    )
                    return status_id
                else:
                    raise ValueError("Failed to upsert status")
        except Exception as e:
            logger.error(f"Error upserting status: {e}", exc_info=True)
            raise
