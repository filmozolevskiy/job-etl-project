"""Service for managing user cover letters."""

from __future__ import annotations

import logging
import mimetypes
import os
from typing import Any

from shared.database import Database
from werkzeug.datastructures import FileStorage

from .queries import (
    DELETE_COVER_LETTER,
    GET_COVER_LETTER_BY_ID,
    GET_COVER_LETTER_GENERATION_HISTORY,
    GET_USER_COVER_LETTERS,
    INSERT_COVER_LETTER,
    UPDATE_COVER_LETTER,
    UPDATE_COVER_LETTER_DOCUMENTS_SECTION,
)
from .storage_service import LocalStorageService, StorageService

logger = logging.getLogger(__name__)

# Error messages
ERROR_FILE_SIZE_EXCEEDED = (
    "File size ({size} bytes) exceeds maximum allowed size ({max_size} bytes)"
)
ERROR_FILE_EXTENSION_NOT_ALLOWED = (  # noqa: E501
    "File extension '{ext}' not allowed. Allowed extensions: {allowed}"
)
ERROR_COVER_LETTER_NOT_FOUND = "Cover letter not found"
ERROR_COVER_LETTER_FILE_NOT_FOUND = "Cover letter file not found: {path}"
ERROR_FAILED_TO_SAVE_COVER_LETTER = "Failed to save cover letter file: {error}"
ERROR_FAILED_TO_READ_COVER_LETTER = "Failed to read cover letter file: {error}"
ERROR_TEXT_BASED_NOT_DOWNLOADABLE = "Cover letter is text-based, not file-based"


class CoverLetterValidationError(Exception):
    """Raised when cover letter validation fails."""

    pass


