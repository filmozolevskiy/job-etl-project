"""Integration tests for authentication flow."""

from __future__ import annotations

import pytest

from services.auth.auth_service import AuthService
from services.auth.user_service import UserService
from services.shared.database import PostgreSQLDatabase


@pytest.fixture
def test_db(test_database):
    """Create a test database connection."""
    return PostgreSQLDatabase(connection_string=test_database)


@pytest.mark.integration
class TestAuthIntegration:
    """Integration tests for authentication flow."""

    def test_full_registration_and_login_flow(self, test_db):
        """Test complete registration → login flow."""
        user_service = UserService(database=test_db)
        auth_service = AuthService(user_service=user_service)

        # Register user
        user_id = auth_service.register_user(
            username="integration_test_user",
            email="integration@test.com",
            password="testpassword123",
        )
        assert user_id is not None

        # Authenticate user
        user = auth_service.authenticate_user("integration_test_user", "testpassword123")
        assert user is not None
        assert user["user_id"] == user_id
        assert user["username"] == "integration_test_user"

        # Try to authenticate with wrong password
        wrong_user = auth_service.authenticate_user("integration_test_user", "wrongpassword")
        assert wrong_user is None

    def test_registration_prevents_duplicate_username(self, test_db):
        """Test that registration prevents duplicate usernames."""
        user_service = UserService(database=test_db)
        auth_service = AuthService(user_service=user_service)

        # Register first user
        auth_service.register_user(
            username="duplicate_test", email="dup1@test.com", password="password123"
        )

        # Try to register with same username
        with pytest.raises(ValueError, match="already exists"):
            auth_service.register_user(
                username="duplicate_test", email="dup2@test.com", password="password123"
            )

    def test_registration_prevents_duplicate_email(self, test_db):
        """Test that registration prevents duplicate emails."""
        user_service = UserService(database=test_db)
        auth_service = AuthService(user_service=user_service)

        # Register first user
        auth_service.register_user(
            username="user1", email="dupemail@test.com", password="password123"
        )

        # Try to register with same email
        with pytest.raises(ValueError, match="already exists"):
            auth_service.register_user(
                username="user2", email="dupemail@test.com", password="password123"
            )
