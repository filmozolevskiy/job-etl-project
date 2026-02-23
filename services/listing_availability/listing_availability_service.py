"""
Listing availability service: call JSearch job-details and update staging markers.

JOB-57: Detect jobs no longer relevant (removed/filled) via job-details;
mark listing_available/listing_checked_at without removing jobs.

What counts as "not relevant" (listing_available = False):
- JSearch job-details returns a successful response with empty data (data: []).
- JSearch job-details returns 5xx (e.g. 500 Internal Server Error); the API uses this when the job is no longer available.
Other errors (timeout, 4xx other than server-side) are not overwritten; we skip and keep the last known state.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from shared import Database

logger = logging.getLogger(__name__)

GET_JOBS_TO_CHECK = """
    SELECT jsearch_job_postings_key, jsearch_job_id
    FROM staging.jsearch_job_postings
    WHERE jsearch_job_id IS NOT NULL
    ORDER BY dwh_load_timestamp DESC
    LIMIT %s
"""

UPDATE_LISTING_STATUS = """
    UPDATE staging.jsearch_job_postings
    SET listing_available = %s, listing_checked_at = CURRENT_TIMESTAMP
    WHERE jsearch_job_postings_key = %s
"""


class ListingAvailabilityService:
    """
    Checks JSearch job-details for each job in staging and updates
    listing_available / listing_checked_at. Empty data or 5xx → not available; other errors → skip.
    """

    def __init__(
        self,
        database: Database,
        jsearch_client: Any,
        batch_limit: int = 500,
    ):
        if not database:
            raise ValueError("Database is required")
        if not jsearch_client:
            raise ValueError("JSearch client is required")
        if batch_limit <= 0:
            raise ValueError("batch_limit must be positive")
        self.db = database
        self.jsearch_client = jsearch_client
        self.batch_limit = batch_limit

    def run_check(self) -> dict[str, int]:
        """
        Fetch job IDs from staging, call job-details for each, update markers.

        Returns:
            Dict with keys: checked, available, unavailable, errors.
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_JOBS_TO_CHECK, (self.batch_limit,))
            rows = cur.fetchall()

        if not rows:
            logger.info("No jobs in staging to check for listing availability")
            return {"checked": 0, "available": 0, "unavailable": 0, "errors": 0}

        stats: dict[str, int] = {"checked": 0, "available": 0, "unavailable": 0, "errors": 0}

        for (key, job_id) in rows:
            try:
                response = self.jsearch_client.get_job_details(job_id)
                data = response.get("data")
                if data is None:
                    logger.warning("job-details for %s returned no 'data' key", job_id)
                    stats["errors"] += 1
                    continue
                available = bool(data) if isinstance(data, list) else bool(data)
                with self.db.get_cursor() as cur:
                    cur.execute(UPDATE_LISTING_STATUS, (available, key))
                stats["checked"] += 1
                if available:
                    stats["available"] += 1
                else:
                    stats["unavailable"] += 1
            except requests.RequestException as e:
                status_code = getattr(getattr(e, "response", None), "status_code", None)
                if status_code is not None and status_code >= 500:
                    with self.db.get_cursor() as cur:
                        cur.execute(UPDATE_LISTING_STATUS, (False, key))
                    stats["checked"] += 1
                    stats["unavailable"] += 1
                    logger.info("job-details 5xx for job_id=%s (status=%s) → marking unavailable", job_id, status_code)
                else:
                    logger.warning("job-details failed for job_id=%s: %s", job_id, e)
                    stats["errors"] += 1

        logger.info(
            "Listing availability check: checked=%s available=%s unavailable=%s errors=%s",
            stats["checked"],
            stats["available"],
            stats["unavailable"],
            stats["errors"],
        )
        return stats
