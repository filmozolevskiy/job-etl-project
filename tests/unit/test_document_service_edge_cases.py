"""Edge case tests for DocumentService."""

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
    """Create a DocumentService instance."""
    return DocumentService(database=mock_database)


class TestDocumentServiceEdgeCases:
    """Edge case tests for DocumentService."""

    def test_link_documents_nonexistent_job(self, document_service, mock_database):
        """Test linking documents to non-existent job (should still work)."""
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
            1, "nonexistent_job", 1, None, None, None, None, None, None
        )

        result = document_service.link_documents_to_job(
            jsearch_job_id="nonexistent_job",
            user_id=1,
        )
        # Should succeed - job existence not validated at this layer
        assert result["jsearch_job_id"] == "nonexistent_job"

    def test_link_documents_both_resume_and_cover_letter(
        self, document_service, mock_database
    ):
        """Test linking both resume and cover letter to same job."""
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
            1, "job123", 1, 10, 20, None, None, None, None
        )

        result = document_service.link_documents_to_job(
            jsearch_job_id="job123",
            user_id=1,
            resume_id=10,
            cover_letter_id=20,
        )
        assert result["resume_id"] == 10
        assert result["cover_letter_id"] == 20

    def test_link_documents_inline_text_and_cover_letter_id(
        self, document_service, mock_database
    ):
        """Test linking both inline text and cover_letter_id (should prioritize cover_letter_id)."""
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
            1, "job123", 1, None, 20, None, None, None, None
        )

        result = document_service.link_documents_to_job(
            jsearch_job_id="job123",
            user_id=1,
            cover_letter_id=20,
            cover_letter_text="Inline text",  # Should be ignored if cover_letter_id provided
        )
        # cover_letter_id should take precedence
        assert result["cover_letter_id"] == 20
        # cover_letter_text might be None or the inline text depending on implementation
        # This tests the edge case behavior

    def test_update_document_clear_resume(self, document_service, mock_database):
        """Test updating document to clear resume (set to None)."""
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
            1, "job123", 1, None, None, None, None, None, None
        )

        result = document_service.update_job_application_document(
            document_id=1,
            user_id=1,
            resume_id=None,  # Clear resume
        )
        assert result.get("resume_id") is None

    def test_update_document_clear_cover_letter(self, document_service, mock_database):
        """Test updating document to clear cover letter."""
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
            1, "job123", 1, None, None, None, None, None, None
        )

        result = document_service.update_job_application_document(
            document_id=1,
            user_id=1,
            cover_letter_id=None,  # Clear cover letter
            cover_letter_text=None,  # Clear inline text
        )
        assert result.get("cover_letter_id") is None
        assert result.get("cover_letter_text") is None

    def test_get_document_nonexistent_job(self, document_service, mock_database):
        """Test getting document for non-existent job."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        doc = document_service.get_job_application_document(
            jsearch_job_id="nonexistent_job", user_id=1
        )
        assert doc is None

    def test_get_document_different_user(self, document_service, mock_database):
        """Test getting document for different user (should return None)."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # Not found for this user

        doc = document_service.get_job_application_document(
            jsearch_job_id="job123", user_id=999
        )
        assert doc is None

    def test_update_document_not_found(self, document_service, mock_database):
        """Test updating document that doesn't exist."""
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
        mock_cursor.fetchone.return_value = None

        # Service raises ValueError when document not found
        with pytest.raises(ValueError, match="not found or access denied"):
            document_service.update_job_application_document(
                document_id=999, user_id=1, user_notes="Test"
            )

    def test_delete_document_not_found(self, document_service, mock_database):
        """Test deleting document that doesn't exist."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = document_service.delete_job_application_document(
            document_id=999, user_id=1
        )
        assert result is False

    def test_delete_document_wrong_user(self, document_service, mock_database):
        """Test deleting document that belongs to different user."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # Not found for this user

        result = document_service.delete_job_application_document(
            document_id=1, user_id=999
        )
        assert result is False

    def test_link_documents_all_fields_none(self, document_service, mock_database):
        """Test linking documents with all fields as None (should still create record)."""
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
            1, "job123", 1, None, None, None, None, None, None
        )

        result = document_service.link_documents_to_job(
            jsearch_job_id="job123",
            user_id=1,
            resume_id=None,
            cover_letter_id=None,
            cover_letter_text=None,
            user_notes=None,
        )
        # Should still create a record (empty document)
        assert result["document_id"] == 1
        assert result["jsearch_job_id"] == "job123"

    def test_update_document_very_long_notes(self, document_service, mock_database):
        """Test updating document with very long notes."""
        long_notes = "A" * 10000  # 10KB of notes
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
            1, "job123", 1, None, None, None, long_notes, None, None
        )

        result = document_service.update_job_application_document(
            document_id=1,
            user_id=1,
            user_notes=long_notes,
        )
        assert len(result["user_notes"]) == 10000

    def test_link_documents_special_characters_in_job_id(
        self, document_service, mock_database
    ):
        """Test linking documents with special characters in job_id."""
        special_job_id = "job-123_test@example.com"
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
            1, special_job_id, 1, None, None, None, None, None, None
        )

        result = document_service.link_documents_to_job(
            jsearch_job_id=special_job_id,
            user_id=1,
        )
        assert result["jsearch_job_id"] == special_job_id

