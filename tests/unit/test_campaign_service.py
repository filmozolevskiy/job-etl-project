"""Unit tests for CampaignService status derivation from metrics."""

from unittest.mock import Mock

import pytest

from services.campaign_management.campaign_service import CampaignService


@pytest.fixture
def mock_database():
    """Create a mock database."""
    db = Mock()
    db.get_cursor.return_value.__enter__ = Mock(return_value=Mock())
    db.get_cursor.return_value.__exit__ = Mock(return_value=False)
    return db


@pytest.fixture
def campaign_service(mock_database):
    """Create a CampaignService instance with mocked database."""
    return CampaignService(database=mock_database)


class TestCampaignServiceStatusFromMetrics:
    """Test cases for get_campaign_status_from_metrics method."""

    def test_get_status_all_tasks_success(self, campaign_service, mock_database):
        """Test status when all 4 critical tasks completed successfully."""
        campaign_id = 1
        dag_run_id = "test_dag_run_123"

        # Mock cursor and fetchall
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("extract_job_postings", "success"),
            ("normalize_jobs", "success"),
            ("rank_jobs", "success"),
            ("send_notifications", "success"),
        ]

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        assert result["status"] == "success"
        assert result["is_complete"] is True
        assert len(result["completed_tasks"]) == 4
        assert len(result["failed_tasks"]) == 0
        assert "extract_job_postings" in result["completed_tasks"]
        assert "normalize_jobs" in result["completed_tasks"]
        assert "rank_jobs" in result["completed_tasks"]
        assert "send_notifications" in result["completed_tasks"]
        assert result["dag_run_id"] == dag_run_id

    def test_get_status_task_failed(self, campaign_service, mock_database):
        """Test status when one or more tasks failed."""
        campaign_id = 1
        dag_run_id = "test_dag_run_123"

        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("extract_job_postings", "success"),
            ("normalize_jobs", "failed"),
            ("rank_jobs", "success"),
            ("send_notifications", "success"),
        ]

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        assert result["status"] == "error"
        assert result["is_complete"] is True
        assert len(result["failed_tasks"]) == 1
        assert "normalize_jobs" in result["failed_tasks"]
        assert len(result["completed_tasks"]) == 3

    def test_get_status_multiple_tasks_failed(self, campaign_service, mock_database):
        """Test status when multiple tasks failed."""
        campaign_id = 1
        dag_run_id = "test_dag_run_123"

        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("extract_job_postings", "failed"),
            ("normalize_jobs", "failed"),
            ("rank_jobs", "success"),
            ("send_notifications", "success"),
        ]

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        assert result["status"] == "error"
        assert result["is_complete"] is True
        assert len(result["failed_tasks"]) == 2
        assert "extract_job_postings" in result["failed_tasks"]
        assert "normalize_jobs" in result["failed_tasks"]

    def test_get_status_partial_completion(self, campaign_service, mock_database):
        """Test status when some tasks complete, others not yet run."""
        campaign_id = 1
        dag_run_id = "test_dag_run_123"

        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("extract_job_postings", "success"),
            ("normalize_jobs", "success"),
        ]

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        assert result["status"] == "running"
        assert result["is_complete"] is False
        assert len(result["completed_tasks"]) == 2
        assert len(result["failed_tasks"]) == 0
        assert "extract_job_postings" in result["completed_tasks"]
        assert "normalize_jobs" in result["completed_tasks"]

    def test_get_status_no_metrics(self, campaign_service, mock_database):
        """Test status when no metrics found for campaign."""
        campaign_id = 1
        dag_run_id = "test_dag_run_123"

        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        assert result["status"] == "pending"
        assert result["is_complete"] is False
        assert len(result["completed_tasks"]) == 0
        assert len(result["failed_tasks"]) == 0
        assert result["dag_run_id"] == dag_run_id

    def test_get_status_specific_dag_run(self, campaign_service, mock_database):
        """Test querying specific dag_run_id instead of most recent."""
        campaign_id = 1
        dag_run_id = "specific_run_456"

        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("extract_job_postings", "success"),
            ("normalize_jobs", "success"),
            ("rank_jobs", "success"),
            ("send_notifications", "success"),
        ]

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        # Verify the correct dag_run_id was used in the query
        # Check that execute was called with the dag_run_id parameter
        call_args = mock_cursor.execute.call_args
        assert call_args is not None
        assert dag_run_id in call_args[0][1]  # dag_run_id should be in params

        assert result["status"] == "success"
        assert result["dag_run_id"] == dag_run_id

    def test_get_status_database_error(self, campaign_service, mock_database):
        """Test handling of database errors."""
        campaign_id = 1

        # Make get_cursor raise an exception
        mock_database.get_cursor.side_effect = Exception("Database connection error")

        result = campaign_service.get_campaign_status_from_metrics(campaign_id=campaign_id)

        # Should return error status on exception
        assert result["status"] == "error"
        assert result["is_complete"] is False
        assert len(result["completed_tasks"]) == 0
        assert len(result["failed_tasks"]) == 0

    def test_get_status_missing_critical_tasks_some_complete(self, campaign_service, mock_database):
        """Test status when some critical tasks are missing but some are complete."""
        campaign_id = 1
        dag_run_id = "test_dag_run_123"

        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        # Only 2 of 4 tasks have run
        mock_cursor.fetchall.return_value = [
            ("extract_job_postings", "success"),
            ("normalize_jobs", "success"),
        ]

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        assert result["status"] == "running"
        assert result["is_complete"] is False
        assert len(result["completed_tasks"]) == 2

    def test_get_status_missing_critical_tasks_none_complete(self, campaign_service, mock_database):
        """Test status when no critical tasks have completed yet."""
        campaign_id = 1
        dag_run_id = "test_dag_run_123"

        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        # Empty result - no tasks have run
        mock_cursor.fetchall.return_value = []

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        assert result["status"] == "pending"
        assert result["is_complete"] is False
        assert len(result["completed_tasks"]) == 0

    def test_get_status_is_complete_flag_success(self, campaign_service, mock_database):
        """Test is_complete flag is True for success status."""
        campaign_id = 1
        dag_run_id = "test_dag_run_123"

        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("extract_job_postings", "success"),
            ("normalize_jobs", "success"),
            ("rank_jobs", "success"),
            ("send_notifications", "success"),
        ]

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        assert result["status"] == "success"
        assert result["is_complete"] is True

    def test_get_status_is_complete_flag_error(self, campaign_service, mock_database):
        """Test is_complete flag is True for error status."""
        campaign_id = 1
        dag_run_id = "test_dag_run_123"

        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("extract_job_postings", "failed"),
        ]

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        assert result["status"] == "error"
        assert result["is_complete"] is True

    def test_get_status_is_complete_flag_running(self, campaign_service, mock_database):
        """Test is_complete flag is False for running status."""
        campaign_id = 1
        dag_run_id = "test_dag_run_123"

        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("extract_job_postings", "success"),
            ("normalize_jobs", "success"),
        ]

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        assert result["status"] == "running"
        assert result["is_complete"] is False

    def test_get_status_is_complete_flag_pending(self, campaign_service, mock_database):
        """Test is_complete flag is False for pending status."""
        campaign_id = 1
        dag_run_id = "test_dag_run_123"

        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = campaign_service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        assert result["status"] == "pending"
        assert result["is_complete"] is False

    def test_get_status_most_recent_dag_run(self, campaign_service, mock_database):
        """Test querying most recent DAG run when dag_run_id is None."""
        campaign_id = 1

        # Need to mock two cursor contexts: one for main query, one for dag_run_id lookup
        mock_cursor1 = Mock()
        mock_cursor2 = Mock()

        # First context manager returns cursor1, second returns cursor2
        context_manager = Mock()
        context_manager.__enter__ = Mock(side_effect=[mock_cursor1, mock_cursor2])
        context_manager.__exit__ = Mock(return_value=False)
        mock_database.get_cursor.return_value = context_manager

        # Mock the task statuses from main query
        mock_cursor1.fetchall.return_value = [
            ("extract_job_postings", "success"),
            ("normalize_jobs", "success"),
            ("rank_jobs", "success"),
            ("send_notifications", "success"),
        ]

        # Mock the dag_run_id lookup
        mock_cursor2.fetchone.return_value = ("latest_dag_run_789",)

        result = campaign_service.get_campaign_status_from_metrics(campaign_id=campaign_id)

        assert result["status"] == "success"
        assert result["is_complete"] is True
        assert result["dag_run_id"] == "latest_dag_run_789"

