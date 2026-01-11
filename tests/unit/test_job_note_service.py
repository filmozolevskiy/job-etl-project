"""Unit tests for JobNoteService."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from services.jobs.job_note_service import JobNoteService


@pytest.fixture
def mock_database():
    """Create a mock database."""
    db = Mock()
    db.get_cursor.return_value.__enter__ = Mock(return_value=Mock())
    db.get_cursor.return_value.__exit__ = Mock(return_value=False)
    return db


@pytest.fixture
def job_note_service(mock_database):
    """Create a JobNoteService instance with mocked database."""
    return JobNoteService(database=mock_database)


class TestJobNoteService:
    """Test cases for JobNoteService."""

    def test_init_requires_database(self):
        """Test that JobNoteService requires a database."""
        with pytest.raises(ValueError, match="Database is required"):
            JobNoteService(database=None)

    def test_get_notes_empty_list(self, job_note_service, mock_database):
        """Test get_notes returns empty list when no notes found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("note_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("note_text",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchall.return_value = []

        result = job_note_service.get_notes("job123", 1)

        assert result == []
        mock_cursor.execute.assert_called_once()

    def test_get_notes_returns_list(self, job_note_service, mock_database):
        """Test get_notes returns list of notes with is_modified flag."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("note_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("note_text",),
            ("created_at",),
            ("updated_at",),
        ]
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        updated_at = datetime(2024, 1, 1, 12, 0, 0)
        mock_cursor.fetchall.return_value = [
            (1, "job123", 1, "First note", created_at, updated_at),
            (2, "job123", 1, "Second note", created_at, updated_at),
        ]

        result = job_note_service.get_notes("job123", 1)

        assert len(result) == 2
        assert result[0]["note_id"] == 1
        assert result[0]["note_text"] == "First note"
        assert result[0]["is_modified"] is False  # created_at == updated_at
        assert result[1]["note_id"] == 2
        assert result[1]["note_text"] == "Second note"
        assert result[1]["is_modified"] is False

    def test_get_notes_detects_modified_notes(self, job_note_service, mock_database):
        """Test get_notes correctly identifies modified notes."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("note_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("note_text",),
            ("created_at",),
            ("updated_at",),
        ]
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        updated_at = datetime(2024, 1, 2, 12, 0, 0)  # Different from created_at
        mock_cursor.fetchall.return_value = [
            (1, "job123", 1, "Edited note", created_at, updated_at),
        ]

        result = job_note_service.get_notes("job123", 1)

        assert len(result) == 1
        assert result[0]["is_modified"] is True

    def test_get_note_by_id_not_found(self, job_note_service, mock_database):
        """Test get_note_by_id returns None when note not found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("note_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("note_text",),
            ("created_at",),
            ("updated_at",),
        ]
        mock_cursor.fetchone.return_value = None

        result = job_note_service.get_note_by_id(999, 1)

        assert result is None

    def test_get_note_by_id_found(self, job_note_service, mock_database):
        """Test get_note_by_id returns note when found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [
            ("note_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("note_text",),
            ("created_at",),
            ("updated_at",),
        ]
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        updated_at = datetime(2024, 1, 1, 12, 0, 0)
        mock_cursor.fetchone.return_value = (1, "job123", 1, "Test note", created_at, updated_at)

        result = job_note_service.get_note_by_id(1, 1)

        assert result is not None
        assert result["note_id"] == 1
        assert result["note_text"] == "Test note"
        assert result["jsearch_job_id"] == "job123"
        assert result["user_id"] == 1
        assert result["is_modified"] is False

    def test_add_note_success(self, job_note_service, mock_database):
        """Test add_note successfully adds a new note."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (123,)

        note_id = job_note_service.add_note("job123", 1, "New note text")

        assert note_id == 123
        mock_cursor.execute.assert_called_once()
        # Verify parameters: (query, (jsearch_job_id, user_id, note_text))
        call_args = mock_cursor.execute.call_args[0]
        assert call_args[1][2] == "New note text"  # Third parameter (note_text)

    def test_add_note_strips_whitespace(self, job_note_service, mock_database):
        """Test add_note strips whitespace from note text."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (123,)

        job_note_service.add_note("job123", 1, "  Note with spaces  ")

        call_args = mock_cursor.execute.call_args[0]
        assert call_args[1][2] == "Note with spaces"  # Third parameter (note_text)

    def test_add_note_handles_exceptions(self, job_note_service, mock_database):
        """Test add_note handles database exceptions."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            job_note_service.add_note("job123", 1, "Test note")

    def test_add_note_fails_when_no_result(self, job_note_service, mock_database):
        """Test add_note raises ValueError when no result returned."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        with pytest.raises(ValueError, match="Failed to add note"):
            job_note_service.add_note("job123", 1, "Test note")

    def test_update_note_success(self, job_note_service, mock_database):
        """Test update_note successfully updates a note."""
        mock_cursor = Mock()
        # Use the same pattern as test_delete_note_success
        mock_database.get_cursor.return_value.__enter__ = Mock(return_value=mock_cursor)

        # Setup description for get_note_by_id call (needs to match query columns)
        mock_cursor.description = [
            ("note_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("note_text",),
            ("created_at",),
            ("updated_at",),
        ]
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        updated_at = datetime(2024, 1, 1, 12, 0, 0)
        # First call (update) returns note_id, second call (get_note_by_id) returns note
        mock_cursor.fetchone.side_effect = [
            (1,),  # update_note (returns note_id)
            (1, "job123", 1, "Old note", created_at, updated_at),  # get_note_by_id
        ]

        result = job_note_service.update_note(1, 1, "Updated note text")

        assert result is True
        # Verify update query was called (first execute call)
        assert mock_cursor.execute.call_count >= 1  # At least once for update
        # Verify parameters of update query: (query, (note_text, note_id, user_id))
        call_args = mock_cursor.execute.call_args_list[0][0]  # First call (update)
        assert call_args[1][0] == "Updated note text"  # First parameter (note_text)

    def test_update_note_strips_whitespace(self, job_note_service, mock_database):
        """Test update_note strips whitespace from note text."""
        mock_cursor = Mock()
        # Use the same pattern as test_delete_note_success
        mock_database.get_cursor.return_value.__enter__ = Mock(return_value=mock_cursor)

        mock_cursor.description = [
            ("note_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("note_text",),
            ("created_at",),
            ("updated_at",),
        ]
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        updated_at = datetime(2024, 1, 1, 12, 0, 0)
        # First call (update) returns note_id, second call (get_note_by_id) returns note
        mock_cursor.fetchone.side_effect = [
            (1,),  # update_note (returns note_id)
            (1, "job123", 1, "Old note", created_at, updated_at),  # get_note_by_id
        ]

        job_note_service.update_note(1, 1, "  Updated note  ")

        call_args = mock_cursor.execute.call_args_list[0][0]  # First call (update)
        assert call_args[1][0] == "Updated note"  # First parameter (note_text)

    def test_update_note_not_found(self, job_note_service, mock_database):
        """Test update_note returns False when note not found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = job_note_service.update_note(999, 1, "Updated note")

        assert result is False

    def test_update_note_handles_exceptions(self, job_note_service, mock_database):
        """Test update_note handles database exceptions."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            job_note_service.update_note(1, 1, "Updated note")

    def test_delete_note_success(self, job_note_service, mock_database):
        """Test delete_note successfully deletes a note."""
        mock_cursor = Mock()
        # Override the fixture's __enter__ to return our configured cursor
        mock_database.get_cursor.return_value.__enter__ = Mock(return_value=mock_cursor)

        mock_cursor.description = [
            ("note_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("note_text",),
            ("created_at",),
            ("updated_at",),
        ]
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        updated_at = datetime(2024, 1, 1, 12, 0, 0)
        # First call (get_note_by_id) returns note, second call (delete) returns note_id
        mock_cursor.fetchone.side_effect = [
            (1, "job123", 1, "Test note", created_at, updated_at),  # get_note_by_id
            (1,),  # delete_note
        ]

        result = job_note_service.delete_note(1, 1)

        assert result is True
        # Verify delete query was called
        assert mock_cursor.execute.call_count >= 1  # At least once for delete

    def test_delete_note_not_found(self, job_note_service, mock_database):
        """Test delete_note returns False when note not found."""
        mock_cursor = Mock()
        # Override the fixture's __enter__ to return our configured cursor
        mock_database.get_cursor.return_value.__enter__ = Mock(return_value=mock_cursor)

        mock_cursor.description = [
            ("note_id",),
            ("jsearch_job_id",),
            ("user_id",),
            ("note_text",),
            ("created_at",),
            ("updated_at",),
        ]
        # First call (get_note_by_id) returns None, second call (delete) also returns None
        mock_cursor.fetchone.side_effect = [None, None]

        result = job_note_service.delete_note(999, 1)

        assert result is False

    def test_delete_note_handles_exceptions(self, job_note_service, mock_database):
        """Test delete_note handles database exceptions."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            job_note_service.delete_note(1, 1)
