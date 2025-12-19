"""
JSearch API Client

Client for interacting with the JSearch API to fetch job postings.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from .base_client import BaseAPIClient

logger = logging.getLogger(__name__)


class JSearchClient(BaseAPIClient):
    """
    Client for JSearch API.

    Handles authentication, rate limiting, and API calls for job search.
    """

    def __init__(
        self,
        api_key: str,
        rate_limit_delay: float = 1.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 2.0,
    ):
        """
        Initialize JSearch API client.

        Args:
            api_key: JSearch API key
            rate_limit_delay: Minimum delay between requests (seconds)
            max_retries: Maximum number of retry attempts
            retry_backoff_factor: Multiplier for exponential backoff
        """
        super().__init__(
            api_key=api_key,
            base_url="https://api.openwebninja.com/jsearch",
            rate_limit_delay=rate_limit_delay,
            max_retries=max_retries,
            retry_backoff_factor=retry_backoff_factor,
        )

    def _make_request(
        self, endpoint: str, params: dict[str, Any] | None = None, method: str = "GET"
    ) -> dict[str, Any]:
        """
        Make a request to the JSearch API.

        Args:
            endpoint: API endpoint (e.g., "/search")
            params: Query parameters
            method: HTTP method (default: GET)

        Returns:
            Parsed JSON response

        Raises:
            requests.RequestException: If the request fails
        """
        self._enforce_rate_limit()

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        try:
            if method.upper() == "GET":
                response = self.session.get(
                    url, headers=headers, params=params, timeout=self.timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            self._log_request(endpoint, params, response.status_code)
            return self._handle_response(response)

        except requests.RequestException as e:
            logger.error(f"JSearch API request failed: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text[:500]}")
            raise

    def search_jobs(
        self,
        query: str,
        location: str | None = None,
        country: str | None = None,
        date_posted: str | None = None,
        page: int = 1,
        num_pages: int = 1,
        employment_types: str | None = None,
        work_from_home: bool | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Search for jobs using JSearch API.

        Args:
            query: Job search query (e.g., "developer jobs in chicago")
            location: Job location
            country: Country code (e.g., "ca", "us")
            date_posted: Date window (e.g., "today", "week", "month")
            page: Page number (default: 1)
            num_pages: Number of pages to fetch (default: 1)
            employment_types: Employment type filter (e.g., "FULLTIME")
            work_from_home: Filter for remote jobs
            **kwargs: Additional query parameters

        Returns:
            API response with job postings data
        """
        params = {
            "query": query,
            "page": str(page),
            "num_pages": str(num_pages),
        }

        if location:
            params["location"] = location
        if country:
            params["country"] = country.lower()
        if date_posted:
            params["date_posted"] = date_posted
        if employment_types:
            params["employment_types"] = employment_types
        if work_from_home is not None:
            params["work_from_home"] = "true" if work_from_home else "false"

        # Add any additional parameters
        params.update(kwargs)

        return self._make_request("/search", params=params)
