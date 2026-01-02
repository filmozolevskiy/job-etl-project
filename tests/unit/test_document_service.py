"""Unit tests for DocumentService."""

from unittest.mock import Mock

import pytest

from services.documents.document_service import DocumentService


@pytest.fixture
def mock_database():
    """Create a mock database."""
    db = Mock()
    db.get_cursor.return_value.__enter__ = Mock(return_value=Mock())
    db.get_cursor.return_value.__exit__ = Mock(return_value=False)
    return db


@pytest.fixture
def document_service(mock_database):
    """Create a DocumentService instance with mocked database."""
    return DocumentService(database=mock_database)


class TestDocumentService:
    """Test cases for DocumentService."""

    def test_init_requires_database(self):
        """Test that DocumentService requires a database."""
        with pytest.raises(ValueError, match="Database is required"):
            DocumentService(database=None)

    def test_link_documents_to_job_success(self, document_service, mock_database):
        """Test linking documents to a job."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("document_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("resume_id",),
            ("cover_letter_id",),
            ("cover_letter_text",),
            ("user_notes",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            "job123",
            1,
            10,
            20,
            None,
            "Notes",
            None,
            None,
        )

        result = document_service.link_documents_to_job(
            jsearch_job_id="job123",
            user_id=1,
            resume_id=10,
            cover_letter_id=20,
            user_notes="Notes",
        )

        assert result["document_id"] == 1
        assert result["resume_id"] == 10
        assert result["cover_letter_id"] == 20

    def test_get_job_application_document_found(
        self, document_service, mock_database
    ):
        """Test getting job application document when found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("document_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("resume_id",),
            ("cover_letter_id",),
            ("cover_letter_text",),
            ("user_notes",),
            ("created_at",),
            ("updated_at",),
            ("resume_name",),
            ("resume_file_path",),
            ("resume_file_type",),
            ("cover_letter_name",),
            ("cover_letter_file_path",),
            ("cover_letter_text_full",),
            ("is_generated",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            "job123",
            1,
            10,
            20,
            None,
            "Notes",
            None,
            None,
            "Resume",
            "path1",
            "pdf",
            "Cover Letter",
            "path2",
            None,
            False,
        )

        doc = document_service.get_job_application_document(
            jsearch_job_id="job123", user_id=1
        )

        assert doc is not None
        assert doc["document_id"] == 1
        assert doc["resume_id"] == 10

    def test_get_job_application_document_not_found(
        self, document_service, mock_database
    ):
        """Test getting job application document when not found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        doc = document_service.get_job_application_document(
            jsearch_job_id="job123", user_id=1
        )

        assert doc is None

    def test_update_job_application_document_success(
        self, document_service, mock_database
    ):
        """Test updating job application document."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("document_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("resume_id",),
            ("cover_letter_id",),
            ("cover_letter_text",),
            ("user_notes",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            "job123",
            1,
            10,
            20,
            None,
            "Updated notes",
            None,
            None,
        )

        result = document_service.update_job_application_document(
            document_id=1,
            user_id=1,
            user_notes="Updated notes",
        )

        assert result["user_notes"] == "Updated notes"

    def test_delete_job_application_document_success(
        self, document_service, mock_database
    ):
        """Test deleting job application document."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)

        result = document_service.delete_job_application_document(
            document_id=1, user_id=1
        )

        assert result is True

    def test_delete_job_application_document_not_found(
        self, document_service, mock_database
    ):
        """Test deleting job application document when not found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = document_service.delete_job_application_document(
            document_id=999, user_id=1
        )

        assert result is False

    def test_link_documents_with_inline_text(
        self, document_service, mock_database
    ):
        """Test linking documents with inline cover letter text."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("document_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("resume_id",),
            ("cover_letter_id",),
            ("cover_letter_text",),
            ("user_notes",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            "job123",
            1,
            10,
            None,  # No cover_letter_id
            "Inline cover letter text",  # Inline text
            "Notes",
            None,
            None,
        )

        result = document_service.link_documents_to_job(
            jsearch_job_id="job123",
            user_id=1,
            resume_id=10,
            cover_letter_text="Inline cover letter text",
            user_notes="Notes",
        )

        assert result["document_id"] == 1
        assert result["resume_id"] == 10
        assert result["cover_letter_text"] == "Inline cover letter text"
        assert result.get("cover_letter_id") is None

    def test_update_document_partial_update(
        self, document_service, mock_database
    ):
        """Test updating document with only some fields (partial update)."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("document_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("resume_id",),
            ("cover_letter_id",),
            ("cover_letter_text",),
            ("user_notes",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            "job123",
            1,
            10,  # Keep existing resume_id
            20,  # Keep existing cover_letter_id
            None,
            "Updated notes only",  # Only notes updated
            None,
            None,
        )

        result = document_service.update_job_application_document(
            document_id=1,
            user_id=1,
            user_notes="Updated notes only",
            # resume_id and cover_letter_id not provided (should keep existing)
        )

        assert result["user_notes"] == "Updated notes only"
        assert result["resume_id"] == 10  # Should be preserved
        assert result["cover_letter_id"] == 20  # Should be preserved

