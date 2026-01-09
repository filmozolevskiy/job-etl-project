"""
Unit tests for ChatGPT Enrichment Service.

Tests API parameter construction, error handling, JSON parsing, and enrichment logic.
"""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

import pytest

from services.enricher.chatgpt_enricher import ChatGPTEnricher
from services.shared import Database


class MockDatabase:
    """Simple mock Database implementation for testing."""

    def __init__(self):
        self.cursor = MagicMock()

    @contextmanager
    def get_cursor(self):
        """Context manager that yields a mock cursor."""
        yield self.cursor


class TestChatGPTEnricherInitialization:
    """Test ChatGPTEnricher initialization."""

    def test_init_with_valid_params(self):
        """Test initialization with valid parameters."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(
                database=mock_db,
                api_key="test-key",
                model="gpt-4",
                batch_size=5,
            )
            assert enricher.db == mock_db
            assert enricher.api_key == "test-key"
            assert enricher.model == "gpt-4"
            assert enricher.batch_size == 5

    def test_init_without_openai_raises_error(self):
        """Test that initialization fails if OpenAI is not installed."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI", None):
            with pytest.raises(ValueError, match="OpenAI library is not installed"):
                ChatGPTEnricher(database=mock_db, api_key="test-key")

    def test_init_without_api_key_raises_error(self):
        """Test that initialization fails without API key."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(ValueError, match="OpenAI API key is required"):
                    ChatGPTEnricher(database=mock_db, api_key=None)

    def test_init_with_invalid_batch_size_raises_error(self):
        """Test that initialization fails with invalid batch size."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            with pytest.raises(ValueError, match="batch_size must be a positive integer"):
                ChatGPTEnricher(database=mock_db, api_key="test-key", batch_size=0)


class TestChatGPTEnricherHelperMethods:
    """Test helper methods for API parameter building and error handling."""

    def test_build_api_params_older_model(self):
        """Test API parameter building for older models."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key", model="gpt-3.5-turbo")
            params = enricher._build_api_params(is_batch=False, batch_size=1)
            assert "max_tokens" in params
            assert params["temperature"] == 0.3
            assert "max_completion_tokens" not in params

    def test_build_api_params_newer_model(self):
        """Test API parameter building for newer models."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key", model="gpt-4o")
            params = enricher._build_api_params(is_batch=False, batch_size=1)
            assert "max_completion_tokens" in params
            assert params["max_completion_tokens"] == 500
            assert "temperature" not in params

    def test_build_api_params_reasoning_model(self):
        """Test API parameter building for reasoning models."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key", model="o1-preview")
            params = enricher._build_api_params(is_batch=False, batch_size=1)
            assert "max_completion_tokens" in params
            assert params["max_completion_tokens"] == 4000

    def test_build_api_params_batch(self):
        """Test API parameter building for batch requests."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key", model="gpt-4o")
            params = enricher._build_api_params(is_batch=True, batch_size=5)
            assert params["max_completion_tokens"] == 2500  # 500 * 5, capped at 4000

    def test_extract_error_details_from_dict_body(self):
        """Test error detail extraction from dict body."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            # Create Mock with only 'body' attribute to avoid response attribute interference
            error = Mock(spec=["body"])
            error.body = {"error": {"message": "Rate limit exceeded"}}
            error_message, error_body = enricher._extract_error_details(error)
            assert error_message == "Rate limit exceeded"
            assert error_body == {"error": {"message": "Rate limit exceeded"}}

    def test_extract_error_details_from_string_body(self):
        """Test error detail extraction from string body."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            # Create Mock with only 'body' attribute to avoid response attribute interference
            error = Mock(spec=["body"])
            error.body = '{"error": {"message": "Invalid API key"}}'
            error_message, error_body = enricher._extract_error_details(error)
            assert error_message == "Invalid API key"
            assert isinstance(error_body, dict)

    def test_should_retry_without_json(self):
        """Test detection of JSON mode unsupported errors."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            assert enricher._should_retry_without_json("response_format is not supported", None)
            assert enricher._should_retry_without_json(
                "unsupported parameter response_format", None
            )

    def test_is_authentication_error(self):
        """Test detection of authentication errors."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            assert enricher._is_authentication_error("401 Unauthorized")
            assert enricher._is_authentication_error("invalid_api_key")
            assert enricher._is_authentication_error("authentication failed")

    def test_parse_json_response_plain_json(self):
        """Test parsing plain JSON response."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            response = '{"summary": "Test", "skills": ["Python"]}'
            result = enricher._parse_json_response(response)
            assert isinstance(result, dict)
            assert result["summary"] == "Test"

    def test_parse_json_response_markdown_wrapped(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            response = '```json\n{"summary": "Test"}\n```'
            result = enricher._parse_json_response(response)
            assert isinstance(result, dict)
            assert result["summary"] == "Test"

    def test_extract_enrichment_from_result(self):
        """Test extraction of enrichment data from API result."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            result = {
                "summary": "Test summary",
                "skills": ["Python", "SQL"],
                "location": "Toronto, ON, Canada",
                "seniority_level": "senior",
                "remote_work_type": "remote",
                "min_salary": 100000,
                "max_salary": 150000,
                "salary_period": "year",
                "salary_currency": "USD",
            }
            enrichment = enricher._extract_enrichment_from_result(result, job_key=1)
            assert enrichment["job_summary"] == "Test summary"
            assert enrichment["chatgpt_extracted_skills"] == ["Python", "SQL"]
            assert enrichment["chatgpt_extracted_location"] == "Toronto, ON, Canada"
            assert enrichment["chatgpt_seniority_level"] == "senior"
            assert enrichment["chatgpt_remote_work_type"] == "remote"
            assert enrichment["chatgpt_job_min_salary"] == 100000.0
            assert enrichment["chatgpt_job_max_salary"] == 150000.0
            assert enrichment["chatgpt_salary_period"] == "year"
            assert enrichment["chatgpt_salary_currency"] == "USD"

    def test_extract_enrichment_invalid_seniority(self):
        """Test that invalid seniority levels are set to None."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            result = {"seniority_level": "invalid_level"}
            enrichment = enricher._extract_enrichment_from_result(result, job_key=1)
            assert enrichment["chatgpt_seniority_level"] is None

    def test_extract_enrichment_invalid_remote_type(self):
        """Test that invalid remote work types are set to None."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            result = {"remote_work_type": "invalid_type"}
            enrichment = enricher._extract_enrichment_from_result(result, job_key=1)
            assert enrichment["chatgpt_remote_work_type"] is None

    def test_get_empty_enrichment(self):
        """Test getting empty enrichment dictionary."""
        mock_db = Mock(spec=Database)
        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            empty = enricher._get_empty_enrichment()
            assert all(v is None for v in empty.values())
            assert "job_summary" in empty
            assert "chatgpt_extracted_skills" in empty


