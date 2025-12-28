"""Unit tests for JobStatusService."""

from unittest.mock import Mock

import pytest

from services.jobs.job_status_service import JobStatusService


@pytest.fixture
def mock_database():
    """Create a mock database."""
    db = Mock()
    db.get_cursor.return_value.__enter__ = Mock(return_value=Mock())
    db.get_cursor.return_value.__exit__ = Mock(return_value=False)
    return db


@pytest.fixture
def job_status_service(mock_database):
    """Create a JobStatusService instance with mocked database."""
    return JobStatusService(database=mock_database)


class TestJobStatusService:
    """Test cases for JobStatusService."""

    def test_init_requires_database(self):
        """Test that JobStatusService requires a database."""
        with pytest.raises(ValueError, match="Database is required"):
            JobStatusService(database=None)

    def test_get_status_not_found(self, job_status_service, mock_database):
        """Test get_status returns None when status not found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("user_job_status_id",), ("status",)]
        mock_cursor.fetchone.return_value = None

        result = job_status_service.get_status("job123", 1)

        assert result is None

    def test_get_status_found(self, job_status_service, mock_database):
        """Test get_status returns status when found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("user_job_status_id",),
            ("user_id",),
            ("jsearch_job_id",),
            ("status",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (1, 1, "job123", "applied", None, None)

        result = job_status_service.get_status("job123", 1)

        assert result is not None
        assert result["status"] == "applied"
        assert result["jsearch_job_id"] == "job123"
        assert result["user_id"] == 1

    def test_upsert_status_valid_status(self, job_status_service, mock_database):
        """Test upsert_status with valid status."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)

        status_id = job_status_service.upsert_status("job123", 1, "applied")

        assert status_id == 1
        mock_cursor.execute.assert_called_once()

    def test_upsert_status_invalid_status(self, job_status_service):
        """Test upsert_status raises ValueError for invalid status."""
        with pytest.raises(ValueError, match="Invalid status"):
            job_status_service.upsert_status("job123", 1, "invalid_status")

    def test_upsert_status_all_valid_statuses(self, job_status_service, mock_database):
        """Test upsert_status accepts all valid status values."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)

        valid_statuses = ["waiting", "applied", "rejected", "interview", "offer", "archived"]

        for status in valid_statuses:
            job_status_service.upsert_status("job123", 1, status)
            # Should not raise exception

    def test_upsert_status_handles_exceptions(self, job_status_service, mock_database):
        """Test upsert_status handles database exceptions."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            job_status_service.upsert_status("job123", 1, "applied")
