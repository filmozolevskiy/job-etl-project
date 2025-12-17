"""
Notification Coordinator

High-level service that coordinates fetching ranked jobs and sending notifications.
Works with any BaseNotifier implementation (email, SMS, etc.).
"""

import os
import logging
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

from .base_notifier import BaseNotifier

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class NotificationCoordinator:
    """
    High-level coordinator for sending job notifications.
    
    Fetches ranked jobs from database and sends notifications using
    a BaseNotifier implementation (email, SMS, etc.).
    """
    
    def __init__(
        self,
        notifier: BaseNotifier,
        db_connection_string: Optional[str] = None,
        max_jobs_per_notification: int = 10
    ):
        """
        Initialize notification coordinator.
        
        Args:
            notifier: BaseNotifier implementation (e.g., EmailNotifier)
            db_connection_string: PostgreSQL connection string. If None, reads from DB_CONNECTION_STRING env var.
            max_jobs_per_notification: Maximum number of jobs to include in each notification (default: 10)
        """
        self.notifier = notifier
        self.db_connection_string = db_connection_string or os.getenv('DB_CONNECTION_STRING')
        self.max_jobs_per_notification = max_jobs_per_notification
        
        if not self.db_connection_string:
            raise ValueError("Database connection string is required (DB_CONNECTION_STRING env var)")
    
    def get_active_profiles(self) -> List[Dict[str, Any]]:
        """
        Get all active profiles that have email addresses.
        
        Returns:
            List of active profile dictionaries with email addresses
        """
        conn = psycopg2.connect(self.db_connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        profile_id,
                        profile_name,
                        email,
                        query
                    FROM marts.profile_preferences
                    WHERE is_active = true
                        AND email IS NOT NULL
                        AND email != ''
                    ORDER BY profile_id
                """)
                
                columns = [desc[0] for desc in cur.description]
                profiles = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                logger.info(f"Found {len(profiles)} active profile(s) with email addresses")
                return profiles
                
        finally:
            conn.close()
    
    def get_top_ranked_jobs_for_profile(
        self,
        profile_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
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
        
        conn = psycopg2.connect(self.db_connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                # Get top ranked jobs with job details
                cur.execute("""
                    SELECT 
                        dr.jsearch_job_id,
                        dr.profile_id,
                        dr.rank_score,
                        fj.job_title,
                        fj.job_location,
                        fj.job_employment_type,
                        fj.job_is_remote,
                        fj.job_posted_at_datetime_utc,
                        COALESCE(dc.company_name, fj.employer_name) as company_name,
                        fj.job_apply_link as apply_link
                    FROM marts.dim_ranking dr
                    INNER JOIN marts.fact_jobs fj
                        ON dr.jsearch_job_id = fj.jsearch_job_id
                        AND dr.profile_id = fj.profile_id
                    LEFT JOIN marts.dim_companies dc
                        ON fj.company_key = dc.company_key
                    WHERE dr.profile_id = %s
                    ORDER BY dr.rank_score DESC, dr.ranked_at DESC
                    LIMIT %s
                """, (profile_id, limit))
                
                columns = [desc[0] for desc in cur.description]
                jobs = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                logger.debug(f"Found {len(jobs)} ranked jobs for profile {profile_id}")
                return jobs
                
        finally:
            conn.close()
    
    def send_notifications_for_profile(
        self,
        profile: Dict[str, Any]
    ) -> bool:
        """
        Send job notifications for a single profile.
        
        Args:
            profile: Profile dictionary
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        profile_id = profile['profile_id']
        profile_name = profile['profile_name']
        
        logger.info(f"Sending notifications for profile {profile_id} ({profile_name})")
        
        # Get top ranked jobs
        jobs = self.get_top_ranked_jobs_for_profile(profile_id)
        
        if not jobs:
            logger.info(f"No ranked jobs found for profile {profile_id}")
            return False
        
        # Send notification using the notifier
        success = self.notifier.send_job_notifications_for_profile(
            profile=profile,
            jobs=jobs,
            max_jobs=self.max_jobs_per_notification
        )
        
        if success:
            logger.info(f"Notification sent successfully to {profile.get('email')} ({len(jobs)} jobs)")
        else:
            logger.warning(f"Failed to send notification to {profile.get('email')}")
        
        return success
    
    def send_all_notifications(self) -> Dict[int, bool]:
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
                results[profile['profile_id']] = success
            except Exception as e:
                logger.error(f"Failed to send notification for profile {profile['profile_id']}: {e}", exc_info=True)
                results[profile['profile_id']] = False
        
        # Log summary
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        logger.info(f"Notification sending complete. Success: {success_count}/{total_count}")
        
        return results


def main():
    """Main entry point for running the coordinator as a standalone script."""
    import sys
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Initialize email notifier
        from .email_notifier import EmailNotifier
        email_notifier = EmailNotifier()
        
        # Initialize notification coordinator with email notifier
        coordinator = NotificationCoordinator(notifier=email_notifier)
        
        # Send all notifications
        results = coordinator.send_all_notifications()
        
        # Print summary
        print("\n=== Notification Summary ===")
        for profile_id, success in results.items():
            status = "✓ Sent" if success else "✗ Failed"
            print(f"Profile {profile_id}: {status}")
        
        success_count = sum(1 for v in results.values() if v)
        print(f"\nTotal: {success_count}/{len(results)} notifications sent successfully")
        
        sys.exit(0 if all(results.values()) else 1)
        
    except Exception as e:
        logger.error(f"Notification sending failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

