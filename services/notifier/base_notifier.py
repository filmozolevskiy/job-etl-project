"""
Base Notification Service

Abstract base class for notification services (email, SMS, etc.).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseNotifier(ABC):
    """
    Abstract base class for notification services.
    
    Subclasses should implement send_notification() to handle
    the actual delivery mechanism (email, SMS, etc.).
    """
    
    def __init__(self):
        """Initialize the notifier."""
        pass
    
    @abstractmethod
    def send_notification(
        self,
        recipient: str,
        subject: str,
        content: str,
        **kwargs
    ) -> bool:
        """
        Send a notification to a recipient.
        
        Args:
            recipient: Recipient identifier (email address, phone number, etc.)
            subject: Notification subject/title
            content: Notification content (HTML, plain text, etc.)
            **kwargs: Additional channel-specific parameters
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        pass
    
    def format_job_list_table(
        self,
        jobs: List[Dict[str, Any]],
        max_jobs: int = 10
    ) -> str:
        """
        Format a list of jobs as an HTML table for notifications.
        
        Creates a styled HTML table with job title, company, location, and score.
        This is a reusable component that can be embedded in full email templates.
        
        Args:
            jobs: List of job dictionaries with ranking and job details
            max_jobs: Maximum number of jobs to include
            
        Returns:
            HTML string with formatted job table
        """
        if not jobs:
            return "<p>No new jobs found.</p>"
        
        # Limit to top N jobs
        jobs_to_show = jobs[:max_jobs]
        
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 800px;">
            <h2 style="color: #333;">Top {len(jobs_to_show)} Job Matches</h2>
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead>
                    <tr style="background-color: #f5f5f5;">
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Title</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Company</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Location</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Score</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for job in jobs_to_show:
            title = job.get('job_title', 'N/A')
            company = job.get('company_name', job.get('employer_name', 'N/A'))
            location = job.get('job_location', 'N/A')
            score = job.get('rank_score', 0)
            apply_link = job.get('apply_link', job.get('job_apply_link', '#'))
            
            # Format score with color
            score_color = '#28a745' if score >= 70 else '#ffc107' if score >= 50 else '#dc3545'
            
            html += f"""
                    <tr style="border-bottom: 1px solid #eee;">
                        <td style="padding: 10px;">
                            <a href="{apply_link}" style="color: #007bff; text-decoration: none; font-weight: bold;">{title}</a>
                        </td>
                        <td style="padding: 10px;">{company}</td>
                        <td style="padding: 10px;">{location}</td>
                        <td style="padding: 10px; color: {score_color}; font-weight: bold;">{score:.1f}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        
        return html
    
    def send_job_notifications_for_profile(
        self,
        profile: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        max_jobs: int = 10
    ) -> bool:
        """
        Send job notifications for a single profile.
        
        This is a convenience method that formats jobs and sends notification.
        Subclasses can override this if they need custom formatting.
        
        Args:
            profile: Profile dictionary with recipient information
            jobs: List of ranked jobs with job details
            max_jobs: Maximum number of jobs to include in notification
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        recipient = profile.get('email')
        if not recipient:
            logger.warning(f"No email address for profile {profile.get('profile_id')}")
            return False
        
        profile_name = profile.get('profile_name', 'Job Seeker')
        query = profile.get('query', 'jobs')
        
        # Format subject
        job_count = len(jobs[:max_jobs])
        subject = f"Daily Job Alerts: {job_count} new {query} jobs"
        
        # Format content
        job_list_html = self.format_job_list_table(jobs, max_jobs)
        
        content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 800px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #007bff;">Hello {profile_name}!</h1>
                <p>Here are your top job matches for today based on your search criteria:</p>
                {job_list_html}
                <p style="margin-top: 30px; color: #666; font-size: 0.9em;">
                    This is an automated notification from your job search profile.
                    You can update your preferences or unsubscribe through the Profile Management UI.
                </p>
            </div>
        </body>
        </html>
        """
        
        try:
            return self.send_notification(
                recipient=recipient,
                subject=subject,
                content=content
            )
        except Exception as e:
            logger.error(f"Failed to send notification to {recipient}: {e}", exc_info=True)
            return False


