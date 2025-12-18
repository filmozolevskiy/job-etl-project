"""
Glassdoor API Client

Client for interacting with the Glassdoor company search API.
"""

import logging
from typing import Any

import requests

from .base_client import BaseAPIClient

logger = logging.getLogger(__name__)


class GlassdoorClient(BaseAPIClient):
    """
    Client for Glassdoor company search API.

    Handles authentication, rate limiting, and API calls for company data.
    """

    def __init__(
        self,
        api_key: str,
        rate_limit_delay: float = 1.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 2.0,
    ):
        """
        Initialize Glassdoor API client.

        Args:
            api_key: Glassdoor API key
            rate_limit_delay: Minimum delay between requests (seconds)
            max_retries: Maximum number of retry attempts
            retry_backoff_factor: Multiplier for exponential backoff
        """
        super().__init__(
            api_key=api_key,
            base_url="https://api.openwebninja.com/realtime-glassdoor-data",
            rate_limit_delay=rate_limit_delay,
            max_retries=max_retries,
            retry_backoff_factor=retry_backoff_factor,
        )

    def _make_request(
        self, endpoint: str, params: dict[str, Any] | None = None, method: str = "GET"
    ) -> dict[str, Any]:
        """
        Make a request to the Glassdoor API.

        Args:
            endpoint: API endpoint (e.g., "/company-search")
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
            logger.error(f"Glassdoor API request failed: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text[:500]}")
            raise

    def search_company(
        self, query: str, limit: int = 10, domain: str = "www.glassdoor.com"
    ) -> dict[str, Any]:
        """
        Search for company information using Glassdoor API.

        Args:
            query: Company name or domain to search for
            limit: Maximum number of results to return (default: 10)
            domain: Glassdoor domain (default: "www.glassdoor.com")

        Returns:
            API response with company data
        """
        params = {"query": query, "limit": str(limit), "domain": domain}

        return self._make_request("/company-search", params=params)
