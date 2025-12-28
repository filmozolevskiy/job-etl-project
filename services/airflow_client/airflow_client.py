"""Airflow REST API client for triggering DAGs."""

import logging
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class AirflowClient:
    """Client for interacting with Airflow REST API."""

    def __init__(self, api_url: str, username: str, password: str):
        """Initialize the Airflow client.

        Args:
            api_url: Base URL for Airflow REST API (e.g., "http://localhost:8080/api/v1")
            username: Airflow API username
            password: Airflow API password
        """
        self.api_url = api_url.rstrip("/")
        self.username = username
        self.password = password
        self.auth = HTTPBasicAuth(username, password)

    def trigger_dag(
        self, dag_id: str, conf: dict[str, Any] | None = None, run_id: str | None = None
    ) -> dict[str, Any]:
        """Trigger a DAG run.

        Args:
            dag_id: DAG ID to trigger
            conf: Optional configuration dictionary to pass to the DAG
            run_id: Optional run ID (if not provided, Airflow generates one)

        Returns:
            Response dictionary from Airflow API

        Raises:
            requests.exceptions.RequestException: If the API request fails
        """
        url = f"{self.api_url}/dags/{dag_id}/dagRuns"
        payload: dict[str, Any] = {}
        if conf:
            payload["conf"] = conf
        if run_id:
            payload["dag_run_id"] = run_id

        try:
            response = requests.post(url, json=payload, auth=self.auth, timeout=30)

            # Handle specific HTTP error codes
            if response.status_code == 401:
                logger.error("Authentication failed for Airflow API. Check credentials.")
                raise requests.exceptions.HTTPError(
                    "401 Unauthorized: Invalid Airflow API credentials", response=response
                )
            elif response.status_code == 403:
                logger.error(f"Access forbidden for DAG {dag_id}. Check user permissions.")
                raise requests.exceptions.HTTPError(
                    f"403 Forbidden: User does not have permission to trigger DAG {dag_id}",
                    response=response,
                )
            elif response.status_code == 404:
                logger.error(f"DAG {dag_id} not found in Airflow.")
                raise requests.exceptions.HTTPError(
                    f"404 Not Found: DAG {dag_id} does not exist", response=response
                )

            response.raise_for_status()
            result = response.json()
            logger.info(f"Triggered DAG {dag_id}: run_id={result.get('dag_run_id')}")
            return result
        except requests.exceptions.Timeout:
            logger.error(
                f"Timeout while triggering DAG {dag_id}: Request took longer than 30 seconds"
            )
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error while triggering DAG {dag_id}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error triggering DAG {dag_id}: {e}", exc_info=True)
            raise

    def get_dag_run_status(self, dag_id: str, run_id: str) -> dict[str, Any] | None:
        """Get the status of a DAG run.

        Args:
            dag_id: DAG ID
            run_id: Run ID

        Returns:
            DAG run dictionary with status information, or None if not found

        Raises:
            requests.exceptions.RequestException: If the API request fails
        """
        url = f"{self.api_url}/dags/{dag_id}/dagRuns/{run_id}"

        try:
            response = requests.get(url, auth=self.auth, timeout=30)

            if response.status_code == 404:
                logger.debug(f"DAG run {dag_id}/{run_id} not found")
                return None
            elif response.status_code == 401:
                logger.error("Authentication failed for Airflow API. Check credentials.")
                raise requests.exceptions.HTTPError(
                    "401 Unauthorized: Invalid Airflow API credentials", response=response
                )
            elif response.status_code == 403:
                logger.error(f"Access forbidden for DAG {dag_id}. Check user permissions.")
                raise requests.exceptions.HTTPError(
                    f"403 Forbidden: User does not have permission to access DAG {dag_id}",
                    response=response,
                )

            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(
                f"Timeout while getting DAG run status for {dag_id}/{run_id}: Request took longer than 30 seconds"
            )
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(
                f"Connection error while getting DAG run status for {dag_id}/{run_id}: {e}"
            )
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting DAG run status for {dag_id}/{run_id}: {e}", exc_info=True)
            raise
