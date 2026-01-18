"""Pytest configuration for browser tests."""

from __future__ import annotations

import os
import time
from collections.abc import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

pytestmark = pytest.mark.browser


@pytest.fixture(scope="session")
def app_url() -> str:
    """Get the Flask app URL from environment or use default."""
    return os.environ.get("FLASK_APP_URL", "http://localhost:5000")


@pytest.fixture(scope="session")
def playwright() -> Generator[Playwright, None, None]:
    """Create Playwright instance."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Generator[Browser, None, None]:
    """Create browser instance."""
    browser = playwright.chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.fixture
def context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """Create browser context for each test."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    yield context
    context.close()


@pytest.fixture
def page(context: BrowserContext, app_url: str) -> Generator[Page, None, None]:
    """Create a new page for each test."""
    page = context.new_page()

    # Wait for Flask server to be ready
    max_retries = 30
    retry_count = 0
    while retry_count < max_retries:
        try:
            response = page.goto(f"{app_url}/", wait_until="networkidle", timeout=5000)
            if response and response.status < 500:
                break
        except Exception:
            pass
        retry_count += 1
        time.sleep(1)

    yield page
    page.close()


@pytest.fixture
def logged_in_page(page: Page, app_url: str) -> Generator[Page, None, None]:
    """Create a page with logged-in user session."""
    # Navigate to login page
    page.goto(f"{app_url}/login")

    # Fill in login form (adjust selectors based on your actual UI)
    username_input = page.locator('input[name="username"], input[type="text"]').first
    password_input = page.locator('input[name="password"], input[type="password"]').first
    login_button = page.locator('button[type="submit"], button:has-text("Login")').first

    # Use test credentials from environment or defaults
    test_username = os.environ.get("TEST_USERNAME", "test_user")
    test_password = os.environ.get("TEST_PASSWORD", "test_password")

    username_input.fill(test_username)
    password_input.fill(test_password)
    login_button.click()

    # Wait for navigation after login
    page.wait_for_url(f"{app_url}/dashboard", timeout=10000)

    yield page