class TestChatGPTEnricherAPICalls:
    """Test OpenAI API call methods."""

    @patch("services.enricher.chatgpt_enricher.OpenAI")
    def test_call_openai_api_success(self, mock_openai_class):
        """Test successful API call."""
        mock_db = Mock(spec=Database)
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"summary": "Test"}'))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
        result = enricher._call_openai_api("Test prompt")

        assert result == '{"summary": "Test"}'
        mock_client.chat.completions.create.assert_called_once()

    @patch("services.enricher.chatgpt_enricher.OpenAI")
    def test_call_openai_api_empty_response(self, mock_openai_class):
        """Test API call with empty response."""
        mock_db = Mock(spec=Database)
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = []
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
        result = enricher._call_openai_api("Test prompt")

        assert result is None

    @patch("services.enricher.chatgpt_enricher.OpenAI")
    @patch("time.sleep")
    def test_call_openai_api_retry_on_error(self, mock_sleep, mock_openai_class):
        """Test that API call retries on error."""
        mock_db = Mock(spec=Database)
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            Exception("Temporary error"),
            MagicMock(choices=[MagicMock(message=MagicMock(content='{"summary": "Test"}'))]),
        ]
        mock_openai_class.return_value = mock_client

        enricher = ChatGPTEnricher(
            database=mock_db, api_key="test-key", max_retries=3, retry_delay=0.1
        )
        result = enricher._call_openai_api("Test prompt")

        assert result == '{"summary": "Test"}'
        assert mock_client.chat.completions.create.call_count == 2
        mock_sleep.assert_called_once()

    @patch("services.enricher.chatgpt_enricher.OpenAI")
    def test_call_openai_api_auth_error_no_retry(self, mock_openai_class):
        """Test that authentication errors don't retry."""
        mock_db = Mock(spec=Database)
        mock_client = MagicMock()
        error = Exception("401 Unauthorized")
        mock_client.chat.completions.create.side_effect = error
        mock_openai_class.return_value = mock_client

        enricher = ChatGPTEnricher(database=mock_db, api_key="test-key", max_retries=3)
        result = enricher._call_openai_api("Test prompt")

        assert result is None
        # Should only call once, not retry
        assert mock_client.chat.completions.create.call_count == 1


