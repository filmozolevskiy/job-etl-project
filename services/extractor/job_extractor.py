"""Job Extractor Service.

Extracts job postings from JSearch API and writes to raw.jsearch_job_postings
table.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from hashlib import md5
from typing import Any

from psycopg2.extras import execute_values
from shared import Database

from .jsearch_client import JSearchClient
from .queries import (
    CHECK_EXISTING_JOBS,
    GET_ACTIVE_CAMPAIGNS_FOR_JOBS,
    INSERT_JSEARCH_JOB_POSTINGS,
)

logger = logging.getLogger(__name__)


class JobExtractor:
    """
    Service for extracting job postings from JSearch API.

    Reads active campaigns from marts.job_campaigns, calls JSearch API
    for each campaign, and writes raw JSON responses to raw.jsearch_job_postings.
    """

    def __init__(
        self,
        database: Database,
        jsearch_client: JSearchClient,
        num_pages: int,
    ):
        """Initialize the job extractor.

        Args:
            database: Database connection interface (implements Database protocol)
            jsearch_client: JSearch API client instance
            num_pages: Number of pages to fetch per campaign.
        """
        if not database:
            raise ValueError("Database is required")
        if not jsearch_client:
            raise ValueError("JSearchClient is required")
        if not isinstance(num_pages, int) or num_pages <= 0:
            raise ValueError(f"num_pages must be a positive integer, got: {num_pages}")

        self.db = database
        self.client = jsearch_client
        self.num_pages = num_pages

    def get_active_campaigns(self) -> list[dict[str, Any]]:
        """Get all active campaigns from marts.job_campaigns.

        Returns:
            List of active campaign dictionaries.
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_ACTIVE_CAMPAIGNS_FOR_JOBS)
            columns = [desc[0] for desc in cur.description]
            campaigns = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.info(f"Found {len(campaigns)} active campaign(s)")
        return campaigns

    def extract_jobs_for_campaign(self, campaign: dict[str, Any]) -> int:
        """
        Extract jobs for a single campaign and write to database.

        Args:
            campaign: Campaign dictionary with search parameters

        Returns:
            Number of jobs extracted
        """
        campaign_id = campaign["campaign_id"]
        campaign_name = campaign["campaign_name"]
        query = campaign["query"]

        logger.info(
            f"Extracting jobs for campaign {campaign_id} ({campaign_name}): query='{query}'"
        )

        try:
            # Call JSearch API
            response = self.client.search_jobs(
                query=query,
                location=campaign.get("location"),
                country=campaign.get("country"),
                date_posted=campaign.get("date_window"),
                num_pages=self.num_pages,
            )

            # Extract job data from response
            if response.get("status") != "OK":
                logger.warning(f"API returned non-OK status: {response.get('status')}")
                return 0

            jobs_data = response.get("data", [])
            if not jobs_data:
                logger.info(f"No jobs found for campaign {campaign_id}")
                return 0

            # Write to database
            jobs_written = self._write_jobs_to_db(jobs_data, campaign_id)
            logger.info(f"Extracted {jobs_written} jobs for campaign {campaign_id}")

            return jobs_written

        except Exception as e:
            logger.error(f"Error extracting jobs for campaign {campaign_id}: {e}", exc_info=True)
            raise

    def _write_jobs_to_db(self, jobs_data: list[dict[str, Any]], campaign_id: int) -> int:
        """Write job postings to raw.jsearch_job_postings table.

        Performs deduplication at the extractor level by checking for existing jobs
        before inserting. Only unique jobs (based on job_id and campaign_id) are inserted.

        Args:
            jobs_data: List of job posting dictionaries from API
            campaign_id: Campaign ID that triggered this extraction

        Returns:
            Number of jobs written (after deduplication).
        """
        if not jobs_data:
            return 0

        now = datetime.now()
        today = date.today()

        # Extract job IDs for deduplication check
        job_ids = [job.get("job_id", "") for job in jobs_data if job.get("job_id")]
        if not job_ids:
            logger.warning(
                f"No valid job IDs found in {len(jobs_data)} jobs for campaign {campaign_id}"
            )
            return 0

        # Check for existing jobs to avoid duplicates
        existing_jobs = set()
        with self.db.get_cursor() as cur:
            cur.execute(CHECK_EXISTING_JOBS, (job_ids, campaign_id))
            for row in cur.fetchall():
                existing_jobs.add((row[0], row[1]))  # (job_id, campaign_id)

        # Filter out duplicates before preparing insert
        unique_jobs = []
        for job in jobs_data:
            job_id = job.get("job_id", "")
            if not job_id:
                continue
            if (job_id, campaign_id) in existing_jobs:
                logger.debug(f"Skipping duplicate job {job_id} for campaign {campaign_id}")
                continue
            unique_jobs.append(job)

        if not unique_jobs:
            logger.info(f"All {len(jobs_data)} jobs already exist for campaign {campaign_id}")
            return 0

        # Prepare data for bulk insert (only unique jobs)
        rows = []
        for job in unique_jobs:
            # Generate surrogate key (using hash of job_id and campaign_id for uniqueness)
            job_id = job.get("job_id", "")
            key_string = f"{job_id}|{campaign_id}"
            jsearch_job_postings_key = int(md5(key_string.encode()).hexdigest()[:15], 16)

            rows.append(
                (
                    jsearch_job_postings_key,
                    json.dumps(job),  # Store entire job object as JSONB
                    today,
                    now,
                    "jsearch",
                    campaign_id,
                )
            )

        # Bulk insert using execute_values for efficiency
        with self.db.get_cursor() as cur:
            execute_values(cur, INSERT_JSEARCH_JOB_POSTINGS, rows)

        logger.info(
            f"Inserted {len(rows)} unique jobs for campaign {campaign_id} "
            f"(skipped {len(jobs_data) - len(rows)} duplicates)"
        )
        return len(rows)

    def extract_all_jobs(self) -> dict[int, int]:
        """Extract jobs for all active campaigns.

        Returns:
            Dictionary mapping campaign_id to number of jobs extracted.
        """
        campaigns = self.get_active_campaigns()

        if not campaigns:
            logger.warning(
                "No active campaigns found. Please create at least one campaign via the Campaign Management UI."
            )
            return {}

        results = {}
        for campaign in campaigns:
            try:
                count = self.extract_jobs_for_campaign(campaign)
                results[campaign["campaign_id"]] = count
            except Exception as e:
                logger.error(f"Failed to extract jobs for campaign {campaign['campaign_id']}: {e}")
                results[campaign["campaign_id"]] = 0

        total_jobs = sum(results.values())
        logger.info(f"Extraction complete. Total jobs extracted: {total_jobs}")

        return results
