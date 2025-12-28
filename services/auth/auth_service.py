"""Authentication service for login/logout operations."""

import logging
from typing import Any

from .user_service import UserService

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication operations."""

    def __init__(self, user_service: UserService):
        """Initialize the auth service.

        Args:
            user_service: UserService instance for user operations
        """
        if not user_service:
            raise ValueError("UserService is required")
        self.user_service = user_service

    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        """Authenticate a user by username and password.

        Args:
            username: Username or email
            password: Plain text password

        Returns:
            User dictionary if authentication succeeds, None otherwise
        """
        if not username or not password:
            return None

        # Try username first, then email
        user = self.user_service.get_user_by_username(username.strip())
        if not user:
            user = self.user_service.get_user_by_email(username.strip())

        if not user:
            logger.warning(f"Authentication failed: user not found: {username}")
            return None

        # Verify password
        if not self.user_service.verify_password(password, user["password_hash"]):
            logger.warning(f"Authentication failed: invalid password for user: {username}")
            return None

        # Update last login
        try:
            self.user_service.update_last_login(user["user_id"])
        except Exception as e:
            logger.error(f"Error updating last login: {e}", exc_info=True)
            # Don't fail authentication if last login update fails

        # Return user without password hash
        user_clean = {k: v for k, v in user.items() if k != "password_hash"}
        logger.info(f"User authenticated: {user['username']} (ID: {user['user_id']})")
        return user_clean

    def register_user(self, username: str, email: str, password: str, role: str = "user") -> int:
        """Register a new user.

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
        return self.user_service.create_user(
            username=username, email=email, password=password, role=role
        )

    def is_admin(self, user: dict[str, Any]) -> bool:
        """Check if user is an admin.

        Args:
            user: User dictionary

        Returns:
            True if user is admin, False otherwise
        """
        return user.get("role") == "admin"