class TestChatGPTEnricherEnrichment:
    """Test job enrichment methods."""

    @patch("services.enricher.chatgpt_enricher.OpenAI")
    def test_enrich_job_success(self, mock_openai_class):
        """Test successful job enrichment."""
        mock_db = Mock(spec=Database)
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "summary": "Test summary",
                            "skills": ["Python"],
                            "location": "Toronto, ON",
                        }
                    )
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Engineer",
            "job_description": "Python developer needed",
        }
        result = enricher.enrich_job(job)

        assert result["job_summary"] == "Test summary"
        assert result["chatgpt_extracted_skills"] == ["Python"]
        assert result["chatgpt_extracted_location"] == "Toronto, ON"

    @patch("services.enricher.chatgpt_enricher.OpenAI")
    def test_enrich_job_api_failure(self, mock_openai_class):
        """Test job enrichment when API fails."""
        mock_db = Mock(spec=Database)
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_client

        enricher = ChatGPTEnricher(database=mock_db, api_key="test-key", max_retries=1)
        job = {"jsearch_job_postings_key": 1, "job_title": "Test"}
        result = enricher.enrich_job(job)

        assert all(v is None for v in result.values())

    @patch("services.enricher.chatgpt_enricher.OpenAI")
    def test_enrich_jobs_batch_success(self, mock_openai_class):
        """Test successful batch enrichment."""
        mock_db = Mock(spec=Database)
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "jobs": [
                                {
                                    "summary": "Job 1",
                                    "skills": ["Python"],
                                    "location": "Toronto",
                                },
                                {
                                    "summary": "Job 2",
                                    "skills": ["Java"],
                                    "location": "Vancouver",
                                },
                            ]
                        }
                    )
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
        jobs = [
            {"jsearch_job_postings_key": 1, "job_title": "Job 1"},
            {"jsearch_job_postings_key": 2, "job_title": "Job 2"},
        ]
        results = enricher.enrich_jobs_batch(jobs)

        assert len(results) == 2
        assert results[0]["job_summary"] == "Job 1"
        assert results[1]["job_summary"] == "Job 2"

    @patch("services.enricher.chatgpt_enricher.OpenAI")
    def test_enrich_jobs_batch_fewer_results(self, mock_openai_class):
        """Test batch enrichment when fewer results than jobs."""
        mock_db = Mock(spec=Database)
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {"jobs": [{"summary": "Job 1", "skills": [], "location": None}]}
                    )
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
        jobs = [
            {"jsearch_job_postings_key": 1, "job_title": "Job 1"},
            {"jsearch_job_postings_key": 2, "job_title": "Job 2"},
        ]
        results = enricher.enrich_jobs_batch(jobs)

        assert len(results) == 2
        assert results[0]["job_summary"] == "Job 1"
        assert all(v is None for v in results[1].values())  # Second job padded with None


class TestChatGPTEnricherDatabaseOperations:
    """Test database operations."""

    def test_get_jobs_to_enrich(self):
        """Test getting jobs that need enrichment."""
        mock_db = MockDatabase()
        mock_db.cursor.description = [
            ("jsearch_job_postings_key",),
            ("job_title",),
            ("job_description",),
        ]
        mock_db.cursor.fetchall.return_value = [(1, "Engineer", "Python dev")]

        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            jobs = enricher.get_jobs_to_enrich(limit=10)

            assert len(jobs) == 1
            assert jobs[0]["jsearch_job_postings_key"] == 1

    def test_update_job_enrichment(self):
        """Test updating job enrichment in database."""
        mock_db = MockDatabase()

        with patch("services.enricher.chatgpt_enricher.OpenAI"):
            enricher = ChatGPTEnricher(database=mock_db, api_key="test-key")
            enricher.update_job_enrichment(
                job_key=1,
                job_summary="Test summary",
                chatgpt_extracted_skills=["Python"],
                chatgpt_extracted_location="Toronto",
            )

            mock_db.cursor.execute.assert_called_once()
            call_args = mock_db.cursor.execute.call_args
            # The query is an INSERT ... ON CONFLICT (upsert), check for the actual SQL pattern
            assert "INSERT INTO staging.chatgpt_enrichments" in str(call_args[0][0])
            assert "ON CONFLICT" in str(call_args[0][0])
