"""
Notification Coordinator

High-level service that coordinates fetching ranked jobs and sending notifications.
Works with any BaseNotifier implementation (email, SMS, etc.).
"""

from __future__ import annotations

import logging
from typing import Any

from shared import Database

from .base_notifier import BaseNotifier
from .queries import (
    GET_ACTIVE_PROFILES_WITH_EMAIL,
    GET_TOP_RANKED_JOBS_FOR_PROFILE,
)

logger = logging.getLogger(__name__)


class NotificationCoordinator:
    """
    High-level coordinator for sending job notifications.

    Fetches ranked jobs from database and sends notifications using
    a BaseNotifier implementation (email, SMS, etc.).
    """

    def __init__(
        self,
        notifier: BaseNotifier,
        database: Database,
        max_jobs_per_notification: int = 10,
    ):
        """
        Initialize notification coordinator.

        Args:
            notifier: BaseNotifier implementation (e.g., EmailNotifier)
            database: Database connection interface (implements Database protocol)
            max_jobs_per_notification: Maximum number of jobs to include in each notification (default: 10)
        """
        if not notifier:
            raise ValueError("Notifier is required")
        if not database:
            raise ValueError("Database is required")

        self.notifier = notifier
        self.db = database
        self.max_jobs_per_notification = max_jobs_per_notification

    def get_active_profiles(self) -> list[dict[str, Any]]:
        """
        Get all active profiles that have email addresses.

        Returns:
            List of active profile dictionaries with email addresses
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_ACTIVE_PROFILES_WITH_EMAIL)

            columns = [desc[0] for desc in cur.description]
            profiles = [dict(zip(columns, row)) for row in cur.fetchall()]

            logger.info(f"Found {len(profiles)} active profile(s) with email addresses")
            return profiles

    def get_top_ranked_jobs_for_profile(
        self, profile_id: int, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Get top ranked jobs for a profile.

        Joins dim_ranking with fact_jobs and dim_companies to get complete job information.

        Args:
            profile_id: Profile ID
            limit: Maximum number of jobs to return (default: max_jobs_per_notification)

        Returns:
            List of job dictionaries with ranking and job details
        """
        if limit is None:
            limit = self.max_jobs_per_notification

        with self.db.get_cursor() as cur:
            # Get top ranked jobs with job details
            cur.execute(GET_TOP_RANKED_JOBS_FOR_PROFILE, (profile_id, limit))

            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, row)) for row in cur.fetchall()]

            logger.debug(f"Found {len(jobs)} ranked jobs for profile {profile_id}")
            return jobs

    def send_notifications_for_profile(self, profile: dict[str, Any]) -> bool:
        """
        Send job notifications for a single profile.

        Args:
            profile: Profile dictionary

        Returns:
            True if notification was sent successfully, False otherwise
        """
        profile_id = profile["profile_id"]
        profile_name = profile["profile_name"]

        logger.info(f"Sending notifications for profile {profile_id} ({profile_name})")

        # Get top ranked jobs
        jobs = self.get_top_ranked_jobs_for_profile(profile_id)

        if not jobs:
            logger.info(f"No ranked jobs found for profile {profile_id}")
            return False

        # Send notification using the notifier
        success = self.notifier.send_job_notifications_for_profile(
            profile=profile, jobs=jobs, max_jobs=self.max_jobs_per_notification
        )

        if success:
            logger.info(
                f"Notification sent successfully to {profile.get('email')} ({len(jobs)} jobs)"
            )
        else:
            logger.warning(f"Failed to send notification to {profile.get('email')}")

        return success

    def send_all_notifications(self) -> dict[int, bool]:
        """
        Send notifications for all active profiles.

        Returns:
            Dictionary mapping profile_id to success status (True/False)
        """
        profiles = self.get_active_profiles()

        if not profiles:
            logger.warning("No active profiles with email addresses found")
            return {}

        results = {}
        for profile in profiles:
            try:
                success = self.send_notifications_for_profile(profile)
                results[profile["profile_id"]] = success
            except Exception as e:
                logger.error(
                    f"Failed to send notification for profile {profile['profile_id']}: {e}",
                    exc_info=True,
                )
                results[profile["profile_id"]] = False

        # Log summary
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        logger.info(f"Notification sending complete. Success: {success_count}/{total_count}")

        return results
