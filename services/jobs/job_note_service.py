"""Service for managing job notes."""

import logging
from typing import Any

from shared.database import Database

from .queries import (
    DELETE_NOTE,
    GET_NOTE_BY_JOB_AND_USER,
    UPSERT_NOTE,
)

logger = logging.getLogger(__name__)


class JobNoteService:
    """Service for managing job notes."""

    def __init__(self, database: Database):
        """Initialize the job note service.

        Args:
            database: Database connection interface
        """
        if not database:
            raise ValueError("Database is required")
        self.db = database

    def get_note(self, jsearch_job_id: str, user_id: int) -> dict[str, Any] | None:
        """Get a note for a job and user.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID

        Returns:
            Note dictionary or None if not found
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_NOTE_BY_JOB_AND_USER, (jsearch_job_id, user_id))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                return None

            return dict(zip(columns, row))

    def upsert_note(self, jsearch_job_id: str, user_id: int, note_text: str) -> int:
        """Insert or update a note for a job and user.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID
            note_text: Note text content

        Returns:
            Note ID
        """
        try:
            with self.db.get_cursor() as cur:
                cur.execute(UPSERT_NOTE, (jsearch_job_id, user_id, note_text.strip()))
                result = cur.fetchone()
                if result:
                    note_id = result[0]
                    logger.info(f"Upserted note {note_id} for job {jsearch_job_id} by user {user_id}")
                    return note_id
                else:
                    raise ValueError("Failed to upsert note")
        except Exception as e:
            logger.error(f"Error upserting note: {e}", exc_info=True)
            raise

    def delete_note(self, note_id: int, user_id: int) -> bool:
        """Delete a note.

        Args:
            note_id: Note ID
            user_id: User ID (for authorization)

        Returns:
            True if note was deleted, False otherwise
        """
        try:
            with self.db.get_cursor() as cur:
                cur.execute(DELETE_NOTE, (note_id, user_id))
                result = cur.fetchone()
                if result:
                    logger.info(f"Deleted note {note_id} by user {user_id}")
                    return True
                else:
                    return False
        except Exception as e:
            logger.error(f"Error deleting note: {e}", exc_info=True)
            raise

