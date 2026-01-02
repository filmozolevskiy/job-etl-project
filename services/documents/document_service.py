"""Service for linking documents to job applications."""

from __future__ import annotations

import logging
from typing import Any

from shared.database import Database

from .queries import (
    DELETE_JOB_APPLICATION_DOCUMENT,
    GET_JOB_APPLICATION_DOCUMENT,
    UPDATE_JOB_APPLICATION_DOCUMENT,
    UPSERT_JOB_APPLICATION_DOCUMENT,
)

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for managing job application document links."""

    def __init__(self, database: Database):
        """Initialize the document service.

        Args:
            database: Database connection interface
        """
        if not database:
            raise ValueError("Database is required")
        self.db = database

    def link_documents_to_job(
        self,
        jsearch_job_id: str,
        user_id: int,
        resume_id: int | None = None,
        cover_letter_id: int | None = None,
        cover_letter_text: str | None = None,
        user_notes: str | None = None,
    ) -> dict[str, Any]:
        """Link documents to a job application (upsert).

        Args:
            jsearch_job_id: Job ID
            user_id: User ID
            resume_id: Resume ID to link
            cover_letter_id: Cover letter ID to link
            cover_letter_text: Inline cover letter text (alternative to cover_letter_id)
            user_notes: User notes for this job application

        Returns:
            Dictionary with job application document data

        Note:
            - If both cover_letter_id and cover_letter_text are provided, cover_letter_id takes precedence
            - This is an upsert operation - it will create or update the document record
        """
        with self.db.get_cursor() as cur:
            cur.execute(
                UPSERT_JOB_APPLICATION_DOCUMENT,
                (
                    jsearch_job_id,
                    user_id,
                    resume_id,
                    cover_letter_id,
                    cover_letter_text,
                    user_notes,
                ),
            )
            result = cur.fetchone()
            if not result:
                raise ValueError("Failed to link documents to job")

            if cur.description is None:
                raise ValueError("No description available from cursor")
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                raise ValueError(f"Invalid cursor description: {e}") from e
            document_data = dict(zip(columns, result))
            logger.info(f"Linked documents to job {jsearch_job_id} for user {user_id}")
            return document_data

    def get_job_application_document(
        self, jsearch_job_id: str, user_id: int
    ) -> dict[str, Any] | None:
        """Get job application document for a job and user.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID

        Returns:
            Dictionary with document data including linked resume and cover letter info,
            or None if not found
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_JOB_APPLICATION_DOCUMENT, (jsearch_job_id, user_id))
            result = cur.fetchone()
            if not result:
                return None

            if cur.description is None:
                return None
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                logger.warning(f"Invalid cursor description in get_job_application_document: {e}")
                return None
            return dict(zip(columns, result))

    def update_job_application_document(
        self,
        document_id: int,
        user_id: int,
        resume_id: int | None = None,
        cover_letter_id: int | None = None,
        cover_letter_text: str | None = None,
        user_notes: str | None = None,
    ) -> dict[str, Any]:
        """Update job application document.

        Args:
            document_id: Document ID
            user_id: User ID (for ownership validation)
            resume_id: Optional new resume ID to link
            cover_letter_id: Optional new cover letter ID to link
            cover_letter_text: Optional new inline cover letter text
            user_notes: Optional new user notes

        Returns:
            Updated document dictionary

        Raises:
            ValueError: If document not found or user doesn't own it

        Note:
            - Only provided fields will be updated (None values are ignored)
            - If both cover_letter_id and cover_letter_text are provided, cover_letter_id takes precedence
        """
        with self.db.get_cursor() as cur:
            cur.execute(
                UPDATE_JOB_APPLICATION_DOCUMENT,
                (
                    resume_id,
                    cover_letter_id,
                    cover_letter_text,
                    user_notes,
                    document_id,
                    user_id,
                ),
            )
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Document {document_id} not found or access denied")

            columns = [desc[0] for desc in cur.description]
            logger.info(f"Updated job application document {document_id} for user {user_id}")
            return dict(zip(columns, result))

    def delete_job_application_document(self, document_id: int, user_id: int) -> bool:
        """Delete job application document.

        Args:
            document_id: Document ID
            user_id: User ID (for ownership validation)

        Returns:
            True if deleted, False if not found

        Note:
            This only deletes the link record, not the actual resume or cover letter files
        """
        with self.db.get_cursor() as cur:
            cur.execute(DELETE_JOB_APPLICATION_DOCUMENT, (document_id, user_id))
            result = cur.fetchone()
            if not result:
                return False

            logger.info(f"Deleted job application document {document_id} for user {user_id}")
            return True
