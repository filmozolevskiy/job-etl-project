"""User management service for authentication."""

import logging
from typing import Any

import bcrypt
from shared.database import Database

from .queries import (
    GET_USER_BY_EMAIL,
    GET_USER_BY_ID,
    GET_USER_BY_USERNAME,
    INSERT_USER,
    UPDATE_USER_LAST_LOGIN,
)

logger = logging.getLogger(__name__)


class UserService:
    """Service for user management and authentication."""

    def __init__(self, database: Database):
        """Initialize the user service.

        Args:
            database: Database connection interface
        """
        if not database:
            raise ValueError("Database is required")
        self.db = database

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "user",
    ) -> int:
        """Create a new user account.

        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password (will be hashed)
            role: User role ('user' or 'admin'), defaults to 'user'

        Returns:
            User ID of the created user

        Raises:
            ValueError: If username or email already exists, or if validation fails
        """
        if not username or not username.strip():
            raise ValueError("Username is required")
        if not email or not email.strip():
            raise ValueError("Email is required")
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        if role not in ("user", "admin"):
            raise ValueError("Role must be 'user' or 'admin'")

        # Check if username or email already exists
        existing_user = self.get_user_by_username(username.strip())
        if existing_user:
            raise ValueError(f"Username '{username}' already exists")

        existing_user = self.get_user_by_email(email.strip())
        if existing_user:
            raise ValueError(f"Email '{email}' already exists")

        # Hash password
        password_hash = self._hash_password(password)

        # Insert user
        try:
            with self.db.get_cursor() as cur:
                cur.execute(
                    INSERT_USER,
                    (username.strip(), email.strip().lower(), password_hash, role),
                )
                result = cur.fetchone()
                if result:
                    user_id = result[0]
                    logger.info(f"Created user: {username} (ID: {user_id})")
                    return user_id
                else:
                    raise ValueError("Failed to create user")
        except Exception as e:
            logger.error(f"Error creating user {username}: {e}", exc_info=True)
            raise

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Get user by username.

        Args:
            username: Username to lookup

        Returns:
            User dictionary or None if not found
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_USER_BY_USERNAME, (username.strip(),))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                return None

            return dict(zip(columns, row))

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Get user by email.

        Args:
            email: Email address to lookup

        Returns:
            User dictionary or None if not found
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_USER_BY_EMAIL, (email.strip().lower(),))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                return None

            return dict(zip(columns, row))

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Get user by ID.

        Args:
            user_id: User ID to lookup

        Returns:
            User dictionary or None if not found
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_USER_BY_ID, (user_id,))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                return None

            return dict(zip(columns, row))

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against a hash.

        Args:
            password: Plain text password
            password_hash: Bcrypt password hash

        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception as e:
            logger.error(f"Error verifying password: {e}", exc_info=True)
            return False

    def update_last_login(self, user_id: int) -> None:
        """Update user's last login timestamp.

        Args:
            user_id: User ID to update
        """
        try:
            with self.db.get_cursor() as cur:
                cur.execute(UPDATE_USER_LAST_LOGIN, (user_id,))
        except Exception as e:
            logger.error(f"Error updating last login for user {user_id}: {e}", exc_info=True)
            raise

    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Bcrypt password hash
        """
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
