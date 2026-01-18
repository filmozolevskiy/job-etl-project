"""Utilities for taking and managing screenshots in browser tests."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"


def ensure_screenshot_dir() -> None:
    """Ensure screenshot directory exists."""
    SCREENSHOT_DIR.mkdir(exist_ok=True)


def take_screenshot(
    page: Page,
    name: str,
    full_page: bool = False,
    description: str | None = None,
) -> Path:
    """Take a screenshot and save it with a descriptive name.

    Args:
        page: Playwright page object
        name: Base name for screenshot (without extension)
        full_page: If True, capture full scrollable page
        description: Optional description for logging

    Returns:
        Path to saved screenshot file

    Example:
        >>> screenshot_path = take_screenshot(page, "dashboard_after_login")
        >>> screenshot_path = take_screenshot(page, "form_before_submit", full_page=True, description="Form state before submission")
    """
    ensure_screenshot_dir()

    # Clean name (remove invalid characters)
    clean_name = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    if not clean_name.endswith(".png"):
        clean_name += ".png"

    screenshot_path = SCREENSHOT_DIR / clean_name

    page.screenshot(path=str(screenshot_path), full_page=full_page)

    if description:
        print(f"Screenshot saved: {screenshot_path} ({description})")
    else:
        print(f"Screenshot saved: {screenshot_path}")

    return screenshot_path


def get_screenshot_path(name: str) -> Path:
    """Get the expected path for a screenshot without taking it.

    Args:
        name: Base name for screenshot (without extension)

    Returns:
        Expected path to screenshot file
    """
    ensure_screenshot_dir()
    clean_name = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    if not clean_name.endswith(".png"):
        clean_name += ".png"
    return SCREENSHOT_DIR / clean_name


def format_screenshot_markdown(screenshot_paths: list[Path], base_description: str = "") -> str:
    """Format screenshot paths as markdown for Linear comments.

    Args:
        screenshot_paths: List of screenshot file paths
        base_description: Optional base description for the screenshot section

    Returns:
        Formatted markdown string for Linear comments

    Example:
        >>> screenshots = [
        ...     get_screenshot_path("dashboard_after_login"),
        ...     get_screenshot_path("campaigns_page_loaded"),
        ... ]
        >>> markdown = format_screenshot_markdown(screenshots, "Browser test verification:")
        >>> # Use markdown in Linear comment
    """
    ensure_screenshot_dir()

    lines = []
    if base_description:
        lines.append(f"{base_description}\n")

    for screenshot_path in screenshot_paths:
        # Get relative path from project root for display
        try:
            rel_path = screenshot_path.relative_to(Path(__file__).parent.parent.parent)
            lines.append(f"- `{str(rel_path)}`")
        except ValueError:
            # If relative path fails, use absolute or just filename
            lines.append(f"- `{screenshot_path.name}`")

    return "\n".join(lines)
