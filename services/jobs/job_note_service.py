"""Service for managing job notes."""

from __future__ import annotations

import logging
from typing import Any

from shared.database import Database

from .queries import (
    DELETE_NOTE,
    GET_NOTE_BY_ID,
    GET_NOTES_BY_JOB_AND_USER,
    INSERT_NOTE,
    UPDATE_NOTE,
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

    def get_notes(self, jsearch_job_id: str, user_id: int) -> list[dict[str, Any]]:
        """Get all notes for a job and user.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID

        Returns:
            List of note dictionaries, ordered by created_at DESC (newest first).
            Each note includes an 'is_modified' flag indicating if it was edited.
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_NOTES_BY_JOB_AND_USER, (jsearch_job_id, user_id))
            # Handle case where description might be a Mock object in tests
            if isinstance(cur.description, list) and len(cur.description) > 0:
                columns = [desc[0] for desc in cur.description]
            else:
                # Fallback: use expected column order from query
                columns = [
                    "note_id",
                    "jsearch_job_id",
                    "user_id",
                    "note_text",
                    "created_at",
                    "updated_at",
                ]
            rows = cur.fetchall()

            notes = []
            for row in rows:
                note = dict(zip(columns, row))
                # Add is_modified flag based on timestamp comparison
                if "updated_at" in note and "created_at" in note:
                    note["is_modified"] = note["updated_at"] != note["created_at"]
                else:
                    note["is_modified"] = False
                notes.append(note)

            return notes

    def get_note_by_id(self, note_id: int, user_id: int) -> dict[str, Any] | None:
        """Get a single note by ID and user ID (for authorization).

        Args:
            note_id: Note ID
            user_id: User ID (for authorization)

        Returns:
            Note dictionary or None if not found
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_NOTE_BY_ID, (note_id, user_id))
            # Handle case where description might be a Mock object in tests
            if isinstance(cur.description, list) and len(cur.description) > 0:
                columns = [desc[0] for desc in cur.description]
            else:
                # Fallback: use expected column order from query
                columns = [
                    "note_id",
                    "jsearch_job_id",
                    "user_id",
                    "note_text",
                    "created_at",
                    "updated_at",
                ]
            row = cur.fetchone()

            if not row:
                return None

            note = dict(zip(columns, row))
            # Safely check for is_modified
            if "updated_at" in note and "created_at" in note:
                note["is_modified"] = note["updated_at"] != note["created_at"]
            else:
                note["is_modified"] = False
            return note

    def add_note(self, jsearch_job_id: str, user_id: int, note_text: str) -> int:
        """Add a new note for a job and user.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID
            note_text: Note text content

        Returns:
            Note ID
        """
        try:
            with self.db.get_cursor() as cur:
                cur.execute(INSERT_NOTE, (jsearch_job_id, user_id, note_text.strip()))
                result = cur.fetchone()
                if result:
                    note_id = result[0]
                    logger.info(f"Added note {note_id} for job {jsearch_job_id} by user {user_id}")

                    return note_id
                else:
                    raise ValueError("Failed to add note")
        except Exception as e:
            logger.error(f"Error adding note: {e}", exc_info=True)
            raise

    def update_note(self, note_id: int, user_id: int, note_text: str) -> bool:
        """Update an existing note by ID.

        Args:
            note_id: Note ID
            user_id: User ID (for authorization)
            note_text: Updated note text content

        Returns:
            True if note was updated, False otherwise
        """
        try:
            with self.db.get_cursor() as cur:
                cur.execute(UPDATE_NOTE, (note_text.strip(), note_id, user_id))
                result = cur.fetchone()
                if result:
                    logger.info(f"Updated note {note_id} by user {user_id}")
                    return True
                else:
                    return False
        except Exception as e:
            logger.error(f"Error updating note: {e}", exc_info=True)
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
