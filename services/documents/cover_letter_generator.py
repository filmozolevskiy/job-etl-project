"""ChatGPT-powered cover letter generation service."""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    from jobs.job_service import JobService
    from shared.database import Database

    from .cover_letter_service import CoverLetterService
    from .resume_service import ResumeService
    from .storage_service import StorageService

from .resume_text_extractor import extract_text_from_resume

logger = logging.getLogger(__name__)


class CoverLetterGenerationError(Exception):
    """Raised when cover letter generation fails."""

    pass


class CoverLetterGenerator:
    """Service for generating cover letters using ChatGPT API.

    Takes a user's resume and a job description, then generates a personalized
    cover letter using OpenAI's ChatGPT API.
    """

    def __init__(
        self,
        database: Database,
        cover_letter_service: CoverLetterService,
        resume_service: ResumeService,
        job_service: JobService,
        storage_service: StorageService,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize the cover letter generator.

        Args:
            database: Database connection interface
            cover_letter_service: Cover letter service for storing generated letters
            resume_service: Resume service for accessing resume data
            job_service: Job service for accessing job details
            storage_service: Storage service for reading resume files
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY environment variable.
            model: OpenAI model to use (default: gpt-4o-mini for cost efficiency)
            max_retries: Maximum number of retries for API calls
            retry_delay: Base delay in seconds between retries (exponential backoff)

        Raises:
            ValueError: If database is None, OpenAI is not installed, or API key is missing
        """
        if not database:
            raise ValueError("Database is required")
        if not cover_letter_service:
            raise ValueError("Cover letter service is required")
        if not resume_service:
            raise ValueError("Resume service is required")
        if not job_service:
            raise ValueError("Job service is required")
        if not storage_service:
            raise ValueError("Storage service is required")

        if OpenAI is None:
            raise ValueError(
                "OpenAI library is not installed. Install with: pip install openai>=1.0.0"
            )

        self.db = database
        self.cover_letter_service = cover_letter_service
        self.resume_service = resume_service
        self.job_service = job_service
        self.storage_service = storage_service
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Get API key from parameter or environment variable
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key or self.api_key.lower() in ("test", "none", ""):
            raise ValueError(
                "OpenAI API key is required and must be valid. "
                "Set OPENAI_API_KEY environment variable or pass api_key parameter. "
                "Current value appears to be invalid."
            )

        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)

    def generate_cover_letter(
        self,
        resume_id: int,
        jsearch_job_id: str,
        user_id: int,
        user_comments: str | None = None,
    ) -> dict[str, Any]:
        """Generate a cover letter using ChatGPT.

        Args:
            resume_id: Resume ID to use for generation
            jsearch_job_id: Job ID to generate cover letter for
            user_id: User ID (for ownership validation)
            user_comments: Optional user instructions/comments for customization

        Returns:
            Dictionary with generated cover letter data including:
            - cover_letter_id: ID of created cover letter
            - cover_letter_text: Generated text
            - cover_letter_name: Generated name
            - generation_prompt: Prompt used for generation

        Raises:
            CoverLetterGenerationError: If generation fails
            ValueError: If resume or job not found, or user doesn't own them
        """
        logger.info(
            f"Generating cover letter for job {jsearch_job_id} with resume {resume_id} (user {user_id})"
        )

        # Extract resume text
        try:
            resume_text = extract_text_from_resume(
                resume_id=resume_id,
                user_id=user_id,
                storage_service=self.storage_service,
                database=self.db,
            )
            if not resume_text or not resume_text.strip():
                raise CoverLetterGenerationError("Resume text extraction returned empty content")
        except Exception as e:
            if isinstance(e, CoverLetterGenerationError):
                raise
            raise CoverLetterGenerationError(f"Failed to extract resume text: {e}") from e

        # Get job details
        job = self.job_service.get_job_by_id(jsearch_job_id, user_id)
        if not job:
            raise ValueError(f"Job {jsearch_job_id} not found or access denied")

        job_title = job.get("job_title", "Position")
        company_name = job.get("company_name", "Company")
        job_description = job.get("job_description", "")

        # Build prompt
        prompt = self._build_prompt(resume_text, job_title, company_name, job_description, user_comments)

        # Call ChatGPT API
        try:
            generated_text = self._call_chatgpt_api(prompt)
        except Exception as e:
            raise CoverLetterGenerationError(f"Failed to generate cover letter: {e}") from e

        if not generated_text or not generated_text.strip():
            raise CoverLetterGenerationError("ChatGPT API returned empty response")

        # Generate cover letter name
        cover_letter_name = f"Cover Letter - {company_name} - {job_title}"

        # Store generated cover letter
        try:
            cover_letter = self.cover_letter_service.create_cover_letter(
                user_id=user_id,
                cover_letter_name=cover_letter_name,
                cover_letter_text=generated_text,
                jsearch_job_id=jsearch_job_id,
                is_generated=True,
                generation_prompt=prompt,
                in_documents_section=False,
            )
            logger.info(
                f"Successfully generated and stored cover letter {cover_letter['cover_letter_id']} "
                f"for job {jsearch_job_id}"
            )
            return cover_letter
        except Exception as e:
            raise CoverLetterGenerationError(f"Failed to store generated cover letter: {e}") from e

    def _build_prompt(
        self,
        resume_text: str,
        job_title: str,
        company_name: str,
        job_description: str,
        user_comments: str | None = None,
    ) -> str:
        """Build the ChatGPT prompt for cover letter generation.

        Args:
            resume_text: Extracted text from user's resume
            job_title: Job title
            company_name: Company name
            job_description: Full job description
            user_comments: Optional user instructions

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "You are a professional cover letter writer. Generate a personalized cover letter based on the following information:",
            "",
            "RESUME:",
            resume_text,
            "",
            "JOB INFORMATION:",
            f"Job Title: {job_title}",
            f"Company: {company_name}",
            "",
            "JOB DESCRIPTION:",
            job_description,
        ]

        if user_comments and user_comments.strip():
            prompt_parts.extend(["", "USER INSTRUCTIONS:", user_comments])

        prompt_parts.extend([
            "",
            "REQUIREMENTS:",
            "- Write in a professional, confident tone",
            "- Highlight relevant skills and experiences from the resume that match the job requirements",
            "- Show enthusiasm for the specific role and company",
            "- Keep it concise: 3-4 paragraphs",
            "- Include a professional greeting (e.g., 'Dear Hiring Manager' or 'Dear [Company Name] Team')",
            "- Include a professional closing with your name",
            "- Do not include placeholders like [Your Name] or [Date] - write as if it's ready to send",
            "",
            "Generate the cover letter now:",
        ])

        return "\n".join(prompt_parts)

    def _call_chatgpt_api(self, prompt: str) -> str:
        """Call ChatGPT API to generate cover letter text.

        Args:
            prompt: The prompt to send to ChatGPT

        Returns:
            Generated cover letter text

        Raises:
            CoverLetterGenerationError: If API call fails after retries
        """
        api_params = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a professional cover letter writer."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
        }

        # Determine timeout based on model
        timeout = 60.0  # Default timeout
        if "gpt-4o" in self.model.lower() or "gpt-5" in self.model.lower():
            timeout = 60.0
        elif "o1" in self.model.lower() or "o3" in self.model.lower():
            timeout = 180.0

        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Calling ChatGPT API (attempt {attempt + 1}/{self.max_retries})")
                response = self.client.chat.completions.create(**api_params, timeout=timeout)

                if not response.choices or not response.choices[0].message:
                    raise CoverLetterGenerationError("Empty response from ChatGPT API")

                generated_text = response.choices[0].message.content
                if not generated_text:
                    raise CoverLetterGenerationError("No content in ChatGPT API response")

                logger.debug("Successfully received response from ChatGPT API")
                return generated_text.strip()

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Don't retry on authentication errors
                if "401" in error_str or "invalid_api_key" in error_str or "authentication" in error_str:
                    raise CoverLetterGenerationError(
                        f"OpenAI API authentication failed: {e}"
                    ) from e

                # Don't retry on invalid request errors
                if "400" in error_str or "invalid_request" in error_str:
                    raise CoverLetterGenerationError(f"Invalid request to OpenAI API: {e}") from e

                # Retry with exponential backoff
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"ChatGPT API call failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"ChatGPT API call failed after {self.max_retries} attempts: {e}")

        raise CoverLetterGenerationError(
            f"Failed to generate cover letter after {self.max_retries} attempts: {last_error}"
        ) from last_error
