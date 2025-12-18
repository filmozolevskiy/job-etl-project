"""
Unit tests for Company Extractor service.

Tests fuzzy matching, SQL injection prevention, and existing company checks.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, Mock

import pytest

from services.extractor.company_extractor import CompanyExtractor
from services.extractor.glassdoor_client import GlassdoorClient
from services.shared import Database


class MockDatabase:
    """Simple mock Database implementation for testing."""

    def __init__(self):
        self.cursor = MagicMock()

    @contextmanager
    def get_cursor(self):
        """Context manager that yields a mock cursor."""
        yield self.cursor


class TestCompanyExtractorFuzzyMatching:
    """Test fuzzy matching functionality."""

    def test_select_best_match_single_result_above_threshold(self):
        """Test that single result above threshold is returned."""
        mock_db = Mock(spec=Database)
        mock_client = Mock(spec=GlassdoorClient)
        extractor = CompanyExtractor(database=mock_db, glassdoor_client=mock_client)

        # Use a more similar match that will exceed threshold
        companies_data = [{"name": "Microsoft", "company_id": 123}]
        lookup_key = "microsoft"

        result = extractor._select_best_match(companies_data, lookup_key, similarity_threshold=0.85)

        assert result is not None
        assert result["name"] == "Microsoft"

    def test_select_best_match_single_result_below_threshold(self):
        """Test that single result below threshold returns None."""
        mock_db = Mock(spec=Database)
        mock_client = Mock(spec=GlassdoorClient)
        extractor = CompanyExtractor(database=mock_db, glassdoor_client=mock_client)

        companies_data = [{"name": "Completely Different Company", "company_id": 123}]
        lookup_key = "microsoft"

        result = extractor._select_best_match(companies_data, lookup_key, similarity_threshold=0.85)

        assert result is None

    def test_select_best_match_multiple_results(self):
        """Test that best match is selected from multiple results."""
        mock_db = Mock(spec=Database)
        mock_client = Mock(spec=GlassdoorClient)
        extractor = CompanyExtractor(database=mock_db, glassdoor_client=mock_client)

        companies_data = [
            {"name": "Apple Inc", "company_id": 1},
            {"name": "Apple Computer", "company_id": 2},  # Should be best match
            {"name": "Microsoft Corporation", "company_id": 3},
        ]
        lookup_key = "apple computer"

        result = extractor._select_best_match(companies_data, lookup_key, similarity_threshold=0.85)

        assert result is not None
        assert result["name"] == "Apple Computer"
        assert result["company_id"] == 2

    def test_select_best_match_empty_list(self):
        """Test that empty list returns None."""
        mock_db = Mock(spec=Database)
        mock_client = Mock(spec=GlassdoorClient)
        extractor = CompanyExtractor(database=mock_db, glassdoor_client=mock_client)

        result = extractor._select_best_match([], "test", similarity_threshold=0.85)

        assert result is None

    def test_select_best_match_no_company_name(self):
        """Test that companies without name are skipped."""
        mock_db = Mock(spec=Database)
        mock_client = Mock(spec=GlassdoorClient)
        extractor = CompanyExtractor(database=mock_db, glassdoor_client=mock_client)

        companies_data = [
            {"name": "", "company_id": 1},
            {"company_id": 2},  # Missing name key
            {"name": "Valid Company", "company_id": 3},
        ]
        lookup_key = "valid company"

        result = extractor._select_best_match(companies_data, lookup_key, similarity_threshold=0.85)

        assert result is not None
        assert result["name"] == "Valid Company"


class TestCompanyExtractorSQLInjection:
    """Test SQL injection prevention."""

    def test_get_companies_to_enrich_parameterized_query(self):
        """Test that limit parameter is properly parameterized."""
        # Setup mock database and cursor
        mock_db = MockDatabase()
        mock_db.cursor.fetchall.return_value = [("company1",), ("company2",)]

        extractor = CompanyExtractor(database=mock_db, glassdoor_client=Mock(spec=GlassdoorClient))

        # Test with limit
        extractor.get_companies_to_enrich(limit=10)

        # Verify execute was called with parameterized query
        execute_calls = mock_db.cursor.execute.call_args_list
        assert len(execute_calls) > 0

        # Check that the last call uses parameterized query
        last_call = execute_calls[-1]
        query, params = last_call[0]

        # Verify LIMIT is parameterized (not in query string)
        assert "LIMIT %s" in query
        assert params == (10,)

    def test_get_companies_to_enrich_invalid_limit(self):
        """Test that invalid limit raises ValueError."""
        mock_db = MockDatabase()
        mock_client = Mock(spec=GlassdoorClient)
        extractor = CompanyExtractor(database=mock_db, glassdoor_client=mock_client)

        # Test with negative limit - validation now happens before DB access
        with pytest.raises(ValueError, match="Limit must be a positive integer"):
            extractor.get_companies_to_enrich(limit=-1)

        # Test with zero
        with pytest.raises(ValueError, match="Limit must be a positive integer"):
            extractor.get_companies_to_enrich(limit=0)

        # Test with non-integer (if somehow passed)
        with pytest.raises(ValueError, match="Limit must be a positive integer"):
            extractor.get_companies_to_enrich(limit="10")  # type: ignore


class TestCompanyExtractorExistingCompanyCheck:
    """Test existing company check in query."""

    def test_get_companies_to_enrich_excludes_existing_companies(self):
        """Test that query excludes companies already in staging.glassdoor_companies."""
        mock_db = MockDatabase()
        mock_db.cursor.fetchall.return_value = []

        extractor = CompanyExtractor(
            database=mock_db,
            glassdoor_client=Mock(spec=GlassdoorClient),
        )

        extractor.get_companies_to_enrich()

        # Verify execute was called
        execute_calls = mock_db.cursor.execute.call_args_list
        assert len(execute_calls) > 0

        # Get the query from the call
        last_call = execute_calls[-1]
        query = last_call[0][0] if last_call[0] else ""

        # Verify query checks staging.glassdoor_companies
        assert "staging.glassdoor_companies" in query
        assert "company_lookup_key" in query
        assert "NOT IN" in query