class CoverLetterService:
    """Service for managing user cover letters (text-based and file-based)."""

    def __init__(
        self,
        database: Database,
        storage_service: StorageService | None = None,
        max_file_size: int = 5 * 1024 * 1024,  # 5 MB default
        allowed_extensions: list[str] | None = None,
    ):
        """Initialize the cover letter service.

        Args:
            database: Database connection interface
            storage_service: Storage service for file operations (defaults to LocalStorageService)
            max_file_size: Maximum file size in bytes (default: 5 MB)
            allowed_extensions: List of allowed file extensions (default: ['pdf', 'docx'])
        """
        if not database:
            raise ValueError("Database is required")
        self.db = database
        self.storage = storage_service or LocalStorageService()
        self.max_file_size = max_file_size
        self.allowed_extensions = allowed_extensions or ["pdf", "docx"]

    def _validate_file(self, file: FileStorage) -> tuple[str, str]:
        """Validate uploaded file.

        Args:
            file: FileStorage object from Flask request

        Returns:
            Tuple of (file_extension, mime_type)

        Raises:
            CoverLetterValidationError: If file validation fails
        """
        if not file or not file.filename:
            raise CoverLetterValidationError("No file provided")

        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer

        if file_size > self.max_file_size:
            raise CoverLetterValidationError(
                ERROR_FILE_SIZE_EXCEEDED.format(size=file_size, max_size=self.max_file_size)
            )

        if file_size == 0:
            raise CoverLetterValidationError("File is empty")

        # Check file extension
        filename = file.filename.lower()
        file_ext = filename.rsplit(".", 1)[-1] if "." in filename else ""

        if file_ext not in self.allowed_extensions:
            raise CoverLetterValidationError(
                ERROR_FILE_EXTENSION_NOT_ALLOWED.format(
                    ext=file_ext, allowed=", ".join(self.allowed_extensions)
                )
            )

        # Check MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        allowed_mimes = {
            "pdf": ["application/pdf"],
            "docx": [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/zip",
            ],
        }

        if file_ext in allowed_mimes:
            if mime_type not in allowed_mimes[file_ext]:
                # For DOCX, also check file content (magic bytes)
                if file_ext == "docx":
                    file.seek(0)
                    header = file.read(4)
                    file.seek(0)
                    if header[:2] != b"PK":
                        raise CoverLetterValidationError("Invalid DOCX file format")

        return file_ext, mime_type or "application/octet-stream"

    def create_cover_letter(
        self,
        user_id: int,
        cover_letter_name: str,
        cover_letter_text: str | None = None,
        jsearch_job_id: str | None = None,
        file_path: str | None = None,
        is_generated: bool = False,
        generation_prompt: str | None = None,
        in_documents_section: bool = False,
    ) -> dict[str, Any]:
        """Create a text-based cover letter.

        Args:
            user_id: User ID who owns the cover letter
            cover_letter_name: Name for the cover letter
            cover_letter_text: Text content of the cover letter
            jsearch_job_id: Optional job ID if this is job-specific
            file_path: Optional file path if this is file-based
            is_generated: Whether this was AI-generated
            generation_prompt: Optional prompt used for AI generation
            in_documents_section: Whether this cover letter is in the documents section

        Returns:
            Dictionary with cover letter record data
        """
        if not cover_letter_text and not file_path:
            raise ValueError("Either cover_letter_text or file_path must be provided")

        with self.db.get_cursor() as cur:
            cur.execute(
                INSERT_COVER_LETTER,
                (
                    user_id,
                    jsearch_job_id,
                    cover_letter_name,
                    cover_letter_text,
                    file_path,
                    is_generated,
                    generation_prompt,
                    in_documents_section,
                ),
            )
            result = cur.fetchone()
            if not result:
                raise ValueError("Failed to create cover letter record")

            if cur.description is None:
                raise ValueError("No description available from cursor")
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                raise ValueError(f"Invalid cursor description: {e}") from e
            cover_letter_data = dict(zip(columns, result))
            logger.info(
                f"Created cover letter {cover_letter_data['cover_letter_id']} for user {user_id}"
            )
            return cover_letter_data

    def upload_cover_letter_file(
        self,
        user_id: int,
        file: FileStorage,
        cover_letter_name: str | None = None,
        jsearch_job_id: str | None = None,
        in_documents_section: bool = False,
    ) -> dict[str, Any]:
        """Upload a cover letter file.

        Args:
            user_id: User ID who owns the cover letter
            file: FileStorage object from Flask request
            cover_letter_name: Optional name for the cover letter (defaults to filename)
            jsearch_job_id: Optional job ID if this is job-specific
            in_documents_section: Whether this cover letter is in the documents section

        Returns:
            Dictionary with cover letter record data

        Raises:
            CoverLetterValidationError: If file validation fails
            IOError: If file cannot be saved
        """
        # Validate file
        file_ext, mime_type = self._validate_file(file)

        # Generate cover letter name if not provided
        if not cover_letter_name:
            cover_letter_name = file.filename or "cover_letter"

        # Read file content
        file.seek(0)
        file_content = file.read()

        # Generate file path
        self.storage.get_user_directory(user_id, "cover_letters")  # Ensure directory exists
        sanitized_filename = self.storage._sanitize_filename(file.filename or "cover_letter")
        temp_file_path = f"cover_letters/{user_id}/{sanitized_filename}"

        # Insert database record first (to get cover_letter_id)
        with self.db.get_cursor() as cur:
            cur.execute(
                INSERT_COVER_LETTER,
                (
                    user_id,
                    jsearch_job_id,
                    cover_letter_name,
                    None,  # cover_letter_text
                    temp_file_path,
                    False,  # is_generated
                    None,  # generation_prompt
                    in_documents_section,
                ),
            )
            result = cur.fetchone()
            if not result:
                raise ValueError("Failed to create cover letter record")

            if cur.description is None:
                raise ValueError("No description available from cursor")
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                raise ValueError(f"Invalid cursor description: {e}") from e
            cover_letter_data = dict(zip(columns, result))
            cover_letter_id = cover_letter_data["cover_letter_id"]

        # Update file path with cover_letter_id
        final_filename = f"{cover_letter_id}_{sanitized_filename}"
        final_file_path = f"cover_letters/{user_id}/{final_filename}"

        # Save file
        try:
            self.storage.save_file(file_content, final_file_path)

            # Update database with final file path
            with self.db.get_cursor() as cur:
                cur.execute(
                    "UPDATE marts.user_cover_letters SET file_path = %s WHERE cover_letter_id = %s",
                    (final_file_path, cover_letter_id),
                )

            logger.info(f"Uploaded cover letter {cover_letter_id} for user {user_id}")
            cover_letter_data["file_path"] = final_file_path
            return cover_letter_data

        except Exception as e:
            # Rollback: delete database record if file save fails
            logger.error(ERROR_FAILED_TO_SAVE_COVER_LETTER.format(error=e))
            try:
                with self.db.get_cursor() as cur:
                    cur.execute(DELETE_COVER_LETTER, (cover_letter_id, user_id))
            except Exception as rollback_error:
                logger.error(f"Failed to rollback cover letter record: {rollback_error}")
            raise OSError(ERROR_FAILED_TO_SAVE_COVER_LETTER.format(error=e)) from e

    def get_user_cover_letters(
        self,
        user_id: int,
        jsearch_job_id: str | None = None,
        in_documents_section: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Get all cover letters for a user (optionally filtered by job and in_documents_section).

        Args:
            user_id: User ID
            jsearch_job_id: Optional job ID to filter by
            in_documents_section: If True, only return cover letters in documents section.
                                 If False, only return cover letters not in documents section.
                                 If None, return all cover letters.

        Returns:
            List of cover letter dictionaries
        """
        with self.db.get_cursor() as cur:
            cur.execute(
                GET_USER_COVER_LETTERS,
                (
                    user_id,
                    jsearch_job_id,
                    jsearch_job_id,
                    in_documents_section,
                    in_documents_section,
                ),
            )
            if cur.description is None:
                return []
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                logger.warning(f"Invalid cursor description in get_user_cover_letters: {e}")
                return []
            cover_letters = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.debug(f"Retrieved {len(cover_letters)} cover letter(s) for user {user_id}")
        return cover_letters

    def get_generation_history(
        self, user_id: int, jsearch_job_id: str
    ) -> list[dict[str, Any]]:
        """Get generation history (all generated cover letters) for a job.

        Args:
            user_id: User ID
            jsearch_job_id: Job ID to get generation history for

        Returns:
            List of generated cover letter dictionaries, ordered by created_at DESC
        """
        with self.db.get_cursor() as cur:
            cur.execute(
                GET_COVER_LETTER_GENERATION_HISTORY,
                (user_id, jsearch_job_id),
            )
            if cur.description is None:
                return []
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                logger.warning(f"Invalid cursor description in get_generation_history: {e}")
                return []
            cover_letters = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.debug(
            f"Retrieved {len(cover_letters)} generated cover letter(s) for job {jsearch_job_id}"
        )
        return cover_letters

    def get_cover_letter_by_id(self, cover_letter_id: int, user_id: int) -> dict[str, Any]:
        """Get a cover letter by ID (with user validation).

        Args:
            cover_letter_id: Cover letter ID
            user_id: User ID (for ownership validation)

        Returns:
            Cover letter dictionary

        Raises:
            ValueError: If cover letter not found or user doesn't own it
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_COVER_LETTER_BY_ID, (cover_letter_id, user_id))
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Cover letter {cover_letter_id} not found or access denied")

            if cur.description is None:
                raise ValueError("No description available from cursor")
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                raise ValueError(f"Invalid cursor description: {e}") from e
            return dict(zip(columns, result))

    def update_cover_letter(
        self,
        cover_letter_id: int,
        user_id: int,
        cover_letter_name: str | None = None,
        cover_letter_text: str | None = None,
        file_path: str | None = None,
    ) -> dict[str, Any]:
        """Update cover letter.

        Args:
            cover_letter_id: Cover letter ID
            user_id: User ID (for ownership validation)
            cover_letter_name: Optional new name
            cover_letter_text: Optional new text content
            file_path: Optional new file path

        Returns:
            Updated cover letter dictionary

        Raises:
            ValueError: If cover letter not found or user doesn't own it
        """
        with self.db.get_cursor() as cur:
            cur.execute(
                UPDATE_COVER_LETTER,
                (cover_letter_name, cover_letter_text, file_path, cover_letter_id, user_id),
            )
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Cover letter {cover_letter_id} not found or access denied")

            if cur.description is None:
                raise ValueError("No description available from cursor")
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                raise ValueError(f"Invalid cursor description: {e}") from e
            logger.info(f"Updated cover letter {cover_letter_id} for user {user_id}")
            return dict(zip(columns, result))

    def delete_cover_letter(self, cover_letter_id: int, user_id: int) -> bool:
        """Delete a cover letter and its file (if file-based).

        Args:
            cover_letter_id: Cover letter ID
            user_id: User ID (for ownership validation)

        Returns:
            True if deleted, False if not found

        Raises:
            IOError: If file cannot be deleted
        """
        # Get cover letter record to get file path
        try:
            cover_letter = self.get_cover_letter_by_id(cover_letter_id, user_id)
            file_path = cover_letter.get("file_path")
        except ValueError:
            return False

        # Delete database record
        with self.db.get_cursor() as cur:
            cur.execute(DELETE_COVER_LETTER, (cover_letter_id, user_id))
            result = cur.fetchone()
            if not result:
                return False

        # Delete file if it exists
        if file_path:
            try:
                self.storage.delete_file(file_path)
                logger.info(f"Deleted cover letter {cover_letter_id} for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to delete cover letter file {file_path}: {e}")
                logger.warning(f"Cover letter record deleted but file may still exist: {file_path}")
                raise OSError(f"Failed to delete cover letter file: {e}") from e
        else:
            logger.info(f"Deleted text-based cover letter {cover_letter_id} for user {user_id}")

        return True

    def download_cover_letter(self, cover_letter_id: int, user_id: int) -> tuple[bytes, str, str]:
        """Download cover letter file content (for file-based cover letters).

        Args:
            cover_letter_id: Cover letter ID
            user_id: User ID (for ownership validation)

        Returns:
            Tuple of (file_content, filename, mime_type)

        Raises:
            ValueError: If cover letter not found, user doesn't own it, or is text-based
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        cover_letter = self.get_cover_letter_by_id(cover_letter_id, user_id)
        file_path = cover_letter.get("file_path")

        if not file_path:
            raise ValueError(ERROR_TEXT_BASED_NOT_DOWNLOADABLE)

        try:
            file_content = self.storage.get_file(file_path)
            filename = cover_letter["cover_letter_name"] + (
                f".{file_path.rsplit('.', 1)[-1]}" if "." in file_path else ""
            )
            mime_type, _ = mimetypes.guess_type(file_path)
            return file_content, filename, mime_type or "application/octet-stream"
        except FileNotFoundError:
            logger.error(ERROR_COVER_LETTER_FILE_NOT_FOUND.format(path=file_path))
            raise
        except Exception as e:
            logger.error(ERROR_FAILED_TO_READ_COVER_LETTER.format(error=e))
            raise OSError(ERROR_FAILED_TO_READ_COVER_LETTER.format(error=e)) from e

    def set_in_documents_section(
        self, cover_letter_id: int, user_id: int, in_documents_section: bool
    ) -> dict[str, Any]:
        """Set the in_documents_section flag for a cover letter.

        Args:
            cover_letter_id: Cover letter ID
            user_id: User ID (for ownership validation)
            in_documents_section: Whether the cover letter should be in documents section

        Returns:
            Updated cover letter dictionary

        Raises:
            ValueError: If cover letter not found or user doesn't own it
        """
        with self.db.get_cursor() as cur:
            cur.execute(
                UPDATE_COVER_LETTER_DOCUMENTS_SECTION,
                (in_documents_section, cover_letter_id, user_id),
            )
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Cover letter {cover_letter_id} not found or access denied")

            if cur.description is None:
                raise ValueError("No description available from cursor")
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                raise ValueError(f"Invalid cursor description: {e}") from e
            logger.info(
                f"Updated cover letter {cover_letter_id} "
                f"in_documents_section to {in_documents_section} for user {user_id}"
            )
            return dict(zip(columns, result))
