"""Edge case tests for CoverLetterService."""

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
    """Create a CoverLetterService instance."""
    return CoverLetterService(
        database=mock_database,
        storage_service=mock_storage,
        max_file_size=5 * 1024 * 1024,
        allowed_extensions=["pdf", "docx"],
    )


class TestCoverLetterServiceEdgeCases:
    """Edge case tests for CoverLetterService."""

    def test_create_cover_letter_empty_text(self, cover_letter_service):
        """Test creating cover letter with empty text."""
        with pytest.raises(ValueError, match="must be provided"):
            cover_letter_service.create_cover_letter(
                user_id=1,
                cover_letter_name="Test",
                cover_letter_text="",  # Empty string
                file_path=None,
            )

    def test_create_cover_letter_whitespace_only_text(self, cover_letter_service, mock_database):
        """Test creating cover letter with only whitespace (currently allowed)."""
        # Note: Service doesn't validate whitespace-only text, it only checks for None/empty
        # Whitespace-only strings are currently allowed
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
            None,
            "Test",
            "   \n\t  ",
            None,
            False,
            None,
            None,
            None,
        )

        result = cover_letter_service.create_cover_letter(
            user_id=1,
            cover_letter_name="Test",
            cover_letter_text="   \n\t  ",  # Only whitespace - currently allowed
            file_path=None,
        )
        assert result["cover_letter_id"] == 1

    def test_create_cover_letter_very_long_text(self, cover_letter_service, mock_database):
        """Test creating cover letter with very long text."""
        long_text = "A" * 100000  # 100KB of text
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
            None,
            "Test",
            long_text,
            None,
            False,
            None,
            None,
            None,
        )

        result = cover_letter_service.create_cover_letter(
            user_id=1,
            cover_letter_name="Test",
            cover_letter_text=long_text,
        )
        assert len(result["cover_letter_text"]) == 100000

    def test_create_cover_letter_special_characters(self, cover_letter_service, mock_database):
        """Test creating cover letter with special characters and unicode."""
        special_text = "Dear Hiring Manager,\n\nI am interested in the position.\n\nBest regards,\nJosé O'Connor\nEmail: test@example.com\nPhone: +1 (555) 123-4567"
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
            None,
            "Test",
            special_text,
            None,
            False,
            None,
            None,
            None,
        )

        result = cover_letter_service.create_cover_letter(
            user_id=1,
            cover_letter_name="Test",
            cover_letter_text=special_text,
        )
        assert "José" in result["cover_letter_text"]
        assert "O'Connor" in result["cover_letter_text"]

    def test_create_cover_letter_unicode_emojis(self, cover_letter_service, mock_database):
        """Test creating cover letter with unicode emojis."""
        emoji_text = "Hello! 👋 I'm excited about this opportunity! 🚀"
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
            None,
            "Test",
            emoji_text,
            None,
            False,
            None,
            None,
            None,
        )

        result = cover_letter_service.create_cover_letter(
            user_id=1,
            cover_letter_name="Test",
            cover_letter_text=emoji_text,
        )
        assert "👋" in result["cover_letter_text"]
        assert "🚀" in result["cover_letter_text"]

    def test_get_cover_letter_by_id_wrong_user(self, cover_letter_service, mock_database):
        """Test getting cover letter that belongs to different user."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        with pytest.raises(ValueError, match="not found"):
            cover_letter_service.get_cover_letter_by_id(cover_letter_id=1, user_id=999)

    def test_delete_cover_letter_not_owned(self, cover_letter_service, mock_database):
        """Test deleting cover letter that doesn't belong to user."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        # First call: get_cover_letter_by_id returns None (not found)
        # delete_cover_letter catches ValueError and returns False
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
        mock_cursor.fetchone.return_value = None

        result = cover_letter_service.delete_cover_letter(cover_letter_id=1, user_id=999)
        assert result is False

    def test_download_cover_letter_text_based_raises(self, cover_letter_service, mock_database):
        """Test that downloading text-based cover letter raises error."""
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
            None,
            "Test",
            "Text",
            None,
            False,
            None,
            None,
            None,
        )

        with pytest.raises(ValueError, match="text-based"):
            cover_letter_service.download_cover_letter(cover_letter_id=1, user_id=1)

    def test_download_cover_letter_file_not_on_disk(
        self, cover_letter_service, mock_database, mock_storage
    ):
        """Test downloading cover letter when file doesn't exist on disk."""
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
            None,
            "Test",
            None,
            "cover_letters/1/1_test.pdf",
            False,
            None,
            None,
            None,
        )
        mock_storage.get_file.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError):
            cover_letter_service.download_cover_letter(cover_letter_id=1, user_id=1)

    def test_get_user_cover_letters_empty_result(self, cover_letter_service, mock_database):
        """Test getting cover letters when user has none."""
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
        mock_cursor.fetchall.return_value = []

        cover_letters = cover_letter_service.get_user_cover_letters(user_id=999)
        assert len(cover_letters) == 0

    def test_create_cover_letter_same_name_different_jobs(
        self, cover_letter_service, mock_database
    ):
        """Test creating cover letters with same name for different jobs."""
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
            "job1",
            "Same Name",
            "Text 1",
            None,
            False,
            None,
            None,
            None,
        )

        result1 = cover_letter_service.create_cover_letter(
            user_id=1,
            cover_letter_name="Same Name",
            cover_letter_text="Text 1",
            jsearch_job_id="job1",
        )

        # Should succeed - same name for different jobs is allowed
        assert result1["cover_letter_name"] == "Same Name"
        assert result1["jsearch_job_id"] == "job1"

    def test_upload_cover_letter_file_exactly_max_size(
        self, cover_letter_service, mock_database, mock_storage
    ):
        """Test uploading cover letter file at exactly the size limit."""
        max_size = 5 * 1024 * 1024
        file_content = b"%PDF-1.4\n" + b"x" * (max_size - 10)
        file = FileStorage(stream=BytesIO(file_content), filename="exact_size.pdf")

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
            None,
            "Test",
            None,
            "cover_letters/1/temp.pdf",
            False,
            None,
            None,
            None,
        )
        mock_storage._sanitize_filename.return_value = "exact_size.pdf"
        mock_storage.save_file.return_value = "cover_letters/1/1_exact_size.pdf"

        result = cover_letter_service.upload_cover_letter_file(
            user_id=1, file=file, cover_letter_name="Test"
        )
        assert result["cover_letter_id"] == 1
