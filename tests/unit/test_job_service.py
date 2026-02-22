"""Unit tests for JobService."""

from unittest.mock import Mock

import pytest

from services.jobs.job_service import JobService


@pytest.fixture
def mock_database():
    """Create a mock database."""
    db = Mock()
    db.get_cursor.return_value.__enter__ = Mock(return_value=Mock())
    db.get_cursor.return_value.__exit__ = Mock(return_value=False)
    return db


@pytest.fixture
def job_service(mock_database):
    """Create a JobService instance with mocked database."""
    return JobService(database=mock_database)


class TestJobService:
    """Test cases for JobService."""

    def test_init_requires_database(self):
        """Test that JobService requires a database."""
        with pytest.raises(ValueError, match="Database is required"):
            JobService(database=None)

    def test_get_jobs_for_campaign_filters_rejected_by_default(self, job_service, mock_database):
        """Test that get_jobs_for_campaign filters rejected jobs by default."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("jsearch_job_id",), ("job_status",)]
        mock_cursor.fetchall.return_value = []

        job_service.get_jobs_for_campaign(campaign_id=1, user_id=1)

        # Verify the query was executed
        assert mock_cursor.execute.called
        # Check that the query includes the rejected filter
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        assert "COALESCE(ujs.status, 'waiting') != 'rejected'" in query

    def test_get_jobs_for_campaign_includes_rejected_when_requested(
        self, job_service, mock_database
    ):
        """Test that get_jobs_for_campaign includes rejected jobs when include_rejected=True."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("jsearch_job_id",), ("job_status",)]
        mock_cursor.fetchall.return_value = []

        job_service.get_jobs_for_campaign(campaign_id=1, user_id=1, include_rejected=True)

        # Verify the query was executed
        assert mock_cursor.execute.called
        # Check that the query does NOT include the rejected filter
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        assert "COALESCE(ujs.status, 'waiting') != 'rejected'" not in query

    def test_get_jobs_for_user_filters_rejected_by_default(self, job_service, mock_database):
        """Test that get_jobs_for_user filters rejected jobs by default."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("jsearch_job_id",), ("job_status",)]
        mock_cursor.fetchall.return_value = []

        job_service.get_jobs_for_user(user_id=1)

        # Verify the query was executed
        assert mock_cursor.execute.called
        # Check that the query includes the rejected filter
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        assert "COALESCE(ujs.status, 'waiting') != 'rejected'" in query

    def test_get_jobs_for_user_includes_rejected_when_requested(self, job_service, mock_database):
        """Test that get_jobs_for_user includes rejected jobs when include_rejected=True."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("jsearch_job_id",), ("job_status",)]
        mock_cursor.fetchall.return_value = []

        job_service.get_jobs_for_user(user_id=1, include_rejected=True)

        # Verify the query was executed
        assert mock_cursor.execute.called
        # Check that the query does NOT include the rejected filter
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        assert "COALESCE(ujs.status, 'waiting') != 'rejected'" not in query

    def test_get_jobs_for_campaign_negative_limit_raises_error(self, job_service):
        """Test that negative limit raises ValueError."""
        with pytest.raises(ValueError, match="Limit must be non-negative"):
            job_service.get_jobs_for_campaign(campaign_id=1, user_id=1, limit=-1)

    def test_get_jobs_for_campaign_negative_offset_raises_error(self, job_service):
        """Test that negative offset raises ValueError."""
        with pytest.raises(ValueError, match="Offset must be non-negative"):
            job_service.get_jobs_for_campaign(campaign_id=1, user_id=1, offset=-1)

    def test_get_jobs_for_user_negative_limit_raises_error(self, job_service):
        """Test that negative limit raises ValueError."""
        with pytest.raises(ValueError, match="Limit must be non-negative"):
            job_service.get_jobs_for_user(user_id=1, limit=-1)

    def test_get_jobs_for_user_negative_offset_raises_error(self, job_service):
        """Test that negative offset raises ValueError."""
        with pytest.raises(ValueError, match="Offset must be non-negative"):
            job_service.get_jobs_for_user(user_id=1, offset=-1)

    def test_get_jobs_for_campaign_returns_jobs(self, job_service, mock_database):
        """Test that get_jobs_for_campaign returns job list."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("jsearch_job_id",), ("job_status",), ("job_title",)]
        mock_cursor.fetchall.return_value = [
            ("job1", "waiting", "Software Engineer"),
            ("job2", "approved", "Data Engineer"),
        ]

        jobs = job_service.get_jobs_for_campaign(campaign_id=1, user_id=1)

        assert len(jobs) == 2
        assert jobs[0]["jsearch_job_id"] == "job1"
        assert jobs[0]["job_status"] == "waiting"
        assert jobs[1]["jsearch_job_id"] == "job2"
        assert jobs[1]["job_status"] == "approved"

    def test_get_jobs_for_user_returns_jobs(self, job_service, mock_database):
        """Test that get_jobs_for_user returns job list."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("jsearch_job_id",), ("job_status",), ("job_title",)]
        mock_cursor.fetchall.return_value = [
            ("job1", "waiting", "Software Engineer"),
            ("job2", "approved", "Data Engineer"),
        ]

        jobs = job_service.get_jobs_for_user(user_id=1)

        assert len(jobs) == 2
        assert jobs[0]["jsearch_job_id"] == "job1"
        assert jobs[0]["job_status"] == "waiting"
        assert jobs[1]["jsearch_job_id"] == "job2"
        assert jobs[1]["job_status"] == "approved"

    def test_get_same_company_jobs_returns_list(self, job_service, mock_database):
        """Test that get_same_company_jobs returns list of same-company jobs."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("jsearch_job_id",),
            ("campaign_id",),
            ("job_title",),
            ("job_status",),
        ]
        mock_cursor.fetchall.return_value = [
            ("other-job-1", 2, "Backend Engineer", "applied"),
        ]

        result = job_service.get_same_company_jobs(jsearch_job_id="current-job", user_id=1)

        assert len(result) == 1
        assert result[0]["jsearch_job_id"] == "other-job-1"
        assert result[0]["campaign_id"] == 2
        assert result[0]["job_title"] == "Backend Engineer"
        assert result[0]["job_status"] == "applied"
        assert mock_cursor.execute.called
        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        assert params[1] == "current-job"
        assert params[2] == "current-job"
