"""
Unit tests for Company Extractor service.

Tests fuzzy matching, SQL injection prevention, and existing company checks.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from services.extractor.company_extractor import CompanyExtractor


class TestCompanyExtractorFuzzyMatching:
    """Test fuzzy matching functionality."""
    
    def test_select_best_match_single_result_above_threshold(self):
        """Test that single result above threshold is returned."""
        extractor = CompanyExtractor(
            db_connection_string="postgresql://test:test@localhost/test",
            glassdoor_api_key="test_key"
        )
        
        companies_data = [{"name": "Microsoft Corporation", "company_id": 123}]
        lookup_key = "microsoft"
        
        result = extractor._select_best_match(companies_data, lookup_key, similarity_threshold=0.85)
        
        assert result is not None
        assert result["name"] == "Microsoft Corporation"
    
    def test_select_best_match_single_result_below_threshold(self):
        """Test that single result below threshold returns None."""
        extractor = CompanyExtractor(
            db_connection_string="postgresql://test:test@localhost/test",
            glassdoor_api_key="test_key"
        )
        
        companies_data = [{"name": "Completely Different Company", "company_id": 123}]
        lookup_key = "microsoft"
        
        result = extractor._select_best_match(companies_data, lookup_key, similarity_threshold=0.85)
        
        assert result is None
    
    def test_select_best_match_multiple_results(self):
        """Test that best match is selected from multiple results."""
        extractor = CompanyExtractor(
            db_connection_string="postgresql://test:test@localhost/test",
            glassdoor_api_key="test_key"
        )
        
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
        extractor = CompanyExtractor(
            db_connection_string="postgresql://test:test@localhost/test",
            glassdoor_api_key="test_key"
        )
        
        result = extractor._select_best_match([], "test", similarity_threshold=0.85)
        
        assert result is None
    
    def test_select_best_match_no_company_name(self):
        """Test that companies without name are skipped."""
        extractor = CompanyExtractor(
            db_connection_string="postgresql://test:test@localhost/test",
            glassdoor_api_key="test_key"
        )
        
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
    
    @patch('services.extractor.company_extractor.psycopg2.connect')
    def test_get_companies_to_enrich_parameterized_query(self, mock_connect):
        """Test that limit parameter is properly parameterized."""
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.fetchall.return_value = [("company1",), ("company2",)]
        
        extractor = CompanyExtractor(
            db_connection_string="postgresql://test:test@localhost/test",
            glassdoor_api_key="test_key"
        )
        
        # Test with limit
        extractor.get_companies_to_enrich(limit=10)
        
        # Verify execute was called with parameterized query
        execute_calls = mock_cursor.execute.call_args_list
        assert len(execute_calls) > 0
        
        # Check that the last call uses parameterized query
        last_call = execute_calls[-1]
        query, params = last_call[0]
        
        # Verify LIMIT is parameterized (not in query string)
        assert "LIMIT %s" in query
        assert params == (10,)
    
    @patch('services.extractor.company_extractor.psycopg2.connect')
    def test_get_companies_to_enrich_invalid_limit(self, mock_connect):
        """Test that invalid limit raises ValueError."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        extractor = CompanyExtractor(
            db_connection_string="postgresql://test:test@localhost/test",
            glassdoor_api_key="test_key"
        )
        
        # Test with negative limit
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
    
    @patch('services.extractor.company_extractor.psycopg2.connect')
    def test_get_companies_to_enrich_excludes_existing_companies(self, mock_connect):
        """Test that query excludes companies already in staging.glassdoor_companies."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.fetchall.return_value = []
        
        extractor = CompanyExtractor(
            db_connection_string="postgresql://test:test@localhost/test",
            glassdoor_api_key="test_key"
        )
        
        extractor.get_companies_to_enrich()
        
        # Verify execute was called
        execute_calls = mock_cursor.execute.call_args_list
        assert len(execute_calls) > 0
        
        # Get the query from the call
        last_call = execute_calls[-1]
        query = last_call[0][0] if last_call[0] else ""
        
        # Verify query checks staging.glassdoor_companies
        assert "staging.glassdoor_companies" in query
        assert "company_lookup_key" in query
        assert "NOT IN" in query

