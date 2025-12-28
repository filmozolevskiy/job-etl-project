"""Unit tests for authentication services."""

from unittest.mock import Mock

import pytest

from services.auth.auth_service import AuthService
from services.auth.user_service import UserService


@pytest.fixture
def mock_user_service():
    """Create a mock UserService."""
    return Mock(spec=UserService)


@pytest.fixture
def auth_service(mock_user_service):
    """Create an AuthService instance with mocked dependencies."""
    return AuthService(user_service=mock_user_service)


class TestAuthService:
    """Test cases for AuthService."""

    def test_init_requires_user_service(self):
        """Test that AuthService requires a UserService."""
        with pytest.raises(ValueError, match="UserService is required"):
            AuthService(user_service=None)

    def test_init_with_valid_user_service(self, auth_service):
        """Test that AuthService initializes with valid UserService."""
        assert auth_service.user_service is not None

    def test_authenticate_user_success_by_username(self, auth_service, mock_user_service):
        """Test successful authentication by username."""
        # Mock user data
        mock_user = {
            "user_id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "password_hash": "$2b$12$hashed_password",
            "role": "user"
        }
        mock_user_service.get_user_by_username.return_value = mock_user
        mock_user_service.verify_password.return_value = True
        mock_user_service.update_last_login.return_value = None

        result = auth_service.authenticate_user("testuser", "password123")

        assert result is not None
        assert result["user_id"] == 1
        assert result["username"] == "testuser"
        assert "password_hash" not in result  # Password hash should be excluded
        mock_user_service.get_user_by_username.assert_called_once_with("testuser")
        mock_user_service.verify_password.assert_called_once()

    def test_authenticate_user_success_by_email(self, auth_service, mock_user_service):
        """Test successful authentication by email."""
        mock_user = {
            "user_id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "password_hash": "$2b$12$hashed_password",
            "role": "user"
        }
        mock_user_service.get_user_by_username.return_value = None
        mock_user_service.get_user_by_email.return_value = mock_user
        mock_user_service.verify_password.return_value = True
        mock_user_service.update_last_login.return_value = None

        result = auth_service.authenticate_user("test@example.com", "password123")

        assert result is not None
        assert result["user_id"] == 1
        mock_user_service.get_user_by_email.assert_called_once_with("test@example.com")

    def test_authenticate_user_invalid_username(self, auth_service, mock_user_service):
        """Test authentication with invalid username."""
        mock_user_service.get_user_by_username.return_value = None
        mock_user_service.get_user_by_email.return_value = None

        result = auth_service.authenticate_user("invaliduser", "password123")

        assert result is None
        mock_user_service.verify_password.assert_not_called()

    def test_authenticate_user_invalid_password(self, auth_service, mock_user_service):
        """Test authentication with invalid password."""
        mock_user = {
            "user_id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "password_hash": "$2b$12$hashed_password",
            "role": "user"
        }
        mock_user_service.get_user_by_username.return_value = mock_user
        mock_user_service.verify_password.return_value = False

        result = auth_service.authenticate_user("testuser", "wrongpassword")

        assert result is None

    def test_authenticate_user_empty_credentials(self, auth_service):
        """Test authentication with empty credentials."""
        result1 = auth_service.authenticate_user("", "password")
        result2 = auth_service.authenticate_user("username", "")
        result3 = auth_service.authenticate_user("", "")

        assert result1 is None
        assert result2 is None
        assert result3 is None

    def test_authenticate_user_handles_last_login_error(self, auth_service, mock_user_service):
        """Test that authentication succeeds even if last login update fails."""
        mock_user = {
            "user_id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "password_hash": "$2b$12$hashed_password",
            "role": "user"
        }
        mock_user_service.get_user_by_username.return_value = mock_user
        mock_user_service.verify_password.return_value = True
        mock_user_service.update_last_login.side_effect = Exception("Database error")

        # Should not raise exception
        result = auth_service.authenticate_user("testuser", "password123")

        assert result is not None

    def test_register_user_success(self, auth_service, mock_user_service):
        """Test successful user registration."""
        mock_user_service.create_user.return_value = 1

        user_id = auth_service.register_user(
            username="newuser",
            email="newuser@example.com",
            password="password123"
        )

        assert user_id == 1
        mock_user_service.create_user.assert_called_once_with(
            username="newuser",
            email="newuser@example.com",
            password="password123",
            role="user"
        )

    def test_register_user_with_custom_role(self, auth_service, mock_user_service):
        """Test user registration with custom role."""
        mock_user_service.create_user.return_value = 2

        user_id = auth_service.register_user(
            username="adminuser",
            email="admin@example.com",
            password="password123",
            role="admin"
        )

        assert user_id == 2
        mock_user_service.create_user.assert_called_once_with(
            username="adminuser",
            email="admin@example.com",
            password="password123",
            role="admin"
        )

    def test_is_admin_returns_true_for_admin(self, auth_service):
        """Test is_admin returns True for admin user."""
        admin_user = {"user_id": 1, "username": "admin", "role": "admin"}
        assert auth_service.is_admin(admin_user) is True

    def test_is_admin_returns_false_for_regular_user(self, auth_service):
        """Test is_admin returns False for regular user."""
        regular_user = {"user_id": 2, "username": "user", "role": "user"}
        assert auth_service.is_admin(regular_user) is False

    def test_is_admin_returns_false_for_missing_role(self, auth_service):
        """Test is_admin returns False when role is missing."""
        user_no_role = {"user_id": 3, "username": "user"}
        assert auth_service.is_admin(user_no_role) is False

