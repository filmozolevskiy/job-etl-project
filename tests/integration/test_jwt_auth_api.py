"""Integration tests for JWT auth API endpoints."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from services.campaign_management import CampaignService
from services.shared import PostgreSQLDatabase

pytestmark = pytest.mark.integration


@pytest.fixture
def test_app(test_database):
    """Create a Flask test app with test database."""
    campaign_ui_path = Path(__file__).parent.parent.parent / "campaign_ui"
    if str(campaign_ui_path) not in sys.path:
        sys.path.insert(0, str(campaign_ui_path))

    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": test_database,
            "JWT_SECRET_KEY": "test-jwt-secret",
            "FLASK_ENV": "development",
        },
        clear=False,
    ):
        if "app" in sys.modules:
            del sys.modules["app"]
        from app import app as flask_app

        flask_app.config["TESTING"] = True
        flask_app.config["WTF_CSRF_ENABLED"] = False
        yield flask_app


@pytest.fixture
def test_client(test_app):
    """Create a Flask test client."""
    return test_app.test_client()


def _register_user(test_client):
    username = f"jwt_user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "test_password_123"

    response = test_client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "password_confirm": password,
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data and "access_token" in data and "user" in data
    return data["access_token"], data["user"]["user_id"], username, password


def test_auth_login_returns_token(test_client):
    """Login returns a valid JWT payload."""
    _, user_id, username, password = _register_user(test_client)

    response = test_client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data and "access_token" in data and "user" in data
    assert data["user"]["user_id"] == user_id


def test_update_campaign_with_jwt_token(test_client, test_database):
    """Campaign update works with JWT identity string."""
    access_token, user_id, _, _ = _register_user(test_client)

    db = PostgreSQLDatabase(connection_string=test_database)
    campaign_service = CampaignService(database=db)
    campaign_id = campaign_service.create_campaign(
        campaign_name="JWT Campaign",
        query="Data Engineer",
        country="us",
        user_id=user_id,
        location="Remote",
    )

    response = test_client.put(
        f"/api/campaigns/{campaign_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "campaign_name": "JWT Campaign Updated",
            "query": "Data Engineer",
            "country": "us",
            "date_window": "week",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data and data.get("message") == "Campaign updated successfully"
