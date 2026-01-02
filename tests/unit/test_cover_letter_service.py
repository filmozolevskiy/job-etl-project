"""Unit tests for CoverLetterService."""

from io import BytesIO
from unittest.mock import Mock

import pytest
from werkzeug.datastructures import FileStorage

from services.documents.cover_letter_service import (
    CoverLetterService,
)
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
def cover_letter_service(mock_database, mock_storage):
    """Create a CoverLetterService instance with mocked dependencies."""
    return CoverLetterService(
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
        filename="test_cover_letter.pdf",
        content_type="application/pdf",
    )
    return file


class TestCoverLetterService:
    """Test cases for CoverLetterService."""

    def test_init_requires_database(self):
        """Test that CoverLetterService requires a database."""
        with pytest.raises(ValueError, match="Database is required"):
            CoverLetterService(database=None)

    def test_create_cover_letter_text_based(self, cover_letter_service, mock_database):
        """Test creating a text-based cover letter."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("cover_letter_id",),
            ("user_id",),
            ("jsearch_job_id",),
            ("cover_letter_name",),
            ("cover_letter_text",),
            ("file_path",),
            ("is_generated",),
            ("generation_prompt",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            1,
            "job123",
            "Test Cover Letter",
            "Dear Hiring Manager...",
            None,
            False,
            None,
            None,
            None,
        )

        result = cover_letter_service.create_cover_letter(
            user_id=1,
            cover_letter_name="Test Cover Letter",
            cover_letter_text="Dear Hiring Manager...",
            jsearch_job_id="job123",
        )

        assert result["cover_letter_id"] == 1
        assert result["cover_letter_text"] == "Dear Hiring Manager..."

    def test_create_cover_letter_requires_text_or_file(self, cover_letter_service):
        """Test that cover letter requires either text or file path."""
        with pytest.raises(ValueError, match="must be provided"):
            cover_letter_service.create_cover_letter(
                user_id=1, cover_letter_name="Test", cover_letter_text=None, file_path=None
            )

    def test_upload_cover_letter_file_success(
        self, cover_letter_service, mock_database, mock_storage, sample_pdf_file
    ):
        """Test successful cover letter file upload."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("cover_letter_id",),
            ("user_id",),
            ("jsearch_job_id",),
            ("cover_letter_name",),
            ("cover_letter_text",),
            ("file_path",),
            ("is_generated",),
            ("generation_prompt",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            1,
            "job123",
            "Test Cover Letter",
            None,
            "cover_letters/1/temp.pdf",
            False,
            None,
            None,
            None,
        )
        mock_storage._sanitize_filename.return_value = "test_cover_letter.pdf"
        mock_storage.save_file.return_value = "cover_letters/1/1_test_cover_letter.pdf"

        result = cover_letter_service.upload_cover_letter_file(
            user_id=1, file=sample_pdf_file, cover_letter_name="Test Cover Letter"
        )

        assert result["cover_letter_id"] == 1
        mock_storage.save_file.assert_called_once()

    def test_get_user_cover_letters(self, cover_letter_service, mock_database):
        """Test getting all cover letters for a user."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("cover_letter_id",),
            ("user_id",),
            ("jsearch_job_id",),
            ("cover_letter_name",),
            ("cover_letter_text",),
            ("file_path",),
            ("is_generated",),
            ("generation_prompt",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchall.return_value = [
            (1, 1, "job123", "Cover Letter 1", "Text 1", None, False, None, None, None),
            (2, 1, None, "Cover Letter 2", None, "path2", False, None, None, None),
        ]

        cover_letters = cover_letter_service.get_user_cover_letters(user_id=1)

        assert len(cover_letters) == 2
        assert cover_letters[0]["cover_letter_name"] == "Cover Letter 1"

    def test_get_cover_letter_by_id_success(self, cover_letter_service, mock_database):
        """Test getting cover letter by ID."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("cover_letter_id",),
            ("user_id",),
            ("jsearch_job_id",),
            ("cover_letter_name",),
            ("cover_letter_text",),
            ("file_path",),
            ("is_generated",),
            ("generation_prompt",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            1,
            "job123",
            "Test Cover Letter",
            "Text content",
            None,
            False,
            None,
            None,
            None,
        )

        cover_letter = cover_letter_service.get_cover_letter_by_id(
            cover_letter_id=1, user_id=1
        )

        assert cover_letter["cover_letter_id"] == 1
        assert cover_letter["cover_letter_name"] == "Test Cover Letter"

    def test_delete_cover_letter_text_based(self, cover_letter_service, mock_database):
        """Test deleting a text-based cover letter."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("cover_letter_id",),
            ("user_id",),
            ("jsearch_job_id",),
            ("cover_letter_name",),
            ("cover_letter_text",),
            ("file_path",),
            ("is_generated",),
            ("generation_prompt",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.side_effect = [
            (1, 1, "job123", "Test", "Text", None, False, None, None, None),
            (1, None),  # DELETE_COVER_LETTER returns
        ]

        result = cover_letter_service.delete_cover_letter(cover_letter_id=1, user_id=1)

        assert result is True

    def test_get_user_cover_letters_with_job_filter(
        self, cover_letter_service, mock_database
    ):
        """Test getting cover letters filtered by job ID."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("cover_letter_id",),
            ("user_id",),
            ("jsearch_job_id",),
            ("cover_letter_name",),
            ("cover_letter_text",),
            ("file_path",),
            ("is_generated",),
            ("generation_prompt",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchall.return_value = [
            (1, 1, "job123", "Job-specific CL", "Text", None, False, None, None, None),
        ]

        cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=1, jsearch_job_id="job123"
        )

        assert len(cover_letters) == 1
        assert cover_letters[0]["jsearch_job_id"] == "job123"

    def test_get_user_cover_letters_all_jobs(
        self, cover_letter_service, mock_database
    ):
        """Test getting all cover letters for a user (no job filter)."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("cover_letter_id",),
            ("user_id",),
            ("jsearch_job_id",),
            ("cover_letter_name",),
            ("cover_letter_text",),
            ("file_path",),
            ("is_generated",),
            ("generation_prompt",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchall.return_value = [
            (1, 1, "job123", "CL 1", "Text 1", None, False, None, None, None),
            (2, 1, None, "CL 2", "Text 2", None, False, None, None, None),
            (3, 1, "job456", "CL 3", "Text 3", None, False, None, None, None),
        ]

        cover_letters = cover_letter_service.get_user_cover_letters(user_id=1)

        assert len(cover_letters) == 3

    def test_download_cover_letter_text_based_raises_error(
        self, cover_letter_service, mock_database
    ):
        """Test that downloading text-based cover letter raises ValueError."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("cover_letter_id",),
            ("user_id",),
            ("jsearch_job_id",),
            ("cover_letter_name",),
            ("cover_letter_text",),
            ("file_path",),
            ("is_generated",),
            ("generation_prompt",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = (
            1,
            1,
            "job123",
            "Text CL",
            "Text content",
            None,  # No file_path = text-based
            False,
            None,
            None,
            None,
        )

        with pytest.raises(ValueError, match="text-based"):
            cover_letter_service.download_cover_letter(cover_letter_id=1, user_id=1)

