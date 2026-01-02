"""Unit tests for ResumeService."""

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
    """Create a ResumeService instance with mocked dependencies."""
    return ResumeService(
        database=mock_database,
        storage_service=mock_storage,
        max_file_size=5 * 1024 * 1024,
        allowed_extensions=["pdf", "docx"],
    )


@pytest.fixture
def sample_pdf_file():
    """Create a sample PDF file for testing."""
    file_content = b"%PDF-1.4\nsample pdf content"
    file = FileStorage(
        stream=BytesIO(file_content),
        filename="test_resume.pdf",
        content_type="application/pdf",
    )
    return file


@pytest.fixture
def sample_docx_file():
    """Create a sample DOCX file for testing."""
    # DOCX files start with PK (ZIP signature)
    file_content = b"PK\x03\x04sample docx content"
    file = FileStorage(
        stream=BytesIO(file_content),
        filename="test_resume.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    return file


class TestResumeService:
    """Test cases for ResumeService."""

    def test_init_requires_database(self):
        """Test that ResumeService requires a database."""
        with pytest.raises(ValueError, match="Database is required"):
            ResumeService(database=None)

    def test_validate_file_valid_pdf(self, resume_service, sample_pdf_file):
        """Test file validation with valid PDF."""
        ext, mime = resume_service._validate_file(sample_pdf_file)
        assert ext == "pdf"
        assert mime == "application/pdf"

    def test_validate_file_valid_docx(self, resume_service, sample_docx_file):
        """Test file validation with valid DOCX."""
        ext, mime = resume_service._validate_file(sample_docx_file)
        assert ext == "docx"

    def test_validate_file_no_file(self, resume_service):
        """Test file validation raises error when no file provided."""
        with pytest.raises(ResumeValidationError, match="No file provided"):
            resume_service._validate_file(None)

    def test_validate_file_too_large(self, resume_service):
        """Test file validation raises error when file is too large."""
        large_content = b"x" * (6 * 1024 * 1024)  # 6 MB
        file = FileStorage(stream=BytesIO(large_content), filename="large.pdf")
        with pytest.raises(ResumeValidationError, match="exceeds maximum"):
            resume_service._validate_file(file)

    def test_validate_file_invalid_extension(self, resume_service):
        """Test file validation raises error for invalid extension."""
        file = FileStorage(stream=BytesIO(b"content"), filename="test.txt")
        with pytest.raises(ResumeValidationError, match="not allowed"):
            resume_service._validate_file(file)

    def test_upload_resume_success(
        self, resume_service, mock_database, mock_storage, sample_pdf_file
    ):
        """Test successful resume upload."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("resume_id",),
            ("user_id",),
            ("resume_name",),
            ("file_path",),
            ("file_size",),
            ("file_type",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            1,
            "Test Resume",
            "resumes/1/temp.pdf",
            100,
            "application/pdf",
            None,
            None,
        )
        mock_storage._sanitize_filename.return_value = "test_resume.pdf"
        mock_storage.save_file.return_value = "resumes/1/1_test_resume.pdf"

        result = resume_service.upload_resume(
            user_id=1, file=sample_pdf_file, resume_name="Test Resume"
        )

        assert result["resume_id"] == 1
        assert result["resume_name"] == "Test Resume"
        mock_storage.save_file.assert_called_once()

    def test_get_user_resumes(self, resume_service, mock_database):
        """Test getting all resumes for a user."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("resume_id",),
            ("user_id",),
            ("resume_name",),
            ("file_path",),
            ("file_size",),
            ("file_type",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchall.return_value = [
            (1, 1, "Resume 1", "path1", 100, "pdf", None, None),
            (2, 1, "Resume 2", "path2", 200, "docx", None, None),
        ]

        resumes = resume_service.get_user_resumes(user_id=1)

        assert len(resumes) == 2
        assert resumes[0]["resume_name"] == "Resume 1"

    def test_get_resume_by_id_success(self, resume_service, mock_database):
        """Test getting resume by ID."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("resume_id",),
            ("user_id",),
            ("resume_name",),
            ("file_path",),
            ("file_size",),
            ("file_type",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            1,
            "Test Resume",
            "path",
            100,
            "pdf",
            None,
            None,
        )

        resume = resume_service.get_resume_by_id(resume_id=1, user_id=1)

        assert resume["resume_id"] == 1
        assert resume["resume_name"] == "Test Resume"

    def test_get_resume_by_id_not_found(self, resume_service, mock_database):
        """Test getting resume by ID when not found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        with pytest.raises(ValueError, match="not found"):
            resume_service.get_resume_by_id(resume_id=999, user_id=1)

    def test_delete_resume_success(self, resume_service, mock_database, mock_storage):
        """Test successful resume deletion."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("resume_id",),
            ("user_id",),
            ("resume_name",),
            ("file_path",),
            ("file_size",),
            ("file_type",),
            ("created_at",),
            ("updated_at",),
        ]
        # First call: get_resume_by_id
        mock_cursor.fetchone.return_value = (
            1,
            1,
            "Test Resume",
            "resumes/1/1_test.pdf",
            100,
            "pdf",
            None,
            None,
        )
        # Second call: delete_resume
        mock_cursor.fetchone.side_effect = [
            (1, 1, "Test Resume", "resumes/1/1_test.pdf", 100, "pdf", None, None),
            (1, "resumes/1/1_test.pdf"),  # DELETE_RESUME returns
        ]
        mock_storage.delete_file.return_value = True

        result = resume_service.delete_resume(resume_id=1, user_id=1)

        assert result is True
        mock_storage.delete_file.assert_called_once()

    def test_download_resume_success(self, resume_service, mock_database, mock_storage):
        """Test successful resume download."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("resume_id",),
            ("user_id",),
            ("resume_name",),
            ("file_path",),
            ("file_size",),
            ("file_type",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            1,
            "Test Resume",
            "resumes/1/1_test.pdf",
            100,
            "application/pdf",
            None,
            None,
        )
        mock_storage.get_file.return_value = b"file content"

        content, filename, mime_type = resume_service.download_resume(resume_id=1, user_id=1)

        assert content == b"file content"
        assert "Test Resume" in filename
        assert mime_type == "application/pdf"
