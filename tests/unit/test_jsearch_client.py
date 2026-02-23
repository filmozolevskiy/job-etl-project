"""Unit tests for JSearchClient (search_jobs and get_job_details)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from services.extractor.jsearch_client import JSearchClient


@pytest.fixture
def client():
    """JSearchClient with test API key."""
    return JSearchClient(api_key="test-key", rate_limit_delay=0)


class TestJSearchClientGetJobDetails:
    """Tests for get_job_details."""

    def test_get_job_details_success_with_data(self, client):
        """When job-details returns data array with one job, response is returned as-is."""
        with patch.object(client, "_make_request") as m:
            m.return_value = {
                "status": "OK",
                "request_id": "req-1",
                "data": [{"job_id": "job123", "job_title": "Engineer"}],
            }
            out = client.get_job_details("job123")
        assert out["data"] == [{"job_id": "job123", "job_title": "Engineer"}]
        m.assert_called_once_with("/job-details", params={"job_id": "job123"})

    def test_get_job_details_success_empty_data(self, client):
        """When job-details returns empty data, response indicates not available."""
        with patch.object(client, "_make_request") as m:
            m.return_value = {"status": "OK", "request_id": "req-2", "data": []}
            out = client.get_job_details("removed-job")
        assert out["data"] == []
        m.assert_called_once_with("/job-details", params={"job_id": "removed-job"})

    def test_get_job_details_with_country_and_language(self, client):
        """Optional country and language are passed as params."""
        with patch.object(client, "_make_request") as m:
            m.return_value = {"status": "OK", "data": []}
            client.get_job_details("job1", country="ca", language="en")
        m.assert_called_once_with(
            "/job-details",
            params={"job_id": "job1", "country": "ca", "language": "en"},
        )

    def test_get_job_details_request_exception_raises(self, client):
        """RequestException from _make_request propagates."""
        with patch.object(client, "_make_request") as m:
            m.side_effect = requests.RequestException("timeout")
            with pytest.raises(requests.RequestException, match="timeout"):
                client.get_job_details("job1")
