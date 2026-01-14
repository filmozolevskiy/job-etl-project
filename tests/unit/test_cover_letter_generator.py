"""Unit tests for cover letter generator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.documents.cover_letter_generator import (
    CoverLetterGenerationError,
    CoverLetterGenerator,
)


class TestCoverLetterGeneratorInitialization:
    """Test CoverLetterGenerator initialization."""

    def test_init_success(self):
        """Test successful initialization."""
        mock_db = MagicMock()
        mock_cover_letter_service = MagicMock()
        mock_resume_service = MagicMock()
        mock_job_service = MagicMock()
        mock_storage_service = MagicMock()

        with patch("services.documents.cover_letter_generator.OpenAI"):
            generator = CoverLetterGenerator(
                database=mock_db,
                cover_letter_service=mock_cover_letter_service,
                resume_service=mock_resume_service,
                job_service=mock_job_service,
                storage_service=mock_storage_service,
                api_key="test-key",
            )

            assert generator.db == mock_db
            assert generator.cover_letter_service == mock_cover_letter_service
            assert generator.resume_service == mock_resume_service
            assert generator.job_service == mock_job_service
            assert generator.storage_service == mock_storage_service
            assert generator.model == "gpt-4o-mini"
            assert generator.api_key == "test-key"

    def test_init_without_openai_raises_error(self):
        """Test that initialization fails if OpenAI is not installed."""
        mock_db = MagicMock()
        mock_cover_letter_service = MagicMock()
        mock_resume_service = MagicMock()
        mock_job_service = MagicMock()
        mock_storage_service = MagicMock()

        with patch("services.documents.cover_letter_generator.OpenAI", None):
            with pytest.raises(ValueError, match="OpenAI library is not installed"):
                CoverLetterGenerator(
                    database=mock_db,
                    cover_letter_service=mock_cover_letter_service,
                    resume_service=mock_resume_service,
                    job_service=mock_job_service,
                    storage_service=mock_storage_service,
                    api_key="test-key",
                )

    def test_init_without_database_raises_error(self):
        """Test that initialization fails without database."""
        mock_cover_letter_service = MagicMock()
        mock_resume_service = MagicMock()
        mock_job_service = MagicMock()
        mock_storage_service = MagicMock()

        with patch("services.documents.cover_letter_generator.OpenAI"):
            with pytest.raises(ValueError, match="Database is required"):
                CoverLetterGenerator(
                    database=None,
                    cover_letter_service=mock_cover_letter_service,
                    resume_service=mock_resume_service,
                    job_service=mock_job_service,
                    storage_service=mock_storage_service,
                    api_key="test-key",
                )

    def test_init_without_api_key_raises_error(self):
        """Test that initialization fails without API key."""
        mock_db = MagicMock()
        mock_cover_letter_service = MagicMock()
        mock_resume_service = MagicMock()
        mock_job_service = MagicMock()
        mock_storage_service = MagicMock()

        with patch("services.documents.cover_letter_generator.OpenAI"):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(ValueError, match="OpenAI API key is required"):
                    CoverLetterGenerator(
                        database=mock_db,
                        cover_letter_service=mock_cover_letter_service,
                        resume_service=mock_resume_service,
                        job_service=mock_job_service,
                        storage_service=mock_storage_service,
                    )


class TestBuildPrompt:
    """Test prompt building."""

    @pytest.fixture
    def generator(self):
        """Create a generator instance for testing."""
        mock_db = MagicMock()
        mock_cover_letter_service = MagicMock()
        mock_resume_service = MagicMock()
        mock_job_service = MagicMock()
        mock_storage_service = MagicMock()

        with patch("services.documents.cover_letter_generator.OpenAI"):
            return CoverLetterGenerator(
                database=mock_db,
                cover_letter_service=mock_cover_letter_service,
                resume_service=mock_resume_service,
                job_service=mock_job_service,
                storage_service=mock_storage_service,
                api_key="test-key",
            )

    def test_build_prompt_basic(self, generator):
        """Test basic prompt building."""
        prompt = generator._build_prompt(
            resume_text="John Doe\nSoftware Engineer\n5 years experience",
            job_title="Senior Software Engineer",
            company_name="Tech Corp",
            job_description="We are looking for an experienced software engineer...",
            user_comments=None,
        )

        assert "RESUME:" in prompt
        assert "John Doe" in prompt
        assert "JOB INFORMATION:" in prompt
        assert "Senior Software Engineer" in prompt
        assert "Tech Corp" in prompt
        assert "JOB DESCRIPTION:" in prompt
        assert "REQUIREMENTS:" in prompt

    def test_build_prompt_with_user_comments(self, generator):
        """Test prompt building with user comments."""
        prompt = generator._build_prompt(
            resume_text="Resume text",
            job_title="Developer",
            company_name="Company",
            job_description="Job description",
            user_comments="Please emphasize my Python experience",
        )

        assert "USER INSTRUCTIONS:" in prompt
        assert "Please emphasize my Python experience" in prompt


class TestCallChatGPTAPI:
    """Test ChatGPT API calls."""

    @pytest.fixture
    def generator(self):
        """Create a generator instance for testing."""
        mock_db = MagicMock()
        mock_cover_letter_service = MagicMock()
        mock_resume_service = MagicMock()
        mock_job_service = MagicMock()
        mock_storage_service = MagicMock()

        with patch("services.documents.cover_letter_generator.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            gen = CoverLetterGenerator(
                database=mock_db,
                cover_letter_service=mock_cover_letter_service,
                resume_service=mock_resume_service,
                job_service=mock_job_service,
                storage_service=mock_storage_service,
                api_key="test-key",
            )
            gen.client = mock_client
            return gen

    def test_call_chatgpt_api_success(self, generator):
        """Test successful API call."""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Generated cover letter text"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        generator.client.chat.completions.create.return_value = mock_response

        result = generator._call_chatgpt_api("Test prompt")

        assert result == "Generated cover letter text"
        generator.client.chat.completions.create.assert_called_once()

    def test_call_chatgpt_api_empty_response(self, generator):
        """Test API call with empty response."""
        mock_response = MagicMock()
        mock_response.choices = []
        generator.client.chat.completions.create.return_value = mock_response

        with pytest.raises(CoverLetterGenerationError, match="Empty response"):
            generator._call_chatgpt_api("Test prompt")

    def test_call_chatgpt_api_authentication_error(self, generator):
        """Test API call with authentication error."""
        error = Exception("401 Unauthorized")
        error.status_code = 401
        generator.client.chat.completions.create.side_effect = error

        with pytest.raises(CoverLetterGenerationError, match="authentication failed"):
            generator._call_chatgpt_api("Test prompt")

    def test_call_chatgpt_api_retry_on_failure(self, generator):
        """Test API call retries on failure."""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Generated text"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        # First call fails, second succeeds
        generator.client.chat.completions.create.side_effect = [
            Exception("Temporary error"),
            mock_response,
        ]

        with patch("time.sleep"):  # Skip actual sleep
            result = generator._call_chatgpt_api("Test prompt")

        assert result == "Generated text"
        assert generator.client.chat.completions.create.call_count == 2

    def test_call_chatgpt_api_max_retries_exceeded(self, generator):
        """Test API call fails after max retries."""
        generator.client.chat.completions.create.side_effect = Exception("Persistent error")

        with patch("time.sleep"):  # Skip actual sleep
            with pytest.raises(CoverLetterGenerationError, match="Failed to generate cover letter"):
                generator._call_chatgpt_api("Test prompt")

        assert generator.client.chat.completions.create.call_count == generator.max_retries


class TestGenerateCoverLetter:
    """Test full cover letter generation flow."""

    @pytest.fixture
    def generator(self):
        """Create a generator instance for testing."""
        mock_db = MagicMock()
        mock_cover_letter_service = MagicMock()
        mock_resume_service = MagicMock()
        mock_job_service = MagicMock()
        mock_storage_service = MagicMock()

        with patch("services.documents.cover_letter_generator.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            gen = CoverLetterGenerator(
                database=mock_db,
                cover_letter_service=mock_cover_letter_service,
                resume_service=mock_resume_service,
                job_service=mock_job_service,
                storage_service=mock_storage_service,
                api_key="test-key",
            )
            gen.client = mock_client
            return gen

    def test_generate_cover_letter_success(self, generator):
        """Test successful cover letter generation."""
        # Mock resume text extraction
        with patch(
            "services.documents.cover_letter_generator.extract_text_from_resume"
        ) as mock_extract:
            mock_extract.return_value = "Resume text content"

            # Mock job service
            generator.job_service.get_job_by_id.return_value = {
                "job_title": "Software Engineer",
                "company_name": "Tech Corp",
                "job_description": "Job description text",
            }

            # Mock ChatGPT API
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Generated cover letter"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            generator.client.chat.completions.create.return_value = mock_response

            # Mock cover letter service
            generator.cover_letter_service.create_cover_letter.return_value = {
                "cover_letter_id": 1,
                "cover_letter_text": "Generated cover letter",
                "cover_letter_name": "Cover Letter - Tech Corp - Software Engineer",
                "generation_prompt": "Test prompt",
            }

            result = generator.generate_cover_letter(
                resume_id=1, jsearch_job_id="job123", user_id=1
            )

            assert result["cover_letter_id"] == 1
            assert result["cover_letter_text"] == "Generated cover letter"
            generator.cover_letter_service.create_cover_letter.assert_called_once()
            call_kwargs = generator.cover_letter_service.create_cover_letter.call_args[1]
            assert call_kwargs["is_generated"] is True
            assert call_kwargs["jsearch_job_id"] == "job123"
            assert call_kwargs["user_id"] == 1

    def test_generate_cover_letter_job_not_found(self, generator):
        """Test generation when job is not found."""
        with patch(
            "services.documents.cover_letter_generator.extract_text_from_resume"
        ) as mock_extract:
            mock_extract.return_value = "Resume text"

            generator.job_service.get_job_by_id.return_value = None

            with pytest.raises(ValueError, match="not found or access denied"):
                generator.generate_cover_letter(resume_id=1, jsearch_job_id="job123", user_id=1)

    def test_generate_cover_letter_resume_extraction_fails(self, generator):
        """Test generation when resume extraction fails."""
        with patch(
            "services.documents.cover_letter_generator.extract_text_from_resume"
        ) as mock_extract:
            mock_extract.side_effect = Exception("Resume extraction failed")

            with pytest.raises(CoverLetterGenerationError, match="Failed to extract resume text"):
                generator.generate_cover_letter(resume_id=1, jsearch_job_id="job123", user_id=1)

    def test_generate_cover_letter_empty_resume_text(self, generator):
        """Test generation when resume text is empty."""
        with patch(
            "services.documents.cover_letter_generator.extract_text_from_resume"
        ) as mock_extract:
            mock_extract.return_value = "   "  # Only whitespace

            with pytest.raises(CoverLetterGenerationError, match="empty content"):
                generator.generate_cover_letter(resume_id=1, jsearch_job_id="job123", user_id=1)

    def test_generate_cover_letter_api_fails(self, generator):
        """Test generation when ChatGPT API fails."""
        with patch(
            "services.documents.cover_letter_generator.extract_text_from_resume"
        ) as mock_extract:
            mock_extract.return_value = "Resume text"

            generator.job_service.get_job_by_id.return_value = {
                "job_title": "Engineer",
                "company_name": "Company",
                "job_description": "Description",
            }

            generator.client.chat.completions.create.side_effect = Exception("API error")

            with patch("time.sleep"):  # Skip retry delays
                with pytest.raises(
                    CoverLetterGenerationError, match="Failed to generate cover letter"
                ):
                    generator.generate_cover_letter(resume_id=1, jsearch_job_id="job123", user_id=1)

    def test_generate_cover_letter_with_user_comments(self, generator):
        """Test generation with user comments."""
        with patch(
            "services.documents.cover_letter_generator.extract_text_from_resume"
        ) as mock_extract:
            mock_extract.return_value = "Resume text"

            generator.job_service.get_job_by_id.return_value = {
                "job_title": "Engineer",
                "company_name": "Company",
                "job_description": "Description",
            }

            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Generated letter"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            generator.client.chat.completions.create.return_value = mock_response

            generator.cover_letter_service.create_cover_letter.return_value = {
                "cover_letter_id": 1,
                "cover_letter_text": "Generated letter",
                "cover_letter_name": "Cover Letter - Company - Engineer",
                "generation_prompt": "Prompt",
            }

            result = generator.generate_cover_letter(
                resume_id=1,
                jsearch_job_id="job123",
                user_id=1,
                user_comments="Emphasize Python skills",
            )

            # Verify prompt includes user comments
            call_args = generator.client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            user_message = messages[1]["content"]
            assert "Emphasize Python skills" in user_message

            assert result["cover_letter_id"] == 1
