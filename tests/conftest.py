"""
Pytest configuration and fixtures.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# Add services directory to Python path for tests
# This allows imports like "from shared import Database" to work in tests
services_path = Path(__file__).parent.parent / "services"
if str(services_path) not in sys.path:
    sys.path.insert(0, str(services_path))


@pytest.fixture
def mock_db_connection():
    """Mock database connection for testing."""
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=MagicMock())
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
    return mock_conn


@pytest.fixture
def test_db_connection_string():
    """Test database connection string."""
    return os.getenv(
        "TEST_DB_CONNECTION_STRING", "postgresql://postgres:postgres@localhost:5432/job_search_test"
    )


@pytest.fixture
def sample_companies_data():
    """Sample company data for testing."""
    return [
        {
            "company_id": 1,
            "name": "Microsoft Corporation",
            "website": "https://microsoft.com",
            "rating": 4.2,
        },
        {
            "company_id": 2,
            "name": "Apple Inc",
            "website": "https://apple.com",
            "rating": 4.3,
        },
        {
            "company_id": 3,
            "name": "Google",
            "website": "https://google.com",
            "rating": 4.4,
        },
    ]
