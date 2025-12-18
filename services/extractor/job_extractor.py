"""Job Extractor Service.

Extracts job postings from JSearch API and writes to raw.jsearch_job_postings
table.
"""

import json
import logging
from datetime import date, datetime
from hashlib import md5
from typing import Any

from psycopg2.extras import execute_values

from shared import Database
from .jsearch_client import JSearchClient
from .queries import GET_ACTIVE_PROFILES_FOR_JOBS, INSERT_JSEARCH_JOB_POSTINGS

logger = logging.getLogger(__name__)


class JobExtractor:
    """
    Service for extracting job postings from JSearch API.

    Reads active profiles from marts.profile_preferences, calls JSearch API
    for each profile, and writes raw JSON responses to raw.jsearch_job_postings.
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
            num_pages: Number of pages to fetch per profile.
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

    def get_active_profiles(self) -> list[dict[str, Any]]:
        """Get all active profiles from marts.profile_preferences.

        Returns:
            List of active profile dictionaries.
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_ACTIVE_PROFILES_FOR_JOBS)
            columns = [desc[0] for desc in cur.description]
            profiles = [dict(zip(columns, row, strict=False)) for row in cur.fetchall()]

        logger.info(f"Found {len(profiles)} active profile(s)")
        return profiles

    def extract_jobs_for_profile(self, profile: dict[str, Any]) -> int:
        """
        Extract jobs for a single profile and write to database.

        Args:
            profile: Profile dictionary with search parameters

        Returns:
            Number of jobs extracted
        """
        profile_id = profile["profile_id"]
        profile_name = profile["profile_name"]
        query = profile["query"]

        logger.info(f"Extracting jobs for profile {profile_id} ({profile_name}): query='{query}'")

        try:
            # Call JSearch API
            response = self.client.search_jobs(
                query=query,
                location=profile.get("location"),
                country=profile.get("country"),
                date_posted=profile.get("date_window"),
                num_pages=self.num_pages,
            )

            # Extract job data from response
            if response.get("status") != "OK":
                logger.warning(f"API returned non-OK status: {response.get('status')}")
                return 0

            jobs_data = response.get("data", [])
            if not jobs_data:
                logger.info(f"No jobs found for profile {profile_id}")
                return 0

            # Write to database
            jobs_written = self._write_jobs_to_db(jobs_data, profile_id)
            logger.info(f"Extracted {jobs_written} jobs for profile {profile_id}")

            return jobs_written

        except Exception as e:
            logger.error(f"Error extracting jobs for profile {profile_id}: {e}", exc_info=True)
            raise

    def _write_jobs_to_db(self, jobs_data: list[dict[str, Any]], profile_id: int) -> int:
        """Write job postings to raw.jsearch_job_postings table.

        Args:
            jobs_data: List of job posting dictionaries from API
            profile_id: Profile ID that triggered this extraction

        Returns:
            Number of jobs written.
        """
        now = datetime.now()
        today = date.today()

        # Prepare data for bulk insert
        rows = []
        for job in jobs_data:
            # Generate surrogate key (using hash of job_id and profile_id for uniqueness)
            job_id = job.get("job_id", "")
            key_string = f"{job_id}|{profile_id}"
            jsearch_job_postings_key = int(md5(key_string.encode()).hexdigest()[:15], 16)

            rows.append(
                (
                    jsearch_job_postings_key,
                    json.dumps(job),  # Store entire job object as JSONB
                    today,
                    now,
                    "jsearch",
                    profile_id,
                )
            )

        if not rows:
            return 0

        # Bulk insert using execute_values for efficiency
        # Note: Duplicates will be handled by staging layer deduplication
        with self.db.get_cursor() as cur:
            execute_values(cur, INSERT_JSEARCH_JOB_POSTINGS, rows)

        return len(rows)

    def extract_all_jobs(self) -> dict[int, int]:
        """Extract jobs for all active profiles.

        Returns:
            Dictionary mapping profile_id to number of jobs extracted.
        """
        profiles = self.get_active_profiles()

        if not profiles:
            logger.warning(
                "No active profiles found. Please create at least one profile via the Profile Management UI."
            )
            return {}

        results = {}
        for profile in profiles:
            try:
                count = self.extract_jobs_for_profile(profile)
                results[profile["profile_id"]] = count
            except Exception as e:
                logger.error(f"Failed to extract jobs for profile {profile['profile_id']}: {e}")
                results[profile["profile_id"]] = 0

        total_jobs = sum(results.values())
        logger.info(f"Extraction complete. Total jobs extracted: {total_jobs}")

        return results
