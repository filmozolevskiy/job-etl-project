"""Unit tests for UserService."""

from unittest.mock import Mock

import bcrypt
import pytest

from services.auth.user_service import UserService


@pytest.fixture
def mock_database():
    """Create a mock database."""
    db = Mock()
    db.get_cursor.return_value.__enter__ = Mock(return_value=Mock())
    db.get_cursor.return_value.__exit__ = Mock(return_value=False)
    return db


@pytest.fixture
def user_service(mock_database):
    """Create a UserService instance with mocked database."""
    return UserService(database=mock_database)


class TestUserService:
    """Test cases for UserService."""

    def test_init_requires_database(self):
        """Test that UserService requires a database."""
        with pytest.raises(ValueError, match="Database is required"):
            UserService(database=None)

    def test_hash_password(self, user_service):
        """Test password hashing."""
        password = "testpassword123"
        hash_result = user_service._hash_password(password)

        assert hash_result is not None
        assert hash_result.startswith("$2b$")  # bcrypt hash prefix
        assert len(hash_result) > 20  # bcrypt hashes are long

    def test_verify_password_correct(self, user_service):
        """Test password verification with correct password."""
        password = "testpassword123"
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        result = user_service.verify_password(password, password_hash)

        assert result is True

    def test_verify_password_incorrect(self, user_service):
        """Test password verification with incorrect password."""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        result = user_service.verify_password(wrong_password, password_hash)

        assert result is False

    def test_create_user_validation_empty_username(self, user_service, mock_database):
        """Test create_user validates empty username."""
        with pytest.raises(ValueError, match="Username is required"):
            user_service.create_user(username="", email="test@example.com", password="password123")

    def test_create_user_validation_empty_email(self, user_service):
        """Test create_user validates empty email."""
        with pytest.raises(ValueError, match="Email is required"):
            user_service.create_user(username="testuser", email="", password="password123")

    def test_create_user_validation_short_password(self, user_service):
        """Test create_user validates password length."""
        with pytest.raises(ValueError, match="Password must be at least 6 characters"):
            user_service.create_user(
                username="testuser", email="test@example.com", password="short"
            )

    def test_create_user_validation_invalid_role(self, user_service):
        """Test create_user validates role."""
        with pytest.raises(ValueError, match="Role must be 'user' or 'admin'"):
            user_service.create_user(
                username="testuser",
                email="test@example.com",
                password="password123",
                role="invalid",
            )

    def test_create_user_checks_username_exists(self, user_service, mock_database):
        """Test create_user checks if username already exists."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock existing user
        existing_user = {"user_id": 1, "username": "existinguser"}
        user_service.get_user_by_username = Mock(return_value=existing_user)

        with pytest.raises(ValueError, match="Username 'existinguser' already exists"):
            user_service.create_user(
                username="existinguser", email="test@example.com", password="password123"
            )

    def test_create_user_checks_email_exists(self, user_service, mock_database):
        """Test create_user checks if email already exists."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock no existing username, but existing email
        user_service.get_user_by_username = Mock(return_value=None)
        existing_user = {"user_id": 1, "email": "existing@example.com"}
        user_service.get_user_by_email = Mock(return_value=existing_user)

        with pytest.raises(ValueError, match="Email 'existing@example.com' already exists"):
            user_service.create_user(
                username="newuser", email="existing@example.com", password="password123"
            )

    def test_create_user_success(self, user_service, mock_database):
        """Test successful user creation."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock no existing user
        user_service.get_user_by_username = Mock(return_value=None)
        user_service.get_user_by_email = Mock(return_value=None)

        # Mock cursor execution
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (1,)  # Return user_id

        user_id = user_service.create_user(
            username="newuser", email="newuser@example.com", password="password123"
        )

        assert user_id == 1
        mock_cursor.execute.assert_called_once()
        # Verify password was hashed
        call_args = mock_cursor.execute.call_args
        assert call_args is not None
        password_hash_arg = call_args[0][1][2]  # Third parameter (index 2) is password_hash
        assert password_hash_arg.startswith("$2b$")

    def test_get_user_by_username_not_found(self, user_service, mock_database):
        """Test get_user_by_username returns None when user not found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("user_id",), ("username",), ("email",)]
        mock_cursor.fetchone.return_value = None

        result = user_service.get_user_by_username("nonexistent")

        assert result is None

    def test_get_user_by_email_not_found(self, user_service, mock_database):
        """Test get_user_by_email returns None when user not found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("user_id",), ("username",), ("email",)]
        mock_cursor.fetchone.return_value = None

        result = user_service.get_user_by_email("nonexistent@example.com")

        assert result is None

    def test_get_user_by_id_not_found(self, user_service, mock_database):
        """Test get_user_by_id returns None when user not found."""
        mock_cursor = Mock()
        mock_database.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("user_id",), ("username",), ("email",)]
        mock_cursor.fetchone.return_value = None

        result = user_service.get_user_by_id(999)

        assert result is None

    def test_verify_password_handles_exceptions(self, user_service):
        """Test verify_password handles exceptions gracefully."""
        # Invalid hash format
        result = user_service.verify_password("password", "invalid_hash")

        assert result is False
