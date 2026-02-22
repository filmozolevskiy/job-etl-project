"""
Notification Coordinator

High-level service that coordinates fetching ranked jobs and sending notifications.
Works with any BaseNotifier implementation (email, SMS, etc.).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from shared import Database

from .base_notifier import BaseNotifier
from .queries import (
    GET_ACTIVE_CAMPAIGNS_WITH_EMAIL,
    GET_TOP_RANKED_JOBS_FOR_CAMPAIGN,
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
        self._campaign_service = None

    @property
    def campaign_service(self):
        """Lazy load CampaignService to avoid circular imports if any."""
        if self._campaign_service is None:
            from campaign_management import CampaignService

            self._campaign_service = CampaignService(self.db)
        return self._campaign_service

    def get_active_campaigns(self) -> list[dict[str, Any]]:
        """
        Get all active campaigns that have email addresses.

        Returns:
            List of active campaign dictionaries with email addresses
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_ACTIVE_CAMPAIGNS_WITH_EMAIL)

            columns = [desc[0] for desc in cur.description]
            campaigns = [dict(zip(columns, row)) for row in cur.fetchall()]

            logger.info(f"Found {len(campaigns)} active campaign(s) with email addresses")
            return campaigns

    def get_top_ranked_jobs_for_campaign(
        self, campaign_id: int, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Get top ranked jobs for a campaign.

        Joins dim_ranking with fact_jobs and dim_companies to get complete job information.

        Args:
            campaign_id: Campaign ID
            limit: Maximum number of jobs to return (default: max_jobs_per_notification)

        Returns:
            List of job dictionaries with ranking and job details
        """
        if limit is None:
            limit = self.max_jobs_per_notification

        with self.db.get_cursor() as cur:
            # Get top ranked jobs with job details
            cur.execute(GET_TOP_RANKED_JOBS_FOR_CAMPAIGN, (campaign_id, limit))

            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, row)) for row in cur.fetchall()]

            logger.debug(f"Found {len(jobs)} ranked jobs for campaign {campaign_id}")
            return jobs

    def send_notifications_for_campaign(self, campaign: dict[str, Any]) -> bool:
        """
        Send job notifications for a single campaign.

        Args:
            campaign: Campaign dictionary

        Returns:
            True if notification was sent successfully, False otherwise
        """
        campaign_id = campaign["campaign_id"]
        campaign_name = campaign["campaign_name"]
        last_sent = campaign.get("last_notification_sent_at")

        # Implement once-per-day restriction
        if last_sent:
            if isinstance(last_sent, str):
                try:
                    last_sent = datetime.fromisoformat(last_sent)
                except ValueError:
                    logger.warning(f"Could not parse last_notification_sent_at: {last_sent}")
                    last_sent = None

            if last_sent and last_sent.date() == datetime.now().date():
                logger.info(
                    f"Skipping notification for campaign {campaign_id} - already sent today ({last_sent.date()})"
                )
                return False

        logger.info(f"Sending notifications for campaign {campaign_id} ({campaign_name})")

        # Get top ranked jobs
        jobs = self.get_top_ranked_jobs_for_campaign(campaign_id)

        if not jobs:
            logger.info(f"No ranked jobs found for campaign {campaign_id}")
            return False

        # Send notification using the notifier
        success = self.notifier.send_job_notifications_for_campaign(
            campaign=campaign, jobs=jobs, max_jobs=self.max_jobs_per_notification
        )

        if success:
            logger.info(
                f"Notification sent successfully to {campaign.get('email')} ({len(jobs)} jobs)"
            )
            # Update last_notification_sent_at
            try:
                self.campaign_service.update_last_notification_sent(campaign_id)
            except Exception as e:
                logger.error(
                    f"Failed to update last_notification_sent_at for campaign {campaign_id}: {e}"
                )
        else:
            logger.warning(f"Failed to send notification to {campaign.get('email')}")

        return success

    def send_all_notifications(self) -> dict[int, bool]:
        """
        Send notifications for all active campaigns.

        Returns:
            Dictionary mapping campaign_id to success status (True/False)
        """
        campaigns = self.get_active_campaigns()

        if not campaigns:
            logger.warning("No active campaigns with email addresses found")
            return {}

        results = {}
        for campaign in campaigns:
            try:
                success = self.send_notifications_for_campaign(campaign)
                results[campaign["campaign_id"]] = success
            except Exception as e:
                logger.error(
                    f"Failed to send notification for campaign {campaign['campaign_id']}: {e}",
                    exc_info=True,
                )
                results[campaign["campaign_id"]] = False

        # Log summary
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        logger.info(f"Notification sending complete. Success: {success_count}/{total_count}")

        return results
