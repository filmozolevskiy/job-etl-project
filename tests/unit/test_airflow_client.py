"""Unit tests for AirflowClient."""

from unittest.mock import Mock, patch

import pytest
from requests.exceptions import ConnectionError, HTTPError, Timeout

from services.airflow_client.airflow_client import AirflowClient


@pytest.fixture
def airflow_client():
    """Create an AirflowClient instance."""
    return AirflowClient(
        api_url="http://localhost:8080/api/v1", username="testuser", password="testpass"
    )


class TestAirflowClient:
    """Test cases for AirflowClient."""

    def test_init_strips_trailing_slash(self):
        """Test that init strips trailing slash from API URL."""
        client = AirflowClient(
            api_url="http://localhost:8080/api/v1/", username="test", password="test"
        )
        assert not client.api_url.endswith("/")

    def test_init_sets_auth(self, airflow_client):
        """Test that init sets authentication."""
        assert airflow_client.username == "testuser"
        assert airflow_client.password == "testpass"
        assert airflow_client.auth is not None

    @patch("services.airflow_client.airflow_client.requests.post")
    def test_trigger_dag_success(self, mock_post, airflow_client):
        """Test successful DAG triggering."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"dag_run_id": "test_run_123"}
        mock_post.return_value = mock_response

        result = airflow_client.trigger_dag("test_dag", conf={"key": "value"})

        assert result["dag_run_id"] == "test_run_123"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "test_dag" in call_args[0][0]  # URL contains dag_id

    @patch("services.airflow_client.airflow_client.requests.post")
    def test_trigger_dag_without_conf(self, mock_post, airflow_client):
        """Test DAG triggering without conf."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"dag_run_id": "test_run_123"}
        mock_post.return_value = mock_response

        result = airflow_client.trigger_dag("test_dag")

        assert result["dag_run_id"] == "test_run_123"

    @patch("services.airflow_client.airflow_client.requests.post")
    def test_trigger_dag_401_unauthorized(self, mock_post, airflow_client):
        """Test DAG triggering with 401 Unauthorized."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        with pytest.raises(HTTPError, match="401 Unauthorized"):
            airflow_client.trigger_dag("test_dag")

    @patch("services.airflow_client.airflow_client.requests.post")
    def test_trigger_dag_403_forbidden(self, mock_post, airflow_client):
        """Test DAG triggering with 403 Forbidden."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response

        with pytest.raises(HTTPError, match="403 Forbidden"):
            airflow_client.trigger_dag("test_dag")

    @patch("services.airflow_client.airflow_client.requests.post")
    def test_trigger_dag_404_not_found(self, mock_post, airflow_client):
        """Test DAG triggering with 404 Not Found."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_post.return_value = mock_response

        with pytest.raises(HTTPError, match="404 Not Found"):
            airflow_client.trigger_dag("nonexistent_dag")

    @patch("services.airflow_client.airflow_client.requests.post")
    def test_trigger_dag_timeout(self, mock_post, airflow_client):
        """Test DAG triggering with timeout."""
        mock_post.side_effect = Timeout("Request timeout")

        with pytest.raises(Timeout, match="Request timeout"):
            airflow_client.trigger_dag("test_dag")

    @patch("services.airflow_client.airflow_client.requests.post")
    def test_trigger_dag_connection_error(self, mock_post, airflow_client):
        """Test DAG triggering with connection error."""
        mock_post.side_effect = ConnectionError("Connection failed")

        with pytest.raises(ConnectionError, match="Connection failed"):
            airflow_client.trigger_dag("test_dag")

    @patch("services.airflow_client.airflow_client.requests.get")
    def test_get_dag_run_status_success(self, mock_get, airflow_client):
        """Test successful DAG run status retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"state": "success", "dag_run_id": "test_run_123"}
        mock_get.return_value = mock_response

        result = airflow_client.get_dag_run_status("test_dag", "test_run_123")

        assert result["state"] == "success"
        assert result["dag_run_id"] == "test_run_123"

    @patch("services.airflow_client.airflow_client.requests.get")
    def test_get_dag_run_status_404_not_found(self, mock_get, airflow_client):
        """Test DAG run status retrieval with 404 Not Found."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = airflow_client.get_dag_run_status("test_dag", "nonexistent_run")

        assert result is None

    @patch("services.airflow_client.airflow_client.requests.get")
    def test_get_dag_run_status_401_unauthorized(self, mock_get, airflow_client):
        """Test DAG run status retrieval with 401 Unauthorized."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        with pytest.raises(HTTPError, match="401 Unauthorized"):
            airflow_client.get_dag_run_status("test_dag", "test_run_123")

    @patch("services.airflow_client.airflow_client.requests.get")
    def test_get_dag_run_status_timeout(self, mock_get, airflow_client):
        """Test DAG run status retrieval with timeout."""
        mock_get.side_effect = Timeout("Request timeout")

        with pytest.raises(Timeout):
            airflow_client.get_dag_run_status("test_dag", "test_run_123")
