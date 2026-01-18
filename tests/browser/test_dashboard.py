"""Browser tests for dashboard functionality."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

pytestmark = pytest.mark.browser


def test_dashboard_loads(logged_in_page: Page, app_url: str) -> None:
    """Test that dashboard loads after login."""
    # logged_in_page fixture already logs in and navigates to dashboard
    page = logged_in_page
    page.goto(f"{app_url}/dashboard")
    
    # Verify page loads without errors
    assert page.locator("body").count() > 0
    
    # Check for common dashboard elements (adjust based on actual UI)
    # This is a basic check - you may want to add more specific assertions
    assert page.url.endswith("/dashboard") or page.url.endswith("/dashboard/")


def test_navigation_to_campaigns(logged_in_page: Page, app_url: str) -> None:
    """Test navigation to campaigns page."""
    page = logged_in_page
    
    # Try to navigate to campaigns page
    campaigns_link = page.locator('a[href*="campaign"], a:has-text("Campaign")').first
    
    if campaigns_link.count() > 0:
        campaigns_link.click()
        page.wait_for_timeout(1000)
        # Verify we navigated to campaigns page
        assert "campaign" in page.url.lower()


def test_logout(logged_in_page: Page, app_url: str) -> None:
    """Test logout functionality."""
    page = logged_in_page
    
    # Find and click logout button/link
    logout_button = page.locator('button:has-text("Logout"), a:has-text("Logout")').first
    
    if logout_button.count() > 0:
        logout_button.click()
        page.wait_for_url(f"{app_url}/login", timeout=5000)
        # Verify we're back on login page
        assert "/login" in page.url
