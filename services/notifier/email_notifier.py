"""
Email Notification Service

Sends job notifications via email using SMTP.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

from .base_notifier import BaseNotifier

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class EmailNotifier(BaseNotifier):
    """
    Email notification service using SMTP.

    Sends HTML emails with job listings to campaign email addresses.
    """

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        smtp_use_tls: bool = True,
        from_email: str | None = None,
    ):
        """
        Initialize email notifier.

        Args:
            smtp_host: SMTP server hostname. If None, reads from SMTP_HOST env var.
            smtp_port: SMTP server port. If None, reads from SMTP_PORT env var (default: 587).
            smtp_user: SMTP username. If None, reads from SMTP_USER env var.
            smtp_password: SMTP password. If None, reads from SMTP_PASSWORD env var.
            smtp_use_tls: Whether to use TLS (default: True)
            from_email: From email address. If None, uses smtp_user or 'noreply@jobsearch.local'
        """
        super().__init__()

        self.smtp_host = smtp_host or os.getenv("SMTP_HOST")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.smtp_use_tls = smtp_use_tls
        self.from_email = from_email or self.smtp_user or "noreply@jobsearch.local"

        # Validate required settings
        if not self.smtp_host:
            logger.warning("SMTP_HOST not configured - email notifications will be disabled")

    def send_notification(self, recipient: str, subject: str, content: str, **kwargs) -> bool:
        """
        Send an email notification.

        Args:
            recipient: Email address of recipient
            subject: Email subject
            content: Email content (HTML)
            **kwargs: Additional parameters (unused for email)

        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.smtp_host:
            logger.warning("Cannot send email - SMTP not configured")
            return False

        if not recipient:
            logger.warning("No recipient email address provided")
            return False

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_email
            msg["To"] = recipient
            msg["Subject"] = subject

            # Add HTML content
            html_part = MIMEText(content, "html")
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()

                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)

                server.send_message(msg)

            logger.info(f"Email sent successfully to {recipient}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}", exc_info=True)
            return False
