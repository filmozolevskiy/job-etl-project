"""
Base API Client

Abstract base class for API clients with common functionality:
- Rate limiting
- Retry logic with exponential backoff
- Error handling
- Logging
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class BaseAPIClient(ABC):
    """
    Abstract base class for API clients.
    
    Provides common functionality for rate limiting, retries, and error handling.
    Subclasses should implement the _make_request method for API-specific logic.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        rate_limit_delay: float = 1.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 2.0,
        timeout: int = 30
    ):
        """
        Initialize the API client.
        
        Args:
            api_key: API key for authentication
            base_url: Base URL for the API
            rate_limit_delay: Minimum delay between requests (seconds)
            max_retries: Maximum number of retry attempts
            retry_backoff_factor: Multiplier for exponential backoff
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self.timeout = timeout
        self.last_request_time = 0.0
        
        # Configure session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting by waiting if necessary."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get default headers for API requests.
        
        Subclasses can override this to add API-specific headers.
        """
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    @abstractmethod
    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> Dict[str, Any]:
        """
        Make an API request.
        
        Args:
            endpoint: API endpoint (relative to base_url)
            params: Query parameters
            method: HTTP method (GET, POST, etc.)
            
        Returns:
            Parsed JSON response
            
        Raises:
            requests.RequestException: If the request fails after retries
        """
        pass
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Handle API response and extract JSON data.
        
        Args:
            response: HTTP response object
            
        Returns:
            Parsed JSON response data
            
        Raises:
            requests.RequestException: If response indicates an error
        """
        response.raise_for_status()
        
        try:
            data = response.json()
            return data
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response.text[:500]}")
            raise requests.RequestException(f"Invalid JSON response: {e}")
    
    def _log_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None
    ):
        """Log API request details."""
        if params:
            # Don't log sensitive data
            safe_params = {k: v for k, v in params.items() if k not in ['api_key', 'token']}
            logger.info(f"API request: {endpoint} with params: {safe_params}")
        else:
            logger.info(f"API request: {endpoint}")
        
        if status_code:
            logger.debug(f"Response status: {status_code}")
