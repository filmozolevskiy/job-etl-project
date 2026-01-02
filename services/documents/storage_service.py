"""File storage abstraction layer for document management."""

import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class StorageService(ABC):
    """Abstract base class for file storage operations.

    This abstraction allows switching between local filesystem and cloud storage
    (e.g., S3) without changing business logic.
    """

    @abstractmethod
    def save_file(self, file_content: bytes, file_path: str) -> str:
        """Save file content to storage.

        Args:
            file_content: Binary file content to save
            file_path: Relative path where file should be stored

        Returns:
            Relative path to the saved file (for database storage)

        Raises:
            IOError: If file cannot be saved
        """
        ...

    @abstractmethod
    def get_file(self, file_path: str) -> bytes:
        """Retrieve file content from storage.

        Args:
            file_path: Relative path to the file

        Returns:
            Binary file content

        Raises:
            FileNotFoundError: If file does not exist
            IOError: If file cannot be read
        """
        ...

    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """Delete file from storage.

        Args:
            file_path: Relative path to the file

        Returns:
            True if file was deleted, False if file did not exist

        Raises:
            IOError: If file cannot be deleted
        """
        ...

    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in storage.

        Args:
            file_path: Relative path to the file

        Returns:
            True if file exists, False otherwise
        """
        ...


class LocalStorageService(StorageService):
    """Local filesystem implementation of storage service.

    Stores files in a local directory structure organized by user and document type.
    """

    def __init__(self, base_dir: str = "uploads"):
        """Initialize local storage service.

        Args:
            base_dir: Base directory for file storage (default: "uploads")
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent directory traversal and special characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for filesystem use
        """
        # Remove path components
        filename = Path(filename).name
        # Remove or replace unsafe characters
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        # Remove leading/trailing dots and spaces
        filename = filename.strip(". ")
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext
        return filename or "file"

    def _get_full_path(self, relative_path: str) -> Path:
        """Convert relative path to full filesystem path.

        Args:
            relative_path: Relative path from base directory

        Returns:
            Full Path object

        Raises:
            ValueError: If path attempts directory traversal
        """
        # Normalize path and check for directory traversal
        full_path = (self.base_dir / relative_path).resolve()
        base_resolved = self.base_dir.resolve()
        if not str(full_path).startswith(str(base_resolved)):
            raise ValueError("Invalid path: directory traversal detected")
        return full_path

    def save_file(self, file_content: bytes, file_path: str) -> str:
        """Save file content to local filesystem.

        Args:
            file_content: Binary file content to save
            file_path: Relative path where file should be stored

        Returns:
            Relative path to the saved file

        Raises:
            IOError: If file cannot be saved
            ValueError: If path is invalid
        """
        full_path = self._get_full_path(file_path)
        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            full_path.write_bytes(file_content)
            logger.debug(f"Saved file to {full_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to save file to {full_path}: {e}")
            raise OSError(f"Failed to save file: {e}") from e

    def get_file(self, file_path: str) -> bytes:
        """Retrieve file content from local filesystem.

        Args:
            file_path: Relative path to the file

        Returns:
            Binary file content

        Raises:
            FileNotFoundError: If file does not exist
            IOError: If file cannot be read
        """
        full_path = self._get_full_path(file_path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        try:
            return full_path.read_bytes()
        except Exception as e:
            logger.error(f"Failed to read file {full_path}: {e}")
            raise OSError(f"Failed to read file: {e}") from e

    def delete_file(self, file_path: str) -> bool:
        """Delete file from local filesystem.

        Args:
            file_path: Relative path to the file

        Returns:
            True if file was deleted, False if file did not exist

        Raises:
            IOError: If file cannot be deleted
        """
        full_path = self._get_full_path(file_path)
        if not full_path.exists():
            return False
        try:
            full_path.unlink()
            logger.debug(f"Deleted file {full_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {full_path}: {e}")
            raise OSError(f"Failed to delete file: {e}") from e

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in local filesystem.

        Args:
            file_path: Relative path to the file

        Returns:
            True if file exists, False otherwise
        """
        try:
            full_path = self._get_full_path(file_path)
            return full_path.exists()
        except ValueError:
            return False

    def get_user_directory(self, user_id: int, document_type: str) -> Path:
        """Get directory path for a user's document type.

        Args:
            user_id: User ID
            document_type: Type of document (e.g., "resumes", "cover_letters")

        Returns:
            Path object for the user's document directory
        """
        return self.base_dir / document_type / str(user_id)

