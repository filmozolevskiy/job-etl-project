"""
Campaign Management Services Package

This package contains services for managing job search campaigns:
- CampaignService for CRUD operations on marts.job_campaigns
"""

from .campaign_service import CampaignService

__all__ = ["CampaignService"]
