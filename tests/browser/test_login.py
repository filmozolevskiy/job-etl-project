"""Browser tests for login functionality."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

pytestmark = pytest.mark.browser


def test_login_page_loads(page: Page, app_url: str) -> None:
    """Test that login page loads correctly."""
    page.goto(f"{app_url}/login")
    
    # Check that page title or heading is present
    assert page.locator("body").count() > 0
    # Check for login form elements (adjust selectors based on actual UI)
    assert (
        page.locator('input[type="text"], input[name="username"]').count() > 0
        or page.locator('input[type="password"], input[name="password"]').count() > 0
    )


def test_login_with_valid_credentials(page: Page, app_url: str) -> None:
    """Test login with valid credentials."""
    import os
    
    page.goto(f"{app_url}/login")
    
    # Fill in login form
    username_input = page.locator('input[name="username"], input[type="text"]').first
    password_input = page.locator('input[name="password"], input[type="password"]').first
    login_button = page.locator('button[type="submit"], button:has-text("Login")').first
    
    test_username = os.environ.get("TEST_USERNAME", "test_user")
    test_password = os.environ.get("TEST_PASSWORD", "test_password")
    
    username_input.fill(test_username)
    password_input.fill(test_password)
    login_button.click()
    
    # Wait for redirect to dashboard or home page
    page.wait_for_url(f"{app_url}/dashboard", timeout=10000)
    
    # Verify we're on the dashboard
    assert "/dashboard" in page.url or "/" in page.url


def test_login_with_invalid_credentials(page: Page, app_url: str) -> None:
    """Test login with invalid credentials shows error."""
    page.goto(f"{app_url}/login")
    
    # Fill in login form with invalid credentials
    username_input = page.locator('input[name="username"], input[type="text"]').first
    password_input = page.locator('input[name="password"], input[type="password"]').first
    login_button = page.locator('button[type="submit"], button:has-text("Login")').first
    
    username_input.fill("invalid_user")
    password_input.fill("invalid_password")
    login_button.click()
    
    # Wait for error message or stay on login page
    page.wait_for_timeout(2000)
    
    # Check that we're still on login page or error message is shown
    assert "/login" in page.url or page.locator("text=error, text=invalid, text=failed").count() > 0
