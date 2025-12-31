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
    UPDATE_USER_PASSWORD,
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

    def update_user_password(self, user_id: int, new_password: str) -> None:
        """Update user's password.

        Args:
            user_id: User ID to update
            new_password: Plain text password (will be hashed)

        Raises:
            ValueError: If password is too short
        """
        if not new_password or len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters")

        password_hash = self._hash_password(new_password)
        logger.info(f"Attempting to update password for user {user_id}")
        try:
            with self.db.get_cursor() as cur:
                # Verify user exists first
                cur.execute(
                    "SELECT user_id, password_hash FROM marts.users WHERE user_id = %s", (user_id,)
                )
                user_row = cur.fetchone()
                if not user_row:
                    raise ValueError(f"User {user_id} not found")
                old_hash = user_row[1]
                logger.debug(f"User {user_id} found, current hash: {old_hash[:20]}...")

                # Update password
                logger.debug(f"Executing UPDATE for user {user_id}")
                cur.execute(UPDATE_USER_PASSWORD, (password_hash, user_id))
                rows_affected = cur.rowcount
                logger.debug(f"UPDATE executed, rows affected: {rows_affected}")

                if rows_affected == 0:
                    raise ValueError(
                        f"Password update failed - no rows affected for user {user_id}"
                    )

                # Immediately verify the update by reading back the hash
                cur.execute("SELECT password_hash FROM marts.users WHERE user_id = %s", (user_id,))
                result = cur.fetchone()
                if not result:
                    raise ValueError(f"Could not retrieve updated password hash for user {user_id}")

                stored_hash = result[0]
                logger.debug(f"Retrieved stored hash: {stored_hash[:20]}...")

                # Verify the new password works with the stored hash
                if not self.verify_password(new_password, stored_hash):
                    logger.error(f"Password verification failed - hash mismatch for user {user_id}")
                    raise ValueError(
                        f"Password update verification failed - new password does not match stored hash for user {user_id}"
                    )

                logger.info(
                    f"Successfully updated password for user {user_id} (rows affected: {rows_affected})"
                )
        except Exception as e:
            logger.error(f"Error updating password for user {user_id}: {e}", exc_info=True)
            raise

    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Bcrypt password hash
        """
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
