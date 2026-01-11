"""Unit tests for JobStatusService."""

from unittest.mock import Mock, patch

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

    @patch("services.jobs.job_service.JobService")
    def test_upsert_status_valid_status(self, mock_job_service_class, job_status_service, mock_database):
        """Test upsert_status with valid status."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock JobService
        mock_job_service = Mock()
        mock_job_service_class.return_value = mock_job_service
        mock_job_service.get_job_by_id.return_value = None

        # Mock get_status call (returns None - no existing status)
        # get_status needs description for columns
        mock_cursor.description = [
            ("user_job_status_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("status",),
            ("created_at",),
            ("updated_at",),
        ]
        # First call: get_status returns None, second call: upsert returns status_id, third call: record_history returns id
        mock_cursor.fetchone.side_effect = [None, (1,), (1,)]

        status_id = job_status_service.upsert_status("job123", 1, "applied")

        assert status_id == 1
        assert mock_cursor.execute.call_count >= 2  # At least get_status and upsert

    def test_upsert_status_invalid_status(self, job_status_service):
        """Test upsert_status raises ValueError for invalid status."""
        with pytest.raises(ValueError, match="Invalid status"):
            job_status_service.upsert_status("job123", 1, "invalid_status")

    @patch("services.jobs.job_service.JobService")
    def test_upsert_status_all_valid_statuses(self, mock_job_service_class, job_status_service, mock_database):
        """Test upsert_status accepts all valid status values."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        # Mock JobService
        mock_job_service = Mock()
        mock_job_service_class.return_value = mock_job_service
        mock_job_service.get_job_by_id.return_value = None

        mock_cursor.description = [
            ("user_job_status_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("status",),
            ("created_at",),
            ("updated_at",),
        ]
        # Mock get_status to return None (no existing status) for each call
        # Each status needs: get_status (None), upsert (status_id), record_history (id)
        mock_cursor.fetchone.side_effect = [None, (1,), (1,)] * 7  # 7 statuses, each needs 3 calls

        valid_statuses = [
            "waiting",
            "applied",
            "approved",
            "rejected",
            "interview",
            "offer",
            "archived",
        ]

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

    def test_record_status_history(self, job_status_service, mock_database):
        """Test record_status_history creates history entry."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("history_id",)]
        mock_cursor.fetchone.return_value = (1,)

        history_id = job_status_service.record_status_history(
            jsearch_job_id="job123",
            user_id=1,
            status="job_found",
            change_type="extraction",
            changed_by="system",
            metadata={"campaign_id": 1},
        )

        assert history_id == 1
        assert mock_cursor.execute.call_count == 1

    def test_record_job_found(self, job_status_service, mock_database):
        """Test record_job_found creates history entry."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("history_id",)]
        mock_cursor.fetchone.return_value = (1,)

        history_id = job_status_service.record_job_found("job123", 1, campaign_id=1)

        assert history_id == 1

    def test_record_ai_update(self, job_status_service, mock_database):
        """Test record_ai_update creates history entry."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("history_id",)]
        mock_cursor.fetchone.return_value = (1,)

        history_id = job_status_service.record_ai_update(
            jsearch_job_id="job123",
            user_id=1,
            enrichment_type="ai_enricher",
            enrichment_details={"skills_extracted": 5},
        )

        assert history_id == 1

    def test_record_document_change(self, job_status_service, mock_database):
        """Test record_document_change creates history entry."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("history_id",)]
        mock_cursor.fetchone.return_value = (1,)

        history_id = job_status_service.record_document_change(
            jsearch_job_id="job123",
            user_id=1,
            change_action="uploaded",
            document_details={"resume_id": 1},
        )

        assert history_id == 1

    def test_record_note_change(self, job_status_service, mock_database):
        """Test record_note_change creates history entry."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("history_id",)]
        mock_cursor.fetchone.return_value = (1,)

        history_id = job_status_service.record_note_change(
            jsearch_job_id="job123",
            user_id=1,
            change_action="added",
            note_id=1,
            note_preview="Test note",
        )

        assert history_id == 1

    def test_get_status_history(self, job_status_service, mock_database):
        """Test get_status_history retrieves history entries."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("history_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("status",),
            ("change_type",),
            ("changed_by",),
            ("changed_by_user_id",),
            ("metadata",),
            ("notes",),
            ("created_at",),
        ]
        mock_cursor.fetchall.return_value = [
            (
                1,
                "job123",
                1,
                "job_found",
                "extraction",
                "system",
                None,
                '{"campaign_id": 1}',
                None,
                None,
            )
        ]

        history = job_status_service.get_status_history("job123", 1)

        assert len(history) == 1
        assert history[0]["status"] == "job_found"
        assert history[0]["metadata"]["campaign_id"] == 1

    def test_get_user_status_history(self, job_status_service, mock_database):
        """Test get_user_status_history retrieves all user history."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("history_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("status",),
            ("change_type",),
            ("changed_by",),
            ("changed_by_user_id",),
            ("metadata",),
            ("notes",),
            ("created_at",),
        ]
        mock_cursor.fetchall.return_value = [
            (1, "job123", 1, "job_found", "extraction", "system", None, "{}", None, None),
            (2, "job456", 1, "updated_by_ai", "enrichment", "ai_enricher", None, "{}", None, None),
        ]

        history = job_status_service.get_user_status_history(1, limit=10)

        assert len(history) == 2

    def test_get_job_status_history(self, job_status_service, mock_database):
        """Test get_job_status_history retrieves all job history."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("history_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("status",),
            ("change_type",),
            ("changed_by",),
            ("changed_by_user_id",),
            ("metadata",),
            ("notes",),
            ("created_at",),
        ]
        mock_cursor.fetchall.return_value = [
            (1, "job123", 1, "job_found", "extraction", "system", None, "{}", None, None),
            (2, "job123", 2, "job_found", "extraction", "system", None, "{}", None, None),
        ]

        history = job_status_service.get_job_status_history("job123", limit=10)

        assert len(history) == 2

    @patch("services.jobs.job_service.JobService")
    def test_upsert_status_records_history_on_change(self, mock_job_service_class, job_status_service, mock_database):
        """Test upsert_status records history when status changes."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock JobService
        mock_job_service = Mock()
        mock_job_service_class.return_value = mock_job_service
        mock_job_service.get_job_by_id.return_value = None

        # get_status needs full description
        mock_cursor.description = [
            ("user_job_status_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("status",),
            ("created_at",),
            ("updated_at",),
        ]
        # First call: get_status returns existing status "waiting"
        # Second call: upsert returns status_id
        # Third call: record_history returns history_id
        mock_cursor.fetchone.side_effect = [
            (1, "job123", 1, "waiting", None, None),  # get_status
            (1,),  # upsert_status
            (1,),  # record_history
        ]

        status_id = job_status_service.upsert_status("job123", 1, "applied")

        assert status_id == 1
        # Should have called execute for get_status, upsert, and record_history
        assert mock_cursor.execute.call_count >= 3

    def test_get_status_history_invalid_limit(self, job_status_service):
        """Test get_status_history raises ValueError for invalid limit."""
        with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
            job_status_service.get_status_history("job123", 1, limit=0)

        with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
            job_status_service.get_status_history("job123", 1, limit=-1)

        with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
            job_status_service.get_status_history("job123", 1, limit=10001)

    def test_get_user_status_history_invalid_limit(self, job_status_service):
        """Test get_user_status_history raises ValueError for invalid limit."""
        with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
            job_status_service.get_user_status_history(1, limit=0)

        with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
            job_status_service.get_user_status_history(1, limit=10001)

    def test_get_user_status_history_invalid_offset(self, job_status_service):
        """Test get_user_status_history raises ValueError for invalid offset."""
        with pytest.raises(ValueError, match="offset must be non-negative"):
            job_status_service.get_user_status_history(1, offset=-1)

    def test_get_job_status_history_invalid_limit(self, job_status_service):
        """Test get_job_status_history raises ValueError for invalid limit."""
        with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
            job_status_service.get_job_status_history("job123", limit=0)

        with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
            job_status_service.get_job_status_history("job123", limit=10001)
