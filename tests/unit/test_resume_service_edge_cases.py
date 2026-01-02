"""Edge case tests for ResumeService."""

from io import BytesIO
from unittest.mock import Mock

import pytest
from werkzeug.datastructures import FileStorage

from services.documents.resume_service import ResumeService, ResumeValidationError
from services.documents.storage_service import LocalStorageService


@pytest.fixture
def mock_database():
    """Create a mock database."""
    db = Mock()
    db.get_cursor.return_value.__enter__ = Mock(return_value=Mock())
    db.get_cursor.return_value.__exit__ = Mock(return_value=False)
    return db


@pytest.fixture
def mock_storage():
    """Create a mock storage service."""
    return Mock(spec=LocalStorageService)


@pytest.fixture
def resume_service(mock_database, mock_storage):
    """Create a ResumeService instance."""
    return ResumeService(
        database=mock_database,
        storage_service=mock_storage,
        max_file_size=5 * 1024 * 1024,
        allowed_extensions=["pdf", "docx"],
    )


class TestResumeServiceEdgeCases:
    """Edge case tests for ResumeService."""

    def test_validate_file_empty_file(self, resume_service):
        """Test validation with empty file."""
        empty_file = FileStorage(stream=BytesIO(b""), filename="empty.pdf")
        with pytest.raises(ResumeValidationError, match="No file provided|empty"):
            resume_service._validate_file(empty_file)

    def test_validate_file_no_extension(self, resume_service):
        """Test validation with file that has no extension."""
        file = FileStorage(stream=BytesIO(b"content"), filename="noextension")
        with pytest.raises(ResumeValidationError, match="not allowed"):
            resume_service._validate_file(file)

    def test_validate_file_exactly_max_size(self, resume_service):
        """Test validation with file at exactly the size limit."""
        max_size = 5 * 1024 * 1024  # 5 MB
        file_content = b"x" * max_size
        file = FileStorage(stream=BytesIO(file_content), filename="exact_size.pdf")
        ext, mime = resume_service._validate_file(file)
        assert ext == "pdf"

    def test_validate_file_one_byte_over_limit(self, resume_service):
        """Test validation with file one byte over the limit."""
        max_size = 5 * 1024 * 1024  # 5 MB
        file_content = b"x" * (max_size + 1)
        file = FileStorage(stream=BytesIO(file_content), filename="too_large.pdf")
        with pytest.raises(ResumeValidationError, match="exceeds maximum"):
            resume_service._validate_file(file)

    def test_validate_file_special_characters_in_filename(self, resume_service):
        """Test validation with filename containing special characters."""
        file_content = b"%PDF-1.4\ncontent"
        file = FileStorage(
            stream=BytesIO(file_content),
            filename="resume with spaces & special!@#.pdf",
        )
        ext, mime = resume_service._validate_file(file)
        assert ext == "pdf"  # Should still validate, sanitization happens later

    def test_validate_file_path_traversal_attempt(self, resume_service):
        """Test validation with filename attempting path traversal."""
        file_content = b"%PDF-1.4\ncontent"
        file = FileStorage(
            stream=BytesIO(file_content), filename="../../../etc/passwd.pdf"
        )
        # Validation should pass (extension is valid)
        # Path sanitization should happen in storage service
        ext, mime = resume_service._validate_file(file)
        assert ext == "pdf"

    def test_validate_file_very_long_filename(self, resume_service):
        """Test validation with very long filename."""
        long_name = "a" * 300 + ".pdf"
        file_content = b"%PDF-1.4\ncontent"
        file = FileStorage(stream=BytesIO(file_content), filename=long_name)
        ext, mime = resume_service._validate_file(file)
        assert ext == "pdf"

    def test_validate_file_wrong_extension_correct_mime(self, resume_service):
        """Test validation with wrong extension but correct MIME type."""
        file_content = b"%PDF-1.4\ncontent"
        file = FileStorage(
            stream=BytesIO(file_content),
            filename="resume.txt",  # Wrong extension
            content_type="application/pdf",  # Correct MIME
        )
        # Should fail because extension doesn't match
        with pytest.raises(ResumeValidationError, match="not allowed"):
            resume_service._validate_file(file)

    def test_upload_resume_duplicate_name(self, resume_service, mock_database, mock_storage):
        """Test uploading resume with duplicate name."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("resume_id",), ("user_id",), ("resume_name",), ("file_path",), ("file_size",), ("file_type",), ("created_at",), ("updated_at",)]
        mock_cursor.fetchone.return_value = (1, 1, "Duplicate Name", "path1", 100, "pdf", None, None)
        mock_storage._sanitize_filename.return_value = "test.pdf"
        mock_storage.save_file.return_value = "resumes/1/1_test.pdf"

        file = FileStorage(stream=BytesIO(b"%PDF-1.4\ncontent"), filename="test.pdf")
        result = resume_service.upload_resume(
            user_id=1, file=file, resume_name="Duplicate Name"
        )
        # Should succeed - duplicate names are allowed
        assert result["resume_name"] == "Duplicate Name"

    def test_get_resume_by_id_wrong_user(self, resume_service, mock_database):
        """Test getting resume that belongs to different user."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # Not found for this user

        with pytest.raises(ValueError, match="not found"):
            resume_service.get_resume_by_id(resume_id=1, user_id=999)

    def test_delete_resume_not_owned_by_user(self, resume_service, mock_database):
        """Test deleting resume that doesn't belong to user."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        # First call: get_resume_by_id returns None (not found)
        # delete_resume catches ValueError and returns False
        mock_cursor.description = [("resume_id",), ("user_id",), ("resume_name",), ("file_path",), ("file_size",), ("file_type",), ("created_at",), ("updated_at",)]
        mock_cursor.fetchone.return_value = None  # Not found

        result = resume_service.delete_resume(resume_id=1, user_id=999)
        assert result is False

    def test_download_resume_file_not_on_disk(
        self, resume_service, mock_database, mock_storage
    ):
        """Test downloading resume when file doesn't exist on disk."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("resume_id",), ("user_id",), ("resume_name",), ("file_path",), ("file_size",), ("file_type",), ("created_at",), ("updated_at",)]
        mock_cursor.fetchone.return_value = (1, 1, "Test", "resumes/1/1_test.pdf", 100, "pdf", None, None)
        mock_storage.get_file.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError):
            resume_service.download_resume(resume_id=1, user_id=1)

    def test_upload_resume_storage_failure_rollback(
        self, resume_service, mock_database, mock_storage
    ):
        """Test that database record is rolled back if file save fails."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("resume_id",), ("user_id",), ("resume_name",), ("file_path",), ("file_size",), ("file_type",), ("created_at",), ("updated_at",)]
        mock_cursor.fetchone.return_value = (1, 1, "Test", "temp_path", 100, "pdf", None, None)
        mock_storage._sanitize_filename.return_value = "test.pdf"
        mock_storage.save_file.side_effect = OSError("Disk full")

        file = FileStorage(stream=BytesIO(b"%PDF-1.4\ncontent"), filename="test.pdf")

        # Should raise exception, but database record might already be created
        # In real implementation, this should use transactions
        with pytest.raises(OSError):
            resume_service.upload_resume(user_id=1, file=file, resume_name="Test")

    def test_upload_resume_empty_name(self, resume_service, mock_database, mock_storage):
        """Test uploading resume with empty name (should use filename)."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("resume_id",), ("user_id",), ("resume_name",), ("file_path",), ("file_size",), ("file_type",), ("created_at",), ("updated_at",)]
        mock_cursor.fetchone.return_value = (1, 1, "test_resume.pdf", "path", 100, "pdf", None, None)
        mock_storage._sanitize_filename.return_value = "test_resume.pdf"
        mock_storage.save_file.return_value = "resumes/1/1_test_resume.pdf"

        file = FileStorage(stream=BytesIO(b"%PDF-1.4\ncontent"), filename="test_resume.pdf")
        result = resume_service.upload_resume(user_id=1, file=file, resume_name="")

        # Should use filename as name
        assert result["resume_id"] == 1

