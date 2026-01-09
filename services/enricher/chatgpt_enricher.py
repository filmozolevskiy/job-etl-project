"""ChatGPT Enrichment Service.

Enriches job postings using OpenAI ChatGPT API to extract:
- Job summary (2 sentences)
- Skills list
- Normalized location
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment, misc]

from shared import Database

from .chatgpt_queries import (
    GET_ALL_JOBS_FOR_CHATGPT_ENRICHMENT,
    GET_JOBS_FOR_CHATGPT_ENRICHMENT,
    UPDATE_CHATGPT_ENRICHMENT,
)

logger = logging.getLogger(__name__)


def _run_in_thread(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Awaitable[Any]:
    """
    Helper to run a synchronous function in a thread pool.
    Compatible with Python 3.7+ (uses run_in_executor instead of to_thread).

    Args:
        func: Synchronous function to run in thread pool
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        Awaitable that resolves to the function's return value
    """
    try:
        # Try to get the running event loop (Python 3.7+)
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, get or create one
        loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: func(*args, **kwargs))


@dataclass
class BatchStatus:
    """Status tracking for a single batch."""

    batch_id: int
    status: str = "pending"  # pending, processing, completed, failed
    start_time: float = 0.0
    jobs_count: int = 0
    error: str | None = None


class ChatGPTEnricher:
    """
    Service for enriching job postings using OpenAI ChatGPT API.

    Reads jobs from staging.jsearch_job_postings that haven't been enriched yet,
    calls OpenAI API to extract job summary, skills, and normalized location,
    and updates the staging table with the results.
    """

    def __init__(
        self,
        database: Database,
        api_key: str | None = None,
        model: str = "gpt-5-nano",
        batch_size: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        max_concurrent_batches: int | None = None,
        api_timeout_reasoning: float | None = None,
        api_timeout_standard: float | None = None,
        status_check_interval: float | None = None,
    ):
        """
        Initialize the ChatGPT enricher.

        Args:
            database: Database connection interface (implements Database protocol)
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY environment variable.
            model: OpenAI model to use (default: gpt-5-nano for cost efficiency)
            batch_size: Number of jobs to process in each batch
            max_retries: Maximum number of retries for API calls
            retry_delay: Delay in seconds between retries
            max_concurrent_batches: Maximum number of batches to process concurrently.
                If None, reads from CHATGPT_MAX_CONCURRENT_BATCHES env var (default: 10)
            api_timeout_reasoning: Timeout for reasoning models in seconds.
                If None, reads from CHATGPT_API_TIMEOUT_REASONING env var (default: 180)
            api_timeout_standard: Timeout for non-reasoning models in seconds.
                If None, reads from CHATGPT_API_TIMEOUT_STANDARD env var (default: 60)
            status_check_interval: Interval for status logging in seconds.
                If None, reads from CHATGPT_STATUS_CHECK_INTERVAL env var (default: 5)

        Raises:
            ValueError: If database is None, OpenAI is not installed, or API key is missing
        """
        if not database:
            raise ValueError("Database is required")

        if OpenAI is None:
            raise ValueError(
                "OpenAI library is not installed. Install with: pip install openai>=1.0.0"
            )

        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError(f"batch_size must be a positive integer, got: {batch_size}")

        self.db = database
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.model = model

        # Get API key from parameter or environment variable
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key or self.api_key.lower() in ("test", "none", ""):
            raise ValueError(
                "OpenAI API key is required and must be valid. "
                "Set OPENAI_API_KEY environment variable or pass api_key parameter. "
                "Current value appears to be invalid."
            )

        # Get concurrency and timeout settings from parameters or environment variables
        self.max_concurrent_batches = max_concurrent_batches
        if self.max_concurrent_batches is None:
            env_value = os.getenv("CHATGPT_MAX_CONCURRENT_BATCHES")
            self.max_concurrent_batches = int(env_value) if env_value else 10

        self.api_timeout_reasoning = api_timeout_reasoning
        if self.api_timeout_reasoning is None:
            env_value = os.getenv("CHATGPT_API_TIMEOUT_REASONING")
            self.api_timeout_reasoning = float(env_value) if env_value else 180.0

        self.api_timeout_standard = api_timeout_standard
        if self.api_timeout_standard is None:
            env_value = os.getenv("CHATGPT_API_TIMEOUT_STANDARD")
            self.api_timeout_standard = float(env_value) if env_value else 60.0

        self.status_check_interval = status_check_interval
        if self.status_check_interval is None:
            env_value = os.getenv("CHATGPT_STATUS_CHECK_INTERVAL")
            self.status_check_interval = float(env_value) if env_value else 5.0

        # Initialize OpenAI client (timeout will be set per-call based on model type)
        self.client = OpenAI(api_key=self.api_key)

    def _build_api_params(self, is_batch: bool = False, batch_size: int = 1) -> dict[str, Any]:
        """
        Build API parameters based on model type.

        Args:
            is_batch: Whether this is a batch request
            batch_size: Number of items in batch (for token calculation)

        Returns:
            Dictionary of API parameters
        """
        model_lower = self.model.lower()
        is_newer_model = (
            "o1" in model_lower
            or "o3" in model_lower
            or "gpt-5" in model_lower
            or "gpt-4o" in model_lower
        )
        is_reasoning_model = "o1" in model_lower or "o3" in model_lower or "gpt-5" in model_lower

        api_params: dict[str, Any] = {
            "model": self.model,
        }

        if is_newer_model:
            if is_reasoning_model:
                # For batch processing, increase tokens significantly
                max_tokens = min(4000 * batch_size, 16000) if is_batch else 4000
                api_params["max_completion_tokens"] = max_tokens
                logger.debug(
                    f"Using reasoning model parameters for {self.model}: "
                    f"max_completion_tokens={max_tokens}, no temperature"
                )
            else:
                max_tokens = min(500 * batch_size, 4000) if is_batch else 500
                api_params["max_completion_tokens"] = max_tokens
                logger.debug(
                    f"Using newer model parameters for {self.model}: "
                    f"max_completion_tokens={max_tokens}, no temperature"
                )
        else:
            max_tokens = min(500 * batch_size, 4000) if is_batch else 500
            api_params["max_tokens"] = max_tokens
            api_params["temperature"] = 0.3
            logger.debug(
                f"Using older model parameters for {self.model}: "
                f"max_tokens={max_tokens}, temperature=0.3"
            )

        return api_params

    def _extract_error_details(
        self, exception: Exception
    ) -> tuple[str | None, dict[str, Any] | None]:
        """
        Extract error message and body from OpenAI API exception.

        Args:
            exception: The exception to extract details from

        Returns:
            Tuple of (error_message, error_body)
        """
        error_message: str | None = None
        error_body: dict[str, Any] | None = None

        # Try to get error details from OpenAI exception structure
        if hasattr(exception, "body"):
            try:
                if isinstance(exception.body, dict):
                    error_body = exception.body
                    if "error" in error_body and isinstance(error_body["error"], dict):
                        error_message = error_body["error"].get("message", "")
                        logger.error(f"OpenAI API error body (dict): {error_body}")
                elif isinstance(exception.body, str):
                    try:
                        error_body = json.loads(exception.body)
                        if isinstance(error_body, dict) and "error" in error_body:
                            error_message = error_body["error"].get("message", "")
                        logger.error(f"OpenAI API error body (parsed JSON): {error_body}")
                    except json.JSONDecodeError:
                        logger.error(f"OpenAI API error body (raw string): {exception.body}")
            except Exception as parse_error:
                logger.error(f"Failed to parse error body: {parse_error}", exc_info=True)

        if hasattr(exception, "response") and exception.response is not None:
            try:
                if hasattr(exception.response, "json"):
                    error_body = exception.response.json()
                    if isinstance(error_body, dict) and "error" in error_body:
                        error_message = error_body["error"].get("message", error_message)
                    logger.error(f"OpenAI API response JSON: {error_body}")
                elif hasattr(exception.response, "text"):
                    try:
                        error_body = json.loads(exception.response.text)
                        if isinstance(error_body, dict) and "error" in error_body:
                            error_message = error_body["error"].get("message", error_message)
                        logger.error(f"OpenAI API response text (parsed): {error_body}")
                    except json.JSONDecodeError:
                        logger.error(f"OpenAI API response text (raw): {exception.response.text}")
            except Exception as parse_error:
                logger.error(f"Failed to parse response: {parse_error}", exc_info=True)

        if hasattr(exception, "status_code"):
            logger.error(f"OpenAI API HTTP status code: {exception.status_code}")

        return error_message, error_body

    def _should_retry_without_json(self, error_str: str, error_message: str | None) -> bool:
        """
        Check if error indicates JSON mode is not supported.

        Args:
            error_str: String representation of the error
            error_message: Extracted error message from API

        Returns:
            True if should retry without JSON mode
        """
        return (
            "response_format" in error_str.lower()
            or ("unsupported" in error_str.lower() and "parameter" in error_str.lower())
            or (
                error_message
                and (
                    "response_format" in error_message.lower()
                    or "unsupported parameter" in error_message.lower()
                )
            )
        )

    def _is_authentication_error(self, error_str: str) -> bool:
        """
        Check if error is an authentication error.

        Args:
            error_str: String representation of the error

        Returns:
            True if authentication error
        """
        return (
            "401" in error_str
            or "invalid_api_key" in error_str.lower()
            or "authentication" in error_str.lower()
        )

    def _parse_json_response(self, response_text: str) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Parse JSON response, handling markdown code blocks.

        Args:
            response_text: Raw response text from API

        Returns:
            Parsed JSON data (dict or list)

        Raises:
            json.JSONDecodeError: If response cannot be parsed as JSON
        """
        # Sometimes ChatGPT wraps JSON in markdown code blocks
        response_text = response_text.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            json_lines = [line for line in lines if not line.strip().startswith("```")]
            response_text = "\n".join(json_lines)

        return json.loads(response_text)

    def _extract_enrichment_from_result(
        self, result: dict[str, Any], job_key: int | str = "unknown"
    ) -> dict[str, Any]:
        """
        Extract enrichment data from a single result dictionary.

        Args:
            result: Result dictionary from API response
            job_key: Job key for logging (optional)

        Returns:
            Dictionary with enrichment fields
        """
        # Handle job_summary
        summary_raw = result.get("summary")
        job_summary = summary_raw.strip() if summary_raw and isinstance(summary_raw, str) else None

        # Handle skills
        skills_list = result.get("skills", [])
        if isinstance(skills_list, list):
            skills_list = [s.strip() for s in skills_list if s and isinstance(s, str) and s.strip()]
        else:
            skills_list = []

        # Handle location
        location_raw = result.get("location")
        location = location_raw.strip() if location_raw and isinstance(location_raw, str) else None

        # Extract seniority level (normalize to lowercase)
        seniority_raw = result.get("seniority_level")
        seniority_level: str | None = None
        if seniority_raw and isinstance(seniority_raw, str):
            seniority_level = seniority_raw.strip().lower() or None
            if seniority_level and seniority_level not in [
                "intern",
                "junior",
                "mid",
                "senior",
                "executive",
            ]:
                logger.warning(
                    f"Invalid seniority_level '{seniority_level}' for job {job_key}, setting to None"
                )
                seniority_level = None

        # Extract remote work type (normalize to lowercase)
        remote_raw = result.get("remote_work_type")
        remote_work_type: str | None = None
        if remote_raw and isinstance(remote_raw, str):
            remote_work_type = remote_raw.strip().lower() or None
            if remote_work_type and remote_work_type not in [
                "remote",
                "hybrid",
                "onsite",
            ]:
                logger.warning(
                    f"Invalid remote_work_type '{remote_work_type}' for job {job_key}, setting to None"
                )
                remote_work_type = None

        # Extract salary fields
        min_salary: float | None = None
        min_salary_raw = result.get("min_salary")
        if min_salary_raw is not None:
            try:
                min_salary = float(min_salary_raw) if min_salary_raw != "" else None
            except (ValueError, TypeError):
                min_salary = None

        max_salary: float | None = None
        max_salary_raw = result.get("max_salary")
        if max_salary_raw is not None:
            try:
                max_salary = float(max_salary_raw) if max_salary_raw != "" else None
            except (ValueError, TypeError):
                max_salary = None

        # Extract salary period (normalize to lowercase)
        period_raw = result.get("salary_period")
        salary_period: str | None = None
        if period_raw and isinstance(period_raw, str):
            salary_period = period_raw.strip().lower() or None
            if salary_period and salary_period not in [
                "year",
                "month",
                "week",
                "day",
                "hour",
            ]:
                logger.warning(
                    f"Invalid salary_period '{salary_period}' for job {job_key}, setting to None"
                )
                salary_period = None

        # Extract salary currency (normalize to uppercase)
        currency_raw = result.get("salary_currency")
        salary_currency: str | None = None
        if currency_raw and isinstance(currency_raw, str):
            salary_currency = currency_raw.strip().upper() or None
            if salary_currency and salary_currency not in ["USD", "CAD", "EUR", "GBP"]:
                logger.warning(
                    f"Invalid salary_currency '{salary_currency}' for job {job_key}, setting to None"
                )
                salary_currency = None

        return {
            "job_summary": job_summary,
            "chatgpt_extracted_skills": skills_list if skills_list else None,
            "chatgpt_extracted_location": location,
            "chatgpt_seniority_level": seniority_level,
            "chatgpt_remote_work_type": remote_work_type,
            "chatgpt_job_min_salary": min_salary,
            "chatgpt_job_max_salary": max_salary,
            "chatgpt_salary_period": salary_period,
            "chatgpt_salary_currency": salary_currency,
        }

    def _get_empty_enrichment(self) -> dict[str, Any]:
        """
        Get empty enrichment dictionary with all fields set to None.

        Returns:
            Dictionary with all enrichment fields set to None
        """
        return {
            "job_summary": None,
            "chatgpt_extracted_skills": None,
            "chatgpt_extracted_location": None,
            "chatgpt_seniority_level": None,
            "chatgpt_remote_work_type": None,
            "chatgpt_job_min_salary": None,
            "chatgpt_job_max_salary": None,
            "chatgpt_salary_period": None,
            "chatgpt_salary_currency": None,
        }

    def get_jobs_to_enrich(
        self, limit: int | None = None, campaign_id: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Get jobs that need ChatGPT enrichment from staging.jsearch_job_postings.

        Args:
            limit: Optional limit on number of jobs to return. If None, uses batch_size.
            campaign_id: Optional campaign_id to filter jobs. If None, processes all campaigns.

        Returns:
            List of job dictionaries with jsearch_job_postings_key, jsearch_job_id,
            job_title, job_description, location fields, and employer_name
        """
        query_limit = limit if limit is not None else self.batch_size
        query = (
            GET_JOBS_FOR_CHATGPT_ENRICHMENT
            if limit is not None
            else GET_ALL_JOBS_FOR_CHATGPT_ENRICHMENT
        )

        with self.db.get_cursor() as cur:
            if limit is not None:
                cur.execute(query, (campaign_id, campaign_id, query_limit))
            else:
                cur.execute(query, (campaign_id, campaign_id))

            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, row)) for row in cur.fetchall()]

            logger.info(f"Found {len(jobs)} job(s) needing ChatGPT enrichment")
            return jobs

    def _call_openai_api(self, prompt: str, system_prompt: str | None = None) -> str | None:
        """
        Call OpenAI API with retry logic.

        Args:
            prompt: User prompt to send to ChatGPT
            system_prompt: Optional system prompt to set context

        Returns:
            Response text from ChatGPT, or None if all retries failed
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Track if we've tried without JSON mode (fallback if JSON mode not supported)
        tried_without_json = False

        for attempt in range(self.max_retries):
            try:
                # Build API parameters using helper method
                api_params = self._build_api_params(is_batch=False, batch_size=1)
                api_params["messages"] = messages

                # Try JSON mode unless we've already tried without it (fallback)
                if not tried_without_json:
                    api_params["response_format"] = {"type": "json_object"}
                    logger.debug("Using JSON mode for structured output")

                logger.info(
                    f"Calling OpenAI API with model={self.model}, params={list(api_params.keys())}"
                )
                logger.debug(
                    f"API call details - model: {self.model}, "
                    f"max_completion_tokens: {api_params.get('max_completion_tokens')}, "
                    f"max_tokens: {api_params.get('max_tokens')}, "
                    f"has_response_format: {'response_format' in api_params}"
                )

                try:
                    response = self.client.chat.completions.create(**api_params)
                    logger.info(
                        f"OpenAI API call succeeded. Response type: {type(response)}, "
                        f"has choices: {hasattr(response, 'choices')}"
                    )
                    if hasattr(response, "choices"):
                        logger.info(
                            f"Response choices count: {len(response.choices) if response.choices else 0}"
                        )
                        if response.choices:
                            content_length = (
                                len(response.choices[0].message.content)
                                if hasattr(response.choices[0].message, "content")
                                else "N/A"
                            )
                            logger.info(f"First choice content length: {content_length}")
                except Exception as api_call_error:
                    error_msg = (
                        f"OpenAI API call raised exception: "
                        f"{type(api_call_error).__name__}: {str(api_call_error)}"
                    )
                    logger.error(error_msg, exc_info=True)
                    logger.error(f"Exception type: {type(api_call_error)}")
                    logger.error(f"Exception args: {api_call_error.args}")
                    raise

                if (
                    not hasattr(response, "choices")
                    or not response.choices
                    or len(response.choices) == 0
                ):
                    logger.warning("OpenAI API returned empty or missing choices")
                    logger.warning(f"Response object: {response}")
                    return None

                content = (
                    response.choices[0].message.content.strip()
                    if hasattr(response.choices[0].message, "content")
                    else None
                )
                if not content:
                    logger.warning("OpenAI API returned empty content in response")
                    logger.warning(f"Response: {response}")
                    return None

                logger.info(
                    f"OpenAI API call successful, returning content (length: {len(content)})"
                )
                return content

            except Exception as e:
                error_msg = (
                    f"OpenAI API exception caught (attempt {attempt + 1}/{self.max_retries}): "
                    f"{type(e).__name__}: {str(e)}"
                )
                logger.error(error_msg, exc_info=True)
                logger.error(f"Exception details: {repr(e)}")

                error_str = str(e)
                error_type = type(e).__name__

                # Extract error details using helper method
                error_message, error_body = self._extract_error_details(e)

                # Build comprehensive error message
                full_error = f"{error_type}: {error_str}"
                if error_message:
                    full_error += f" | API Error Message: {error_message}"

                logger.error(
                    f"OpenAI API call failed (attempt {attempt + 1}/{self.max_retries}): {full_error}"
                )

                if error_body:
                    logger.error(f"Full API error response body: {error_body}")

                # Check if error is about unsupported response_format parameter
                if not tried_without_json and self._should_retry_without_json(
                    error_str, error_message
                ):
                    logger.warning(
                        f"JSON mode (response_format) not supported for model {self.model}. "
                        f"Retrying without JSON mode. Error: {error_message or error_str}"
                    )
                    tried_without_json = True
                    continue

                # Check for authentication errors (401) - don't retry these
                if self._is_authentication_error(error_str):
                    logger.error(
                        f"OpenAI API authentication failed: {full_error}. "
                        f"Check OPENAI_API_KEY environment variable. Skipping retries."
                    )
                    return None

                # Retry with exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    logger.info(f"Retrying OpenAI API call after {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    final_error_msg = (
                        f"All {self.max_retries} retries failed for OpenAI API call. "
                        f"Model: {self.model}, Final error: {full_error}"
                    )
                    logger.error(final_error_msg)
                    return None

        # This should not be reached, but log if it is
        logger.error(
            f"OpenAI API call failed: retry loop completed without returning. "
            f"Model: {self.model}, max_retries: {self.max_retries}"
        )
        return None

    async def _call_openai_api_async(
        self, prompt: str, system_prompt: str | None = None
    ) -> str | None:
        """
        Async version of _call_openai_api with timeout handling.

        Args:
            prompt: User prompt to send to ChatGPT
            system_prompt: Optional system prompt to set context

        Returns:
            Response text from ChatGPT, or None if all retries failed
        """
        # Determine timeout based on model type
        model_lower = self.model.lower()
        is_reasoning_model = "o1" in model_lower or "o3" in model_lower or "gpt-5" in model_lower
        timeout = self.api_timeout_reasoning if is_reasoning_model else self.api_timeout_standard

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Track if we've tried without JSON mode (fallback if JSON mode not supported)
        tried_without_json = False

        for attempt in range(self.max_retries):
            try:
                # Build API parameters using helper method
                api_params = self._build_api_params(is_batch=False, batch_size=1)
                api_params["messages"] = messages

                if not tried_without_json:
                    api_params["response_format"] = {"type": "json_object"}
                    logger.debug("Using JSON mode for async structured output")

                logger.info(f"Calling OpenAI API async with model={self.model}, timeout={timeout}s")

                # Run synchronous API call in thread pool with timeout
                def _make_api_call(params=api_params) -> Any:
                    return self.client.chat.completions.create(**params)

                try:
                    response = await asyncio.wait_for(
                        _run_in_thread(_make_api_call), timeout=timeout
                    )

                    if (
                        not hasattr(response, "choices")
                        or not response.choices
                        or len(response.choices) == 0
                    ):
                        logger.warning("OpenAI API returned empty or missing choices")
                        logger.warning(f"Response object: {response}")
                        return None

                    content = (
                        response.choices[0].message.content.strip()
                        if hasattr(response.choices[0].message, "content")
                        else None
                    )
                    if not content:
                        logger.warning("OpenAI API returned empty content in response")
                        logger.warning(f"Response: {response}")
                        return None

                    logger.info(
                        f"OpenAI API async call successful, returning content (length: {len(content)})"
                    )
                    return content

                except TimeoutError:
                    logger.error(
                        f"OpenAI API call timed out after {timeout}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (attempt + 1)
                        logger.info(f"Retrying after {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"All {self.max_retries} retries failed due to timeout")
                        return None

            except Exception as e:
                error_msg = (
                    f"OpenAI API async exception caught (attempt {attempt + 1}/{self.max_retries}): "
                    f"{type(e).__name__}: {str(e)}"
                )
                logger.error(error_msg, exc_info=True)
                logger.error(f"Exception details: {repr(e)}")

                error_str = str(e)
                error_type = type(e).__name__

                # Extract error details using helper method
                error_message, error_body = self._extract_error_details(e)

                # Build comprehensive error message
                full_error = f"{error_type}: {error_str}"
                if error_message:
                    full_error += f" | API Error Message: {error_message}"

                logger.error(
                    f"OpenAI API async call failed (attempt {attempt + 1}/{self.max_retries}): {full_error}"
                )

                if error_body:
                    logger.error(f"Full API error response body: {error_body}")

                # Check if error is about unsupported response_format parameter
                if not tried_without_json and self._should_retry_without_json(
                    error_str, error_message
                ):
                    logger.warning(
                        f"JSON mode (response_format) not supported for model {self.model}. "
                        f"Retrying without JSON mode. Error: {error_message or error_str}"
                    )
                    tried_without_json = True
                    continue

                # Check for authentication errors (401) - don't retry these
                if self._is_authentication_error(error_str):
                    logger.error(
                        f"OpenAI API authentication failed: {full_error}. "
                        f"Check OPENAI_API_KEY environment variable. Skipping retries."
                    )
                    return None

                # Retry with exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    logger.info(f"Retrying OpenAI API async call after {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    final_error_msg = (
                        f"All {self.max_retries} retries failed for OpenAI API async call. "
                        f"Model: {self.model}, Final error: {full_error}"
                    )
                    logger.error(final_error_msg)
                    return None

        logger.error(
            f"OpenAI API async call failed: retry loop completed without returning. "
            f"Model: {self.model}, max_retries: {self.max_retries}"
        )
        return None

    def _call_openai_api_batch(
        self, jobs: list[dict[str, Any]], system_prompt: str | None = None
    ) -> str | None:
        """
        Call OpenAI API with multiple jobs in a single request (batch processing).

        Args:
            jobs: List of job dictionaries to process in batch
            system_prompt: Optional system prompt to set context

        Returns:
            Response text from ChatGPT (JSON array), or None if all retries failed
        """
        if not jobs:
            return None

        # Build batch prompt with all jobs
        job_prompts = []
        for idx, job in enumerate(jobs):
            job_title = job.get("job_title", "") or ""
            job_description = job.get("job_description", "") or ""
            job_location = job.get("job_location", "") or ""
            job_city = job.get("job_city", "") or ""
            job_state = job.get("job_state", "") or ""
            job_country = job.get("job_country", "") or ""
            employer_name = job.get("employer_name", "") or ""
            job_key = job.get("jsearch_job_postings_key", idx)
            job_min_salary = job.get("job_min_salary")
            job_max_salary = job.get("job_max_salary")
            job_salary_period = job.get("job_salary_period", "") or ""
            job_is_remote = job.get("job_is_remote")
            job_employment_type = job.get("job_employment_type", "") or ""

            # Build location context
            location_parts = [p for p in [job_city, job_state, job_country] if p]
            location_context = ", ".join(location_parts) if location_parts else job_location

            # Build salary context if available
            salary_context = ""
            if job_min_salary is not None or job_max_salary is not None:
                salary_parts = []
                if job_min_salary is not None:
                    salary_parts.append(f"Min: {job_min_salary}")
                if job_max_salary is not None:
                    salary_parts.append(f"Max: {job_max_salary}")
                if job_salary_period:
                    salary_parts.append(f"Period: {job_salary_period}")
                salary_context = f"Salary: {', '.join(salary_parts)}"

            # Build employment context
            employment_context = ""
            if job_employment_type:
                employment_context = f"Employment Type: {job_employment_type}"
            if job_is_remote is not None:
                remote_text = "Remote: Yes" if job_is_remote else "Remote: No"
                if employment_context:
                    employment_context += f", {remote_text}"
                else:
                    employment_context = remote_text

            # Limit description to avoid token limits (first 1500 characters per job in batch)
            description_truncated = (
                job_description[:1500] if len(job_description) > 1500 else job_description
            )

            # Build job prompt with all available context
            prompt_parts = [
                f"Job {idx + 1} (ID: {job_key}):",
                f"Title: {job_title}",
                f"Company: {employer_name}",
                f"Location: {location_context}",
            ]
            if salary_context:
                prompt_parts.append(salary_context)
            if employment_context:
                prompt_parts.append(employment_context)
            prompt_parts.append(f"Description: {description_truncated}")

            job_prompt = "\n".join(prompt_parts) + "\n"
            job_prompts.append(job_prompt)

        batch_prompt = f"""Analyze the following {len(jobs)} job posting(s) and extract for each:
1. A 2-sentence summary of the role (max 2 sentences, be concise)
2. A list of technical skills and technologies mentioned (as a JSON array of strings)
3. A normalized location string (city, state/province, country format, e.g., "Toronto, ON, Canada")
4. Seniority level (must be one of: "intern", "junior", "mid", "senior", "executive" - lowercase)
5. Remote work type (must be one of: "remote", "hybrid", "onsite" - lowercase)
6. Minimum salary (numeric value, or null if not mentioned)
7. Maximum salary (numeric value, or null if not mentioned)
8. Salary period (must be one of: "year", "month", "week", "day", "hour" - lowercase, or null)
9. Salary currency (must be one of: "USD", "CAD", "EUR", "GBP" - uppercase, or null)

{chr(10).join(job_prompts)}

Respond with a JSON object containing a "jobs" array where each element corresponds to a job in order (Job 1 = index 0, Job 2 = index 1, etc.).
Each element in the "jobs" array should be in this exact format:
{{
  "summary": "First sentence. Second sentence.",
  "skills": ["skill1", "skill2", "skill3"],
  "location": "City, State/Province, Country",
  "seniority_level": "senior",
  "remote_work_type": "remote",
  "min_salary": 120000,
  "max_salary": 150000,
  "salary_period": "year",
  "salary_currency": "USD"
}}

IMPORTANT INSTRUCTIONS FOR MISSING DATA:
- summary: Always provide a 2-sentence summary. If insufficient information, write a brief summary based on the job title and any available details. Never use null.
- skills: Return an empty array [] if no skills are mentioned. Never use null.
- location: Use null if location cannot be determined from the posting. Try to infer from context if possible.
- seniority_level: Infer from job description if not explicitly stated. Use null only if absolutely no indication (title, requirements, experience level) can be found.
- remote_work_type: Infer from job description if not explicitly stated. Use null only if absolutely no indication can be found.
- min_salary, max_salary: Use null if not mentioned in the job posting. Do not infer or guess salary amounts.
- salary_period: Use null if not mentioned. If salary amounts are provided but period is unclear, use null.
- salary_currency: Use null if not mentioned. If salary amounts are provided but currency is unclear, use null.

Example response format:
{{
  "jobs": [
    {{"summary": "...", "skills": [...], "location": "...", "seniority_level": "senior", "remote_work_type": "remote", "min_salary": 120000, "max_salary": 150000, "salary_period": "year", "salary_currency": "USD"}},
    {{"summary": "...", "skills": [...], "location": "...", "seniority_level": "mid", "remote_work_type": "hybrid", "min_salary": null, "max_salary": null, "salary_period": null, "salary_currency": null}},
    {{"summary": "...", "skills": [], "location": null, "seniority_level": null, "remote_work_type": null, "min_salary": null, "max_salary": null, "salary_period": null, "salary_currency": null}}
  ]
}}"""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append(
                {
                    "role": "system",
                    "content": "You are a job posting analysis assistant. Extract structured information from job postings. You must respond with a valid JSON array. Be concise and accurate.",
                }
            )
        messages.append({"role": "user", "content": batch_prompt})

        # Track if we've tried without JSON mode (fallback if JSON mode not supported)
        tried_without_json = False

        for attempt in range(self.max_retries):
            try:
                # Build API parameters using helper method
                api_params = self._build_api_params(is_batch=True, batch_size=len(jobs))
                api_params["messages"] = messages

                # Try JSON mode unless we've already tried without it (fallback)
                if not tried_without_json:
                    api_params["response_format"] = {"type": "json_object"}
                    logger.debug("Using JSON mode for batch structured output")

                logger.info(
                    f"Calling OpenAI API batch with model={self.model}, jobs={len(jobs)}, params={list(api_params.keys())}"
                )

                try:
                    response = self.client.chat.completions.create(**api_params)
                    logger.info(
                        f"OpenAI API batch call succeeded. Response type: {type(response)}, has choices: {hasattr(response, 'choices')}"
                    )
                    if hasattr(response, "choices") and response.choices:
                        logger.info(f"Response choices count: {len(response.choices)}")
                        if response.choices[0].message.content:
                            logger.info(
                                f"First choice content length: {len(response.choices[0].message.content)}"
                            )
                except Exception as api_call_error:
                    error_msg = f"OpenAI API batch call raised exception: {type(api_call_error).__name__}: {str(api_call_error)}"
                    logger.error(error_msg, exc_info=True)
                    raise

                if (
                    not hasattr(response, "choices")
                    or not response.choices
                    or len(response.choices) == 0
                ):
                    logger.warning("OpenAI API batch returned empty or missing choices")
                    logger.warning(f"Response object: {response}")
                    return None

                content = (
                    response.choices[0].message.content.strip()
                    if hasattr(response.choices[0].message, "content")
                    else None
                )
                if not content:
                    logger.warning("OpenAI API batch returned empty content in response")
                    logger.warning(f"Response: {response}")
                    return None

                logger.info(
                    f"OpenAI API batch call successful, returning content (length: {len(content)})"
                )
                return content

            except Exception as e:
                error_msg = (
                    f"OpenAI API batch exception caught (attempt {attempt + 1}/{self.max_retries}): "
                    f"{type(e).__name__}: {str(e)}"
                )
                logger.error(error_msg, exc_info=True)
                logger.error(f"Exception details: {repr(e)}")

                error_str = str(e)
                error_type = type(e).__name__

                # Extract error details using helper method
                error_message, error_body = self._extract_error_details(e)

                # Build comprehensive error message
                full_error = f"{error_type}: {error_str}"
                if error_message:
                    full_error += f" | API Error Message: {error_message}"

                logger.error(
                    f"OpenAI API batch call failed (attempt {attempt + 1}/{self.max_retries}): {full_error}"
                )

                if error_body:
                    logger.error(f"Full API batch error response body: {error_body}")

                # Check if error is about unsupported response_format parameter
                if not tried_without_json and self._should_retry_without_json(
                    error_str, error_message
                ):
                    logger.warning(
                        f"JSON mode (response_format) not supported for model {self.model} in batch. "
                        f"Retrying without JSON mode. Error: {error_message or error_str}"
                    )
                    tried_without_json = True
                    continue

                # Check for authentication errors (401) - don't retry these
                if self._is_authentication_error(error_str):
                    logger.error(
                        f"OpenAI API batch authentication failed: {full_error}. "
                        f"Check OPENAI_API_KEY environment variable. Skipping retries."
                    )
                    return None

                # Retry with exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    logger.info(f"Retrying OpenAI API batch call after {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    final_error_msg = (
                        f"All {self.max_retries} retries failed for OpenAI API batch call. Model: {self.model}, "
                        f"Final error: {full_error}"
                    )
                    logger.error(final_error_msg)
                    return None

        logger.error(
            f"OpenAI API batch call failed: retry loop completed without returning. "
            f"Model: {self.model}, max_retries: {self.max_retries}"
        )
        return None

    async def _call_openai_api_batch_async(
        self, jobs: list[dict[str, Any]], system_prompt: str | None = None
    ) -> str | None:
        """
        Async version of _call_openai_api_batch with timeout handling.

        Args:
            jobs: List of job dictionaries to process in batch
            system_prompt: Optional system prompt to set context

        Returns:
            Response text from ChatGPT (JSON array), or None if all retries failed
        """
        # Determine timeout based on model type
        model_lower = self.model.lower()
        is_reasoning_model = "o1" in model_lower or "o3" in model_lower or "gpt-5" in model_lower
        timeout = self.api_timeout_reasoning if is_reasoning_model else self.api_timeout_standard

        # Use the sync version wrapped in asyncio with timeout
        for attempt in range(self.max_retries):
            try:
                response_text = await asyncio.wait_for(
                    _run_in_thread(self._call_openai_api_batch, jobs, system_prompt),
                    timeout=timeout,
                )
                return response_text
            except TimeoutError:
                logger.error(
                    f"OpenAI API batch call timed out after {timeout}s (attempt {attempt + 1}/{self.max_retries})"
                )
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    logger.info(f"Retrying after {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All {self.max_retries} retries failed due to timeout")
                    return None
            except Exception as e:
                logger.error(f"Error in async batch API call: {e}", exc_info=True)
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    await asyncio.sleep(wait_time)
                else:
                    return None

        return None

    def enrich_job(self, job: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich a single job using ChatGPT API.

        Args:
            job: Job dictionary with job_title, job_description, location fields

        Returns:
            Dictionary with job_summary, chatgpt_extracted_skills (list),
            and chatgpt_extracted_location (str)
        """
        job_title = job.get("job_title", "") or ""
        job_description = job.get("job_description", "") or ""
        job_location = job.get("job_location", "") or ""
        job_city = job.get("job_city", "") or ""
        job_state = job.get("job_state", "") or ""
        job_country = job.get("job_country", "") or ""
        employer_name = job.get("employer_name", "") or ""
        job_min_salary = job.get("job_min_salary")
        job_max_salary = job.get("job_max_salary")
        job_salary_period = job.get("job_salary_period", "") or ""
        job_is_remote = job.get("job_is_remote")
        job_employment_type = job.get("job_employment_type", "") or ""

        # Build location context
        location_parts = [p for p in [job_city, job_state, job_country] if p]
        location_context = ", ".join(location_parts) if location_parts else job_location

        # Build salary context if available
        salary_context = ""
        if job_min_salary is not None or job_max_salary is not None:
            salary_parts = []
            if job_min_salary is not None:
                salary_parts.append(f"Min: {job_min_salary}")
            if job_max_salary is not None:
                salary_parts.append(f"Max: {job_max_salary}")
            if job_salary_period:
                salary_parts.append(f"Period: {job_salary_period}")
            salary_context = f"Salary: {', '.join(salary_parts)}"

        # Build employment context
        employment_context = ""
        if job_employment_type:
            employment_context = f"Employment Type: {job_employment_type}"
        if job_is_remote is not None:
            remote_text = "Remote: Yes" if job_is_remote else "Remote: No"
            if employment_context:
                employment_context += f", {remote_text}"
            else:
                employment_context = remote_text

        # System prompt for consistent extraction
        # Note: response_format={"type": "json_object"} is set in API call, so response will be JSON
        system_prompt = """You are a job posting analysis assistant. Extract structured information from job postings.
You must respond with a valid JSON object. Be concise and accurate."""

        # Create comprehensive prompt for all extractions
        # Limit description to avoid token limits (first 2000 characters)
        description_truncated = (
            job_description[:2000] if len(job_description) > 2000 else job_description
        )

        # Build full prompt with all available context
        prompt_parts = [
            f"Job Title: {job_title}",
            f"Company: {employer_name}",
            f"Location: {location_context}",
        ]
        if salary_context:
            prompt_parts.append(salary_context)
        if employment_context:
            prompt_parts.append(employment_context)
        prompt_parts.append(f"Description: {description_truncated}")

        prompt = f"""Analyze the following job posting and extract:
1. A 2-sentence summary of the role (max 2 sentences, be concise)
2. A list of technical skills and technologies mentioned (as a JSON array of strings)
3. A normalized location string (city, state/province, country format, e.g., "Toronto, ON, Canada")
4. Seniority level (must be one of: "intern", "junior", "mid", "senior", "executive" - lowercase)
5. Remote work type (must be one of: "remote", "hybrid", "onsite" - lowercase)
6. Minimum salary (numeric value, or null if not mentioned)
7. Maximum salary (numeric value, or null if not mentioned)
8. Salary period (must be one of: "year", "month", "week", "day", "hour" - lowercase, or null)
9. Salary currency (must be one of: "USD", "CAD", "EUR", "GBP" - uppercase, or null)

{chr(10).join(prompt_parts)}

Respond with a JSON object in this exact format:
{{
  "summary": "First sentence. Second sentence.",
  "skills": ["skill1", "skill2", "skill3"],
  "location": "City, State/Province, Country",
  "seniority_level": "senior",
  "remote_work_type": "remote",
  "min_salary": 120000,
  "max_salary": 150000,
  "salary_period": "year",
  "salary_currency": "USD"
}}

IMPORTANT INSTRUCTIONS FOR MISSING DATA:
- summary: Always provide a 2-sentence summary. If insufficient information, write a brief summary based on the job title and any available details. Never use null.
- skills: Return an empty array [] if no skills are mentioned. Never use null.
- location: Use null if location cannot be determined from the posting. Try to infer from context if possible.
- seniority_level: Infer from job description if not explicitly stated. Use null only if absolutely no indication (title, requirements, experience level) can be found.
- remote_work_type: Infer from job description if not explicitly stated. Use null only if absolutely no indication can be found.
- min_salary, max_salary: Use null if not mentioned in the job posting. Do not infer or guess salary amounts.
- salary_period: Use null if not mentioned. If salary amounts are provided but period is unclear, use null.
- salary_currency: Use null if not mentioned. If salary amounts are provided but currency is unclear, use null."""

        response_text = self._call_openai_api(prompt, system_prompt)

        if not response_text:
            job_key = job.get("jsearch_job_postings_key", "unknown")
            logger.warning(
                f"Failed to get ChatGPT response for job {job_key}. "
                f"Check previous error logs for API call details."
            )
            return self._get_empty_enrichment()

        # Parse JSON response using helper method
        try:
            response_data = self._parse_json_response(response_text)
            if not isinstance(response_data, dict):
                raise ValueError(f"Expected dict, got {type(response_data)}")

            job_key = job.get("jsearch_job_postings_key", "unknown")
            return self._extract_enrichment_from_result(response_data, job_key)

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse ChatGPT JSON response for job {job.get('jsearch_job_postings_key')}: {e}. Response: {response_text[:200]}"
            )
            return self._get_empty_enrichment()

    def update_job_enrichment(
        self,
        job_key: int,
        job_summary: str | None,
        chatgpt_extracted_skills: list[str] | None,
        chatgpt_extracted_location: str | None,
        chatgpt_seniority_level: str | None = None,
        chatgpt_remote_work_type: str | None = None,
        chatgpt_job_min_salary: float | None = None,
        chatgpt_job_max_salary: float | None = None,
        chatgpt_salary_period: str | None = None,
        chatgpt_salary_currency: str | None = None,
    ) -> None:
        """
        Upsert ChatGPT enrichment data into staging.chatgpt_enrichments table.

        Args:
            job_key: jsearch_job_postings_key (primary key)
            job_summary: 2-sentence job summary or None
            chatgpt_extracted_skills: List of extracted skills or None
            chatgpt_extracted_location: Normalized location string or None
            chatgpt_seniority_level: Seniority level (intern, junior, mid, senior, executive) or None
            chatgpt_remote_work_type: Remote work type (remote, hybrid, onsite) or None
            chatgpt_job_min_salary: Minimum salary (numeric) or None
            chatgpt_job_max_salary: Maximum salary (numeric) or None
            chatgpt_salary_period: Salary period (year, month, week, day, hour) or None
            chatgpt_salary_currency: Currency code (USD, CAD, EUR, GBP) or None
        """
        # Convert skills list to JSONB for storage
        skills_json = None
        if chatgpt_extracted_skills is not None:
            skills_json = json.dumps(chatgpt_extracted_skills)

        # Build enrichment status JSONB to track which fields were successfully extracted
        enrichment_status = {
            "summary": job_summary is not None,
            "skills": chatgpt_extracted_skills is not None and len(chatgpt_extracted_skills) > 0,
            "location": chatgpt_extracted_location is not None,
            "seniority": chatgpt_seniority_level is not None,
            "remote_type": chatgpt_remote_work_type is not None,
            "salary": chatgpt_job_min_salary is not None or chatgpt_job_max_salary is not None,
        }
        status_json = json.dumps(enrichment_status)

        with self.db.get_cursor() as cur:
            cur.execute(
                UPDATE_CHATGPT_ENRICHMENT,
                (
                    job_key,  # jsearch_job_postings_key
                    job_summary,  # job_summary
                    skills_json,  # chatgpt_extracted_skills (JSONB)
                    chatgpt_extracted_location,  # chatgpt_extracted_location
                    chatgpt_seniority_level,  # chatgpt_seniority_level
                    chatgpt_remote_work_type,  # chatgpt_remote_work_type
                    chatgpt_job_min_salary,  # chatgpt_job_min_salary
                    chatgpt_job_max_salary,  # chatgpt_job_max_salary
                    chatgpt_salary_period,  # chatgpt_salary_period
                    chatgpt_salary_currency,  # chatgpt_salary_currency
                    status_json,  # chatgpt_enrichment_status (JSONB)
                ),
            )
            logger.debug(
                f"Upserted ChatGPT enrichment for job_key={job_key}: "
                f"summary={'extracted' if job_summary else 'None'}, "
                f"skills={'extracted' if chatgpt_extracted_skills else 'None'}, "
                f"location={'extracted' if chatgpt_extracted_location else 'None'}, "
                f"seniority={'extracted' if chatgpt_seniority_level else 'None'}, "
                f"remote_type={'extracted' if chatgpt_remote_work_type else 'None'}, "
                f"salary={'extracted' if (chatgpt_job_min_salary or chatgpt_job_max_salary) else 'None'}"
            )

    def enrich_jobs_batch(self, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Enrich multiple jobs in a single API call (batch processing).

        Args:
            jobs: List of job dictionaries to enrich

        Returns:
            List of enrichment data dictionaries, one per job (in same order as input)
        """
        if not jobs:
            return []

        # Call OpenAI API with batch of jobs
        response_text = self._call_openai_api_batch(jobs)

        if not response_text:
            logger.warning(f"Failed to get ChatGPT batch response for {len(jobs)} job(s)")
            # Return empty enrichment data for all jobs
            return [self._get_empty_enrichment() for _ in jobs]

        # Parse JSON response using helper method
        try:
            response_data = self._parse_json_response(response_text)

            # Handle different response formats
            if isinstance(response_data, list):
                batch_results = response_data
            elif isinstance(response_data, dict):
                # If it's an object, try to find an array field
                if "jobs" in response_data and isinstance(response_data["jobs"], list):
                    batch_results = response_data["jobs"]
                elif "results" in response_data and isinstance(response_data["results"], list):
                    batch_results = response_data["results"]
                else:
                    logger.error(f"Unexpected batch response format: {response_data}")
                    batch_results = []
            else:
                logger.error(f"Unexpected batch response type: {type(response_data)}")
                batch_results = []

            # Validate we got the right number of results
            if len(batch_results) != len(jobs):
                logger.warning(
                    f"Batch response has {len(batch_results)} results but expected {len(jobs)} jobs. "
                    f"Some jobs may have missing enrichment data."
                )

            # Process each result using helper method
            enrichment_list = []
            for idx, result in enumerate(batch_results):
                if idx >= len(jobs):
                    break  # Extra results, ignore

                if not isinstance(result, dict):
                    logger.warning(f"Batch result {idx} is not a dict: {type(result)}")
                    enrichment_list.append(self._get_empty_enrichment())
                    continue

                job_key = jobs[idx].get("jsearch_job_postings_key", idx)
                enrichment_list.append(self._extract_enrichment_from_result(result, job_key))

            # If we got fewer results than jobs, pad with None values
            while len(enrichment_list) < len(jobs):
                enrichment_list.append(self._get_empty_enrichment())

            return enrichment_list

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse ChatGPT batch JSON response: {e}. Response: {response_text[:500]}"
            )
            # Return empty enrichment data for all jobs
            return [self._get_empty_enrichment() for _ in jobs]
        except Exception as e:
            logger.error(f"Unexpected error parsing batch response: {e}", exc_info=True)
            # Return empty enrichment data for all jobs
            return [self._get_empty_enrichment() for _ in jobs]

    async def enrich_jobs_batch_async(self, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Async version of enrich_jobs_batch.

        Args:
            jobs: List of job dictionaries to enrich

        Returns:
            List of enrichment data dictionaries, one per job (in same order as input)
        """
        if not jobs:
            return []

        # Call async batch API
        response_text = await self._call_openai_api_batch_async(jobs)

        if not response_text:
            logger.warning(f"Failed to get ChatGPT batch response for {len(jobs)} job(s)")
            return [
                {
                    "job_summary": None,
                    "chatgpt_extracted_skills": None,
                    "chatgpt_extracted_location": None,
                    "chatgpt_seniority_level": None,
                    "chatgpt_remote_work_type": None,
                    "chatgpt_job_min_salary": None,
                    "chatgpt_job_max_salary": None,
                    "chatgpt_salary_period": None,
                    "chatgpt_salary_currency": None,
                }
                for _ in jobs
            ]

        # Parse JSON response using helper method (same logic as sync version)
        try:
            response_data = self._parse_json_response(response_text)

            if isinstance(response_data, list):
                batch_results = response_data
            elif isinstance(response_data, dict):
                if "jobs" in response_data and isinstance(response_data["jobs"], list):
                    batch_results = response_data["jobs"]
                elif "results" in response_data and isinstance(response_data["results"], list):
                    batch_results = response_data["results"]
                else:
                    logger.error(f"Unexpected batch response format: {response_data}")
                    batch_results = []
            else:
                logger.error(f"Unexpected batch response type: {type(response_data)}")
                batch_results = []

            if len(batch_results) != len(jobs):
                logger.warning(
                    f"Batch response has {len(batch_results)} results but expected {len(jobs)} jobs."
                )

            enrichment_list = []
            for idx, result in enumerate(batch_results):
                if idx >= len(jobs):
                    break

                if not isinstance(result, dict):
                    logger.warning(f"Batch result {idx} is not a dict: {type(result)}")
                    enrichment_list.append(self._get_empty_enrichment())
                    continue

                job_key = jobs[idx].get("jsearch_job_postings_key", idx)
                enrichment_list.append(self._extract_enrichment_from_result(result, job_key))

            while len(enrichment_list) < len(jobs):
                enrichment_list.append(self._get_empty_enrichment())

            return enrichment_list

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse ChatGPT batch JSON response: {e}. Response: {response_text[:500]}"
            )
            return [
                {
                    "job_summary": None,
                    "chatgpt_extracted_skills": None,
                    "chatgpt_extracted_location": None,
                    "chatgpt_seniority_level": None,
                    "chatgpt_remote_work_type": None,
                    "chatgpt_job_min_salary": None,
                    "chatgpt_job_max_salary": None,
                    "chatgpt_salary_period": None,
                    "chatgpt_salary_currency": None,
                }
                for _ in jobs
            ]
        except Exception as e:
            logger.error(f"Unexpected error parsing batch response: {e}", exc_info=True)
            return [
                {
                    "job_summary": None,
                    "chatgpt_extracted_skills": None,
                    "chatgpt_extracted_location": None,
                    "chatgpt_seniority_level": None,
                    "chatgpt_remote_work_type": None,
                    "chatgpt_job_min_salary": None,
                    "chatgpt_job_max_salary": None,
                    "chatgpt_salary_period": None,
                    "chatgpt_salary_currency": None,
                }
                for _ in jobs
            ]

    async def _status_logger_task(
        self, batch_statuses: dict[int, BatchStatus], stop_event: asyncio.Event
    ) -> None:
        """
        Background task that logs batch status periodically.

        Args:
            batch_statuses: Dictionary mapping batch_id to BatchStatus
            stop_event: Event to signal when to stop logging
        """
        while not stop_event.is_set():
            try:
                await asyncio.sleep(self.status_check_interval)
                if stop_event.is_set():
                    break

                # Count statuses
                completed = sum(1 for s in batch_statuses.values() if s.status == "completed")
                processing = sum(1 for s in batch_statuses.values() if s.status == "processing")
                pending = sum(1 for s in batch_statuses.values() if s.status == "pending")
                failed = sum(1 for s in batch_statuses.values() if s.status == "failed")
                total = len(batch_statuses)

                # Log summary
                logger.info(
                    f"[Status Check] Batches: {completed}/{total} completed, "
                    f"{processing} processing, {pending} pending, {failed} failed"
                )

                # Log details for processing batches
                for batch_id, status in sorted(batch_statuses.items()):
                    if status.status == "processing":
                        elapsed = time.time() - status.start_time if status.start_time > 0 else 0
                        logger.info(
                            f"  Batch {batch_id}: {status.status} ({status.jobs_count} jobs, "
                            f"{elapsed:.1f}s elapsed)"
                        )
                    elif status.status == "completed":
                        elapsed = time.time() - status.start_time if status.start_time > 0 else 0
                        logger.info(
                            f"  Batch {batch_id}: {status.status} ({status.jobs_count} jobs, "
                            f"{elapsed:.1f}s)"
                        )
                    elif status.status == "failed":
                        logger.warning(
                            f"  Batch {batch_id}: {status.status} ({status.jobs_count} jobs) - "
                            f"{status.error}"
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in status logger task: {e}", exc_info=True)

    async def _process_batch_async(
        self,
        batch_id: int,
        batch_jobs: list[dict[str, Any]],
        batch_statuses: dict[int, BatchStatus],
        semaphore: asyncio.Semaphore,
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """
        Process a single batch asynchronously.

        Args:
            batch_id: Unique identifier for this batch
            batch_jobs: List of jobs in this batch
            batch_statuses: Dictionary to update with batch status
            semaphore: Semaphore to limit concurrent batches

        Returns:
            Tuple of (enrichment_results, batch_stats)
        """
        batch_stats = {"processed": 0, "enriched": 0, "errors": 0}
        enrichment_results = []

        async with semaphore:
            # Update status to processing
            batch_statuses[batch_id] = BatchStatus(
                batch_id=batch_id,
                status="processing",
                start_time=time.time(),
                jobs_count=len(batch_jobs),
            )

            try:
                # Enrich batch of jobs
                enrichment_results = await self.enrich_jobs_batch_async(batch_jobs)

                # Process each job's enrichment result
                for job, enrichment_data in zip(batch_jobs, enrichment_results):
                    try:
                        batch_stats["processed"] += 1
                        job_key = job["jsearch_job_postings_key"]

                        if (
                            enrichment_data["job_summary"]
                            or enrichment_data["chatgpt_extracted_skills"]
                            or enrichment_data["chatgpt_extracted_location"]
                            or enrichment_data["chatgpt_seniority_level"]
                            or enrichment_data["chatgpt_remote_work_type"]
                            or enrichment_data["chatgpt_job_min_salary"]
                            or enrichment_data["chatgpt_job_max_salary"]
                        ):
                            # Update database (synchronous operation, run in thread pool)
                            await _run_in_thread(
                                self.update_job_enrichment,
                                job_key,
                                enrichment_data["job_summary"],
                                enrichment_data["chatgpt_extracted_skills"],
                                enrichment_data["chatgpt_extracted_location"],
                                enrichment_data["chatgpt_seniority_level"],
                                enrichment_data["chatgpt_remote_work_type"],
                                enrichment_data["chatgpt_job_min_salary"],
                                enrichment_data["chatgpt_job_max_salary"],
                                enrichment_data["chatgpt_salary_period"],
                                enrichment_data["chatgpt_salary_currency"],
                            )
                            batch_stats["enriched"] += 1
                        else:
                            logger.debug(f"No enrichment data for job {job_key} - skipping update")

                    except Exception as e:
                        batch_stats["errors"] += 1
                        job_key = job.get("jsearch_job_postings_key", "unknown")
                        logger.error(
                            f"Error updating enrichment for job {job_key}: {e}", exc_info=True
                        )

                # Update status to completed
                batch_statuses[batch_id].status = "completed"

            except Exception as e:
                batch_stats["errors"] += len(batch_jobs)
                error_msg = str(e)
                batch_statuses[batch_id].status = "failed"
                batch_statuses[batch_id].error = error_msg
                logger.error(f"Error enriching batch {batch_id}: {e}", exc_info=True)
                # Return empty results on error
                if not enrichment_results:
                    enrichment_results = [
                        {
                            "job_summary": None,
                            "chatgpt_extracted_skills": None,
                            "chatgpt_extracted_location": None,
                            "chatgpt_seniority_level": None,
                            "chatgpt_remote_work_type": None,
                            "chatgpt_job_min_salary": None,
                            "chatgpt_job_max_salary": None,
                            "chatgpt_salary_period": None,
                            "chatgpt_salary_currency": None,
                        }
                        for _ in batch_jobs
                    ]

        return enrichment_results, batch_stats

    async def enrich_jobs_async(self, jobs: list[dict[str, Any]] | None = None) -> dict[str, int]:
        """
        Async version of enrich_jobs with concurrent batch processing and status monitoring.

        Args:
            jobs: Optional list of jobs to enrich. If None, fetches jobs from database.

        Returns:
            Dictionary with statistics: {"processed": int, "enriched": int, "errors": int}
        """
        if jobs is None:
            jobs = self.get_jobs_to_enrich()

        stats = {"processed": 0, "enriched": 0, "errors": 0}

        # Check if we have a valid API key before processing
        if not self.api_key or self.api_key.lower() in ("test", "none", ""):
            logger.error(
                "OpenAI API key is invalid. Cannot enrich jobs. "
                "Set a valid OPENAI_API_KEY environment variable."
            )
            return {"processed": 0, "enriched": 0, "errors": len(jobs) if jobs else 0}

        if not jobs:
            logger.info("No jobs to enrich")
            return stats

        # Split jobs into batches
        batch_size = self.batch_size
        total_batches = (len(jobs) + batch_size - 1) // batch_size

        logger.info(
            f"Processing {len(jobs)} job(s) in {total_batches} batch(es) of up to {batch_size} jobs each "
            f"(max {self.max_concurrent_batches} concurrent)"
        )

        # Create semaphore to limit concurrent batches
        semaphore = asyncio.Semaphore(self.max_concurrent_batches)

        # Track batch statuses
        batch_statuses: dict[int, BatchStatus] = {}
        for batch_idx in range(total_batches):
            batch_statuses[batch_idx + 1] = BatchStatus(
                batch_id=batch_idx + 1,
                status="pending",
                jobs_count=min(batch_size, len(jobs) - batch_idx * batch_size),
            )

        # Create stop event for status logger
        stop_event = asyncio.Event()

        # Start background status logger
        status_logger_task = asyncio.create_task(
            self._status_logger_task(batch_statuses, stop_event)
        )

        try:
            # Create tasks for all batches
            batch_tasks = []
            for batch_idx in range(total_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(jobs))
                batch_jobs = jobs[start_idx:end_idx]
                batch_id = batch_idx + 1

                task = self._process_batch_async(batch_id, batch_jobs, batch_statuses, semaphore)
                batch_tasks.append(task)

            # Wait for all batches to complete
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Collect statistics
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Batch task raised exception: {result}", exc_info=True)
                    stats["errors"] += batch_size  # Approximate
                else:
                    _, batch_stats = result
                    stats["processed"] += batch_stats["processed"]
                    stats["enriched"] += batch_stats["enriched"]
                    stats["errors"] += batch_stats["errors"]

        finally:
            # Stop status logger
            stop_event.set()
            status_logger_task.cancel()
            try:
                await status_logger_task
            except asyncio.CancelledError:
                pass

        logger.info(
            f"ChatGPT enrichment batch complete: processed={stats['processed']}, "
            f"enriched={stats['enriched']}, errors={stats['errors']}"
        )
        return stats

    def enrich_jobs(self, jobs: list[dict[str, Any]] | None = None) -> dict[str, int]:
        """
        Enrich a batch of jobs using ChatGPT with concurrent batch processing.

        Synchronous wrapper that calls the async implementation.

        Args:
            jobs: Optional list of jobs to enrich. If None, fetches jobs from database.

        Returns:
            Dictionary with statistics: {"processed": int, "enriched": int, "errors": int}
        """
        # Check if we're already in an async context
        try:
            asyncio.get_running_loop()
            # We're in an async context, can't use asyncio.run()
            # This shouldn't happen in normal usage, but handle it gracefully
            logger.warning(
                "enrich_jobs called from async context. Use enrich_jobs_async instead. "
                "Creating new event loop in thread."
            )
            # Run in a new thread with its own event loop
            import concurrent.futures

            def run_in_thread():
                # Create new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(self.enrich_jobs_async(jobs))
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            return asyncio.run(self.enrich_jobs_async(jobs))

    def enrich_all_pending_jobs(self, campaign_id: int | None = None) -> dict[str, int]:
        """
        Enrich all pending jobs in batches with concurrent processing.

        Fetches multiple batches of jobs at once and processes them concurrently
        to maximize throughput. Each fetch gets enough jobs to fill multiple batches
        (batch_size * max_concurrent_batches), which are then split and processed
        concurrently by enrich_jobs_async.

        Args:
            campaign_id: Optional campaign_id to filter jobs. If None, processes all campaigns.

        Returns:
            Dictionary with total statistics: {"processed": int, "enriched": int, "errors": int}
        """
        # Check if API key is valid before processing
        if not self.api_key or self.api_key.lower() in ("test", "none", ""):
            logger.error(
                "OpenAI API key is invalid. Cannot enrich jobs. "
                "Set a valid OPENAI_API_KEY environment variable."
            )
            return {"processed": 0, "enriched": 0, "errors": 0}

        total_stats = {"processed": 0, "enriched": 0, "errors": 0}
        consecutive_auth_errors = 0
        max_auth_errors = 3  # Stop after 3 consecutive authentication errors

        # Fetch enough jobs to fill multiple batches for concurrent processing
        # This allows enrich_jobs_async to split them into batches and process concurrently
        fetch_limit = self.batch_size * self.max_concurrent_batches

        while True:
            # Get multiple batches worth of jobs at once
            jobs = self.get_jobs_to_enrich(limit=fetch_limit, campaign_id=campaign_id)

            if not jobs:
                break

            # Process all jobs concurrently (enrich_jobs_async will split into batches)
            batch_stats = self.enrich_jobs(jobs)
            total_stats["processed"] += batch_stats["processed"]
            total_stats["enriched"] += batch_stats["enriched"]
            total_stats["errors"] += batch_stats["errors"]

            # Check if we got authentication errors - if so, stop processing
            if batch_stats["errors"] > 0 and batch_stats["enriched"] == 0:
                consecutive_auth_errors += 1
                if consecutive_auth_errors >= max_auth_errors:
                    logger.error(
                        f"Stopping enrichment after {consecutive_auth_errors} consecutive batches "
                        "with authentication errors. Check OPENAI_API_KEY."
                    )
                    break
            else:
                consecutive_auth_errors = 0  # Reset counter on success

        logger.info(
            f"All jobs enriched with ChatGPT: processed={total_stats['processed']}, "
            f"enriched={total_stats['enriched']}, errors={total_stats['errors']}"
        )

        return total_stats
