# Browser Tests with Playwright

This directory contains end-to-end browser tests using Playwright for headless browser testing.

## Purpose

These tests enable cloud agents to:
- Test the full application stack (Flask backend + React frontend)
- Verify UI functionality and user workflows
- Test database-related features end-to-end
- Run autonomously without manual intervention

## Prerequisites

### For Cloud Agents

1. **External Database**: Cloud agents need an external PostgreSQL database configured via Cursor Secrets:
   - `POSTGRES_HOST` - Database host
   - `POSTGRES_PORT` - Database port (default: 5432)
   - `POSTGRES_USER` - Database user
   - `POSTGRES_PASSWORD` - Database password
   - `POSTGRES_DB` - Database name

2. **Flask Secrets** (for testing auth features):
   - `FLASK_SECRET_KEY` - Flask session secret
   - `JWT_SECRET_KEY` - JWT token secret

3. **Test User Credentials** (optional, for login tests):
   - `TEST_USERNAME` - Test user username (default: "test_user")
   - `TEST_PASSWORD` - Test user password (default: "test_password")

4. **Application URL** (optional):
   - `FLASK_APP_URL` - Flask app URL (default: "http://localhost:5000")

### For Local Development

All prerequisites above apply, plus:
- Node.js and npm (for building frontend)
- Python 3.11+
- Playwright installed: `pip install playwright && python -m playwright install chromium`

## Running Tests

### Run All Browser Tests

```bash
pytest tests/browser/ -v
```

### Run Specific Test File

```bash
pytest tests/browser/test_login.py -v
```

### Run with Specific Marker

```bash
pytest -m browser -v
```

## Test Structure

- **`conftest.py`**: Pytest fixtures for browser setup (Playwright, pages, logged-in sessions)
- **`test_login.py`**: Login functionality tests
- **`test_dashboard.py`**: Dashboard and navigation tests
- Additional test files can be added for other features

## How Cloud Agents Use These Tests

1. **Environment Setup**: Cloud agents use `.cursor/environment.json` to:
   - Install Playwright and browser binaries
   - Build the React frontend
   - Start Flask server in a background terminal

2. **Test Execution**: Agents run `pytest tests/browser/` to execute all browser tests

3. **Database Access**: Tests connect to the external database configured in Cursor Secrets

## Local Verification Before Merging

Before merging a PR, you can verify changes locally:

### Step 1: Pull the Branch

```bash
git fetch origin
git checkout <branch-name>
```

### Step 2: Build and Start Services

```bash
# Build frontend
cd frontend
npm install
npm run build
cd ..

# Start services with docker-compose
docker-compose up -d postgres campaign-ui
```

### Step 3: Run Browser Tests

```bash
# Set environment variables (or use .env file)
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
export POSTGRES_DB=job_search_db
export FLASK_SECRET_KEY=dev-secret-key
export JWT_SECRET_KEY=dev-jwt-secret

# Run tests
pytest tests/browser/ -v
```

### Step 4: Manual Browser Testing (Optional)

```bash
# Start Flask server
cd campaign_ui
python app.py
```

Then open `http://localhost:5000` in your browser and test manually.

## Writing New Browser Tests

1. Create a new test file in `tests/browser/`
2. Import necessary fixtures from `conftest.py`
3. Use Playwright's page object to interact with UI elements
4. Use selectors that are stable (prefer data-testid attributes if available)
5. Take screenshots at key verification points using `screenshot_utils.take_screenshot()`

Example:

```python
from tests.browser.screenshot_utils import take_screenshot

def test_my_feature(logged_in_page: Page, app_url: str) -> None:
    """Test my new feature."""
    page = logged_in_page
    page.goto(f"{app_url}/my-feature")
    
    # Take screenshot before interaction
    take_screenshot(page, "my_feature_initial_state", description="Initial state of feature page")
    
    # Interact with elements
    button = page.locator('button:has-text("Submit")')
    button.click()
    
    # Wait for response/state change
    page.wait_for_timeout(1000)
    
    # Assert expected behavior
    assert page.locator("text=Success").count() > 0
    
    # Take screenshot after interaction
    take_screenshot(page, "my_feature_after_submit", description="Feature page after successful submission")
```

## Taking Screenshots for Linear Issues

When running browser tests during QA, take screenshots to attach to Linear issues:

```python
from tests.browser.screenshot_utils import take_screenshot, format_screenshot_markdown, get_screenshot_path

def test_qa_verification(logged_in_page: Page, app_url: str) -> None:
    """QA verification test with screenshots."""
    page = logged_in_page
    
    # Test steps with screenshots
    page.goto(f"{app_url}/dashboard")
    screenshot1 = take_screenshot(page, "dashboard_loaded")
    
    page.goto(f"{app_url}/campaigns")
    screenshot2 = take_screenshot(page, "campaigns_page_loaded")
    
    # Format screenshots for Linear comment
    screenshots = [screenshot1, screenshot2]
    markdown = format_screenshot_markdown(screenshots, "Browser test verification screenshots:")
    
    # Use markdown string in Linear issue comment
    # Example: mcp_Linear_create_comment(issue_id=..., body=markdown)
```

Screenshots are saved to `tests/browser/screenshots/` and can be referenced in Linear comments using the formatted markdown.

## Notes

- Browser tests are slower than unit/integration tests - use sparingly for critical paths
- Selectors may need adjustment as UI changes - consider adding data-testid attributes
- Tests require the Flask server to be running (handled automatically by cloud agents via terminals)
- Database must be accessible and seeded with test data if needed
