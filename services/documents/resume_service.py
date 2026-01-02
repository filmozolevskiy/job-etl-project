"""Service for managing user resumes."""

from __future__ import annotations

import logging
import mimetypes
import os
from typing import Any

from shared.database import Database
from werkzeug.datastructures import FileStorage

from .queries import (
    DELETE_RESUME,
    GET_RESUME_BY_ID,
    GET_USER_RESUMES,
    INSERT_RESUME,
    UPDATE_RESUME,
    UPDATE_RESUME_DOCUMENTS_SECTION,
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
ERROR_RESUME_NOT_FOUND = "Resume not found"
ERROR_RESUME_FILE_NOT_FOUND = "Resume file not found: {path}"
ERROR_FAILED_TO_SAVE_RESUME = "Failed to save resume file: {error}"
ERROR_FAILED_TO_READ_RESUME = "Failed to read resume file: {error}"


class ResumeValidationError(Exception):
    """Raised when resume validation fails."""

    pass


class ResumeService:
    """Service for managing user resume uploads and storage."""

    def __init__(
        self,
        database: Database,
        storage_service: StorageService | None = None,
        max_file_size: int = 5 * 1024 * 1024,  # 5 MB default
        allowed_extensions: list[str] | None = None,
    ):
        """Initialize the resume service.

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
            ResumeValidationError: If file validation fails
        """
        if not file or not file.filename:
            raise ResumeValidationError("No file provided")

        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer

        if file_size > self.max_file_size:
            raise ResumeValidationError(
                ERROR_FILE_SIZE_EXCEEDED.format(size=file_size, max_size=self.max_file_size)
            )

        if file_size == 0:
            raise ResumeValidationError("File is empty")

        # Check file extension
        filename = file.filename.lower()
        file_ext = filename.rsplit(".", 1)[-1] if "." in filename else ""

        if file_ext not in self.allowed_extensions:
            raise ResumeValidationError(
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
                "application/zip",  # DOCX files are ZIP archives
            ],
        }

        if file_ext in allowed_mimes:
            if mime_type not in allowed_mimes[file_ext]:
                # For DOCX, also check file content (magic bytes)
                if file_ext == "docx":
                    file.seek(0)
                    header = file.read(4)
                    file.seek(0)
                    # DOCX files start with PK (ZIP signature)
                    if header[:2] != b"PK":
                        raise ResumeValidationError("Invalid DOCX file format")
                else:
                    logger.warning(
                        f"MIME type '{mime_type}' doesn't match expected for {file_ext}, "
                        f"but allowing based on extension"
                    )

        return file_ext, mime_type or "application/octet-stream"

    def upload_resume(
        self,
        user_id: int,
        file: FileStorage,
        resume_name: str | None = None,
        in_documents_section: bool = False,
    ) -> dict[str, Any]:
        """Upload a resume file.

        Args:
            user_id: User ID who owns the resume
            file: FileStorage object from Flask request
            resume_name: Optional name for the resume (defaults to filename)
            in_documents_section: Whether this resume is in the documents section

        Returns:
            Dictionary with resume record data

        Raises:
            ResumeValidationError: If file validation fails
            IOError: If file cannot be saved
        """
        # Validate file
        file_ext, mime_type = self._validate_file(file)

        # Generate resume name if not provided
        if not resume_name:
            resume_name = file.filename or "resume"

        # Read file content
        file.seek(0)
        file_content = file.read()
        file_size = len(file_content)

        # Generate file path
        self.storage.get_user_directory(user_id, "resumes")  # Ensure directory exists
        sanitized_filename = self.storage._sanitize_filename(file.filename or "resume")
        # We'll use the resume_id in the filename after insertion
        temp_file_path = f"resumes/{user_id}/{sanitized_filename}"

        # Insert database record first (to get resume_id)
        with self.db.get_cursor() as cur:
            cur.execute(
                INSERT_RESUME,
                (user_id, resume_name, temp_file_path, file_size, mime_type, in_documents_section),
            )
            result = cur.fetchone()
            if not result:
                raise ValueError("Failed to create resume record")

            if cur.description is None:
                raise ValueError("No description available from cursor")
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                raise ValueError(f"Invalid cursor description: {e}") from e
            resume_data = dict(zip(columns, result))
            resume_id = resume_data["resume_id"]

        # Update file path with resume_id
        final_filename = f"{resume_id}_{sanitized_filename}"
        final_file_path = f"resumes/{user_id}/{final_filename}"

        # Save file
        try:
            self.storage.save_file(file_content, final_file_path)

            # Update database with final file path
            with self.db.get_cursor() as cur:
                cur.execute(
                    UPDATE_RESUME,
                    (resume_name, resume_id, user_id),
                )
                # Also update file_path directly
                cur.execute(
                    "UPDATE marts.user_resumes SET file_path = %s WHERE resume_id = %s",
                    (final_file_path, resume_id),
                )

            logger.info(f"Uploaded resume {resume_id} for user {user_id}")
            resume_data["file_path"] = final_file_path
            return resume_data

        except Exception as e:
            # Rollback: delete database record if file save fails
            logger.error(ERROR_FAILED_TO_SAVE_RESUME.format(error=e))
            try:
                with self.db.get_cursor() as cur:
                    cur.execute(DELETE_RESUME, (resume_id, user_id))
            except Exception as rollback_error:
                logger.error(f"Failed to rollback resume record: {rollback_error}")
            raise OSError(ERROR_FAILED_TO_SAVE_RESUME.format(error=e)) from e

    def get_user_resumes(
        self, user_id: int, in_documents_section: bool | None = None
    ) -> list[dict[str, Any]]:
        """Get all resumes for a user.

        Args:
            user_id: User ID
            in_documents_section: If True, only return resumes in documents section.
                                 If False, only return resumes not in documents section.
                                 If None, return all resumes.

        Returns:
            List of resume dictionaries
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_USER_RESUMES, (user_id, in_documents_section, in_documents_section))
            if cur.description is None:
                return []
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                logger.warning(f"Invalid cursor description in get_user_resumes: {e}")
                return []
            resumes = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.debug(f"Retrieved {len(resumes)} resume(s) for user {user_id}")
        return resumes

    def get_resume_by_id(self, resume_id: int, user_id: int) -> dict[str, Any]:
        """Get a resume by ID (with user validation).

        Args:
            resume_id: Resume ID
            user_id: User ID (for ownership validation)

        Returns:
            Resume dictionary

        Raises:
            ValueError: If resume not found or user doesn't own it
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_RESUME_BY_ID, (resume_id, user_id))
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Resume {resume_id} not found or access denied")

            if cur.description is None:
                raise ValueError("No description available from cursor")
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                raise ValueError(f"Invalid cursor description: {e}") from e
            return dict(zip(columns, result))

    def update_resume(self, resume_id: int, user_id: int, resume_name: str) -> dict[str, Any]:
        """Update resume name.

        Args:
            resume_id: Resume ID
            user_id: User ID (for ownership validation)
            resume_name: New resume name

        Returns:
            Updated resume dictionary

        Raises:
            ValueError: If resume not found or user doesn't own it
        """
        with self.db.get_cursor() as cur:
            cur.execute(UPDATE_RESUME, (resume_name, resume_id, user_id))
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Resume {resume_id} not found or access denied")

            if cur.description is None:
                raise ValueError("No description available from cursor")
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                raise ValueError(f"Invalid cursor description: {e}") from e
            logger.info(f"Updated resume {resume_id} for user {user_id}")
            return dict(zip(columns, result))

    def delete_resume(self, resume_id: int, user_id: int) -> bool:
        """Delete a resume and its file.

        Args:
            resume_id: Resume ID
            user_id: User ID (for ownership validation)

        Returns:
            True if deleted, False if not found

        Raises:
            IOError: If file cannot be deleted
        """
        # Get resume record to get file path
        try:
            resume = self.get_resume_by_id(resume_id, user_id)
            file_path = resume["file_path"]
        except ValueError:
            return False

        # Delete database record
        with self.db.get_cursor() as cur:
            cur.execute(DELETE_RESUME, (resume_id, user_id))
            result = cur.fetchone()
            if not result:
                return False

        # Delete file
        try:
            self.storage.delete_file(file_path)
            logger.info(f"Deleted resume {resume_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete resume file {file_path}: {e}")
            # File deletion failed, but record is deleted - log warning
            logger.warning(f"Resume record deleted but file may still exist: {file_path}")
            raise OSError(f"Failed to delete resume file: {e}") from e

    def download_resume(self, resume_id: int, user_id: int) -> tuple[bytes, str, str]:
        """Download resume file content.

        Args:
            resume_id: Resume ID
            user_id: User ID (for ownership validation)

        Returns:
            Tuple of (file_content, filename, mime_type)

        Raises:
            ValueError: If resume not found or user doesn't own it
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        resume = self.get_resume_by_id(resume_id, user_id)
        file_path = resume["file_path"]

        try:
            file_content = self.storage.get_file(file_path)
            filename = resume["resume_name"] + (
                f".{file_path.rsplit('.', 1)[-1]}" if "." in file_path else ""
            )
            mime_type = resume["file_type"]
            return file_content, filename, mime_type
        except FileNotFoundError:
            logger.error(ERROR_RESUME_FILE_NOT_FOUND.format(path=file_path))
            raise
        except Exception as e:
            logger.error(ERROR_FAILED_TO_READ_RESUME.format(error=e))
            raise OSError(ERROR_FAILED_TO_READ_RESUME.format(error=e)) from e

    def set_in_documents_section(
        self, resume_id: int, user_id: int, in_documents_section: bool
    ) -> dict[str, Any]:
        """Set the in_documents_section flag for a resume.

        Args:
            resume_id: Resume ID
            user_id: User ID (for ownership validation)
            in_documents_section: Whether the resume should be in documents section

        Returns:
            Updated resume dictionary

        Raises:
            ValueError: If resume not found or user doesn't own it
        """
        with self.db.get_cursor() as cur:
            cur.execute(UPDATE_RESUME_DOCUMENTS_SECTION, (in_documents_section, resume_id, user_id))
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Resume {resume_id} not found or access denied")

            if cur.description is None:
                raise ValueError("No description available from cursor")
            try:
                columns = [desc[0] for desc in cur.description]
            except (TypeError, IndexError) as e:
                raise ValueError(f"Invalid cursor description: {e}") from e
            logger.info(
                f"Updated resume {resume_id} in_documents_section to "
                f"{in_documents_section} for user {user_id}"
            )
            return dict(zip(columns, result))
