"""
Pytest configuration and fixtures for unit tests.

Unit tests are fast, isolated tests that don't require external dependencies.
"""

from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture
def mock_db_connection():
    """Mock database connection for unit testing."""
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=MagicMock())
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
    return mock_conn


@pytest.fixture
def sample_companies_data():
    """Sample company data for unit testing."""
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

