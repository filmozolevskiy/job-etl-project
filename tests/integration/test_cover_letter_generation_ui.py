"""Integration tests for cover letter generation UI routes."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.documents.cover_letter_generator import CoverLetterGenerationError

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def test_app(test_database):
    """Create a Flask test app with test database."""
    import sys

    # Add campaign_ui to path
    campaign_ui_path = Path(__file__).parent.parent.parent / "campaign_ui"
    if str(campaign_ui_path) not in sys.path:
        sys.path.insert(0, str(campaign_ui_path))

    from app import app as flask_app

    # Configure test database
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False

    # Set test database connection
    with patch.dict(os.environ, {"DATABASE_URL": test_database}):
        yield flask_app


@pytest.fixture
def test_client(test_app):
    """Create a Flask test client."""
    return test_app.test_client()


@pytest.fixture
def authenticated_user(test_database, test_client):
    """Create and authenticate a test user."""
    from services.auth import UserService
    from services.shared import PostgreSQLDatabase

    db = PostgreSQLDatabase(connection_string=test_database)
    user_service = UserService(database=db)

    # Create test user
    user_id = user_service.create_user(
        username="test_gen_user",
        email="test_gen@example.com",
        password="test_password_123",
        role="user",
    )

    # Get the full user object
    user = user_service.get_user_by_id(user_id)

    # Login user - set session data for Flask-Login
    with test_client.session_transaction() as sess:
        sess["_user_id"] = str(user["user_id"])
        sess["_fresh"] = True

    yield user

    # Cleanup
    with db.get_cursor() as cur:
        cur.execute("DELETE FROM marts.users WHERE user_id = %s", (user_id,))


class TestCoverLetterGenerationRoute:
    """Test the cover letter generation Flask route."""

    def test_generate_cover_letter_success(self, test_client, authenticated_user, test_app):
        """Test successful cover letter generation."""
        import sys

        campaign_ui_path = Path(__file__).parent.parent.parent / "campaign_ui"
        if str(campaign_ui_path) not in sys.path:
            sys.path.insert(0, str(campaign_ui_path))

        # Import app module so we can patch its functions
        import app as app_module

        job_id = "test_job_123"
        resume_id = 1

        mock_cover_letter = {
            "cover_letter_id": 1,
            "cover_letter_text": "Generated cover letter text",
            "cover_letter_name": "Cover Letter - Company - Position",
            "generation_prompt": "Test prompt",
        }

        mock_generator = MagicMock()
        mock_generator.generate_cover_letter.return_value = mock_cover_letter

        mock_doc_service = MagicMock()

        # Patch the functions in the module where they're used
        with patch.object(app_module, "get_cover_letter_generator", return_value=mock_generator):
            with patch.object(app_module, "get_document_service", return_value=mock_doc_service):
                response = test_client.post(
                    f"/api/jobs/{job_id}/cover-letter/generate",
                    json={"resume_id": resume_id},
                    content_type="application/json",
                )

                assert response.status_code == 200
                data = response.get_json()
                assert data["cover_letter_text"] == "Generated cover letter text"
                assert data["cover_letter_id"] == 1
                assert data["cover_letter_name"] == "Cover Letter - Company - Position"

                # Verify generator was called correctly
                mock_generator.generate_cover_letter.assert_called_once_with(
                    resume_id=resume_id,
                    jsearch_job_id=job_id,
                    user_id=authenticated_user["user_id"],
                    user_comments=None,
                )

                # Verify document was linked
                mock_doc_service.link_documents_to_job.assert_called_once_with(
                    jsearch_job_id=job_id,
                    user_id=authenticated_user["user_id"],
                    cover_letter_id=1,
                )

    def test_generate_cover_letter_with_comments(self, test_client, authenticated_user, test_app):
        """Test cover letter generation with user comments."""
        import sys

        campaign_ui_path = Path(__file__).parent.parent.parent / "campaign_ui"
        if str(campaign_ui_path) not in sys.path:
            sys.path.insert(0, str(campaign_ui_path))

        import app as app_module

        job_id = "test_job_123"
        resume_id = 1
        user_comments = "Emphasize Python experience"

        mock_cover_letter = {
            "cover_letter_id": 1,
            "cover_letter_text": "Generated text",
            "cover_letter_name": "Cover Letter",
        }

        mock_generator = MagicMock()
        mock_generator.generate_cover_letter.return_value = mock_cover_letter

        with patch.object(app_module, "get_cover_letter_generator", return_value=mock_generator):
            with patch.object(app_module, "get_document_service"):
                response = test_client.post(
                    f"/api/jobs/{job_id}/cover-letter/generate",
                    json={"resume_id": resume_id, "user_comments": user_comments},
                    content_type="application/json",
                )

                assert response.status_code == 200
                mock_generator.generate_cover_letter.assert_called_once_with(
                    resume_id=resume_id,
                    jsearch_job_id=job_id,
                    user_id=authenticated_user["user_id"],
                    user_comments=user_comments,
                )

    def test_generate_cover_letter_missing_resume_id(self, test_client, authenticated_user):
        """Test generation fails when resume_id is missing."""
        job_id = "test_job_123"

        response = test_client.post(
            f"/api/jobs/{job_id}/cover-letter/generate",
            json={},
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "resume_id is required" in data["error"]

    def test_generate_cover_letter_invalid_resume_id(self, test_client, authenticated_user):
        """Test generation fails when resume_id is invalid."""
        job_id = "test_job_123"

        response = test_client.post(
            f"/api/jobs/{job_id}/cover-letter/generate",
            json={"resume_id": "not_an_int"},
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "must be an integer" in data["error"]

    def test_generate_cover_letter_not_json(self, test_client, authenticated_user):
        """Test generation fails when request is not JSON."""
        job_id = "test_job_123"

        response = test_client.post(
            f"/api/jobs/{job_id}/cover-letter/generate",
            data={"resume_id": 1},
            content_type="application/x-www-form-urlencoded",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "Request must be JSON" in data["error"]

    def test_generate_cover_letter_generation_error(
        self, test_client, authenticated_user, test_app
    ):
        """Test generation handles CoverLetterGenerationError."""
        import sys

        campaign_ui_path = Path(__file__).parent.parent.parent / "campaign_ui"
        if str(campaign_ui_path) not in sys.path:
            sys.path.insert(0, str(campaign_ui_path))

        import app as app_module

        job_id = "test_job_123"
        resume_id = 1

        mock_generator = MagicMock()
        mock_generator.generate_cover_letter.side_effect = CoverLetterGenerationError(
            "Failed to generate cover letter"
        )

        with patch.object(app_module, "get_cover_letter_generator", return_value=mock_generator):
            response = test_client.post(
                f"/api/jobs/{job_id}/cover-letter/generate",
                json={"resume_id": resume_id},
                content_type="application/json",
            )

            assert response.status_code == 500
            data = response.get_json()
            assert "error" in data
            # The error message is sanitized, so check for any error message
            assert len(data["error"]) > 0

    def test_generate_cover_letter_validation_error(
        self, test_client, authenticated_user, test_app
    ):
        """Test generation handles ValueError (e.g., job not found)."""
        import sys

        campaign_ui_path = Path(__file__).parent.parent.parent / "campaign_ui"
        if str(campaign_ui_path) not in sys.path:
            sys.path.insert(0, str(campaign_ui_path))

        import app as app_module

        job_id = "test_job_123"
        resume_id = 1

        mock_generator = MagicMock()
        mock_generator.generate_cover_letter.side_effect = ValueError(
            "Job not found or access denied"
        )

        with patch.object(app_module, "get_cover_letter_generator", return_value=mock_generator):
            response = test_client.post(
                f"/api/jobs/{job_id}/cover-letter/generate",
                json={"resume_id": resume_id},
                content_type="application/json",
            )

            assert response.status_code == 400
            data = response.get_json()
            assert "error" in data

    def test_generate_cover_letter_requires_login(self, test_client):
        """Test generation requires authentication."""
        job_id = "test_job_123"

        response = test_client.post(
            f"/api/jobs/{job_id}/cover-letter/generate",
            json={"resume_id": 1},
            content_type="application/json",
        )

        assert response.status_code == 302  # Redirect to login

    def test_generate_cover_letter_general_exception(
        self, test_client, authenticated_user, test_app
    ):
        """Test generation handles general exceptions."""
        import sys

        campaign_ui_path = Path(__file__).parent.parent.parent / "campaign_ui"
        if str(campaign_ui_path) not in sys.path:
            sys.path.insert(0, str(campaign_ui_path))

        import app as app_module

        job_id = "test_job_123"
        resume_id = 1

        mock_generator = MagicMock()
        mock_generator.generate_cover_letter.side_effect = Exception("Unexpected error")

        with patch.object(app_module, "get_cover_letter_generator", return_value=mock_generator):
            response = test_client.post(
                f"/api/jobs/{job_id}/cover-letter/generate",
                json={"resume_id": resume_id},
                content_type="application/json",
            )

            assert response.status_code == 500
            data = response.get_json()
            assert "error" in data
            # The error message is sanitized, so check for any error message
            assert len(data["error"]) > 0
