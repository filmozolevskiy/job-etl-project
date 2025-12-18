"""
Notification Service

Abstract notification service for sending job alerts via various channels.
Currently supports email notifications, with extensibility for SMS and other methods.
"""

from .base_notifier import BaseNotifier
from .email_notifier import EmailNotifier
from .notification_coordinator import NotificationCoordinator

__all__ = ["BaseNotifier", "EmailNotifier", "NotificationCoordinator"]
