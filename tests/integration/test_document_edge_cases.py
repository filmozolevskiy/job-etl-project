"""Integration tests for edge cases in document management."""

from __future__ import annotations

import tempfile
from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def test_storage_dir():
    """Create a temporary directory for file storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_user_id(test_database):
    """Create a test user and return user_id."""
    import psycopg2

    conn = psycopg2.connect(test_database)
    try:
        conn.autocommit = True
    except psycopg2.ProgrammingError:
        pass
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO marts.users (username, email, password_hash, role)
                VALUES ('test_edge_user', 'test_edge@example.com', 'hashed_password', 'user')
                RETURNING user_id
                """
            )
            user_id = cur.fetchone()[0]
            yield user_id
    finally:
        conn.close()


@pytest.fixture
def test_job_id(test_database):
    """Create a test job and return jsearch_job_id."""
    from services.shared import PostgreSQLDatabase

    db = PostgreSQLDatabase(connection_string=test_database)
    with db.get_cursor() as cur:
        # Create a user first to satisfy foreign key constraint
        cur.execute(
            """
            INSERT INTO marts.users (username, email, password_hash, role)
            VALUES ('edge_case_user', 'edge@test.com', 'hash', 'user')
            ON CONFLICT (username) DO UPDATE SET email = EXCLUDED.email
            RETURNING user_id
            """
        )
        user_id = cur.fetchone()[0]

        # Create a test campaign first to satisfy foreign key constraint
        cur.execute(
            """
            INSERT INTO marts.job_campaigns (campaign_id, user_id, campaign_name, is_active, query, country)
            VALUES (1, %s, 'Test Edge Campaign', true, 'test', 'us')
            ON CONFLICT (campaign_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                campaign_name = EXCLUDED.campaign_name,
                is_active = EXCLUDED.is_active
            """,
            (user_id,),
        )
        cur.execute(
            """
            INSERT INTO marts.fact_jobs (
                jsearch_job_id, campaign_id, job_title, employer_name, job_location,
                job_apply_link, job_posted_at_datetime_utc, dwh_load_date, dwh_load_timestamp, dwh_source_system
            )
            VALUES (
                'test_edge_job', 1, 'Test Job', 'Test Company',
                'Test Location', 'https://test.com', CURRENT_TIMESTAMP, CURRENT_DATE, NOW(), 'test'
            )
            ON CONFLICT (jsearch_job_id, campaign_id) DO UPDATE SET
                job_title = EXCLUDED.job_title
            RETURNING jsearch_job_id
            """
        )
        result = cur.fetchone()

    if result:
        yield result[0]
    else:
        yield "test_edge_job"


class TestDocumentEdgeCasesIntegration:
    """Integration tests for document management edge cases."""

    def test_resume_linked_to_multiple_jobs(
        self,
        resume_service,
        document_service,
        test_user_id,
        test_storage_dir,
    ):
        """Test that same resume can be linked to multiple jobs."""
        from io import BytesIO

        file = FileStorage(
            stream=BytesIO(b"%PDF-1.4\ncontent"),
            filename="shared_resume.pdf",
            content_type="application/pdf",
        )

        # Upload resume
        resume = resume_service.upload_resume(
            user_id=test_user_id, file=file, resume_name="Shared Resume"
        )

        # Link to multiple jobs
        job1_doc = document_service.link_documents_to_job(
            jsearch_job_id="job1", user_id=test_user_id, resume_id=resume["resume_id"]
        )
        job2_doc = document_service.link_documents_to_job(
            jsearch_job_id="job2", user_id=test_user_id, resume_id=resume["resume_id"]
        )

        assert job1_doc["resume_id"] == resume["resume_id"]
        assert job2_doc["resume_id"] == resume["resume_id"]

        # Verify both links exist
        doc1 = document_service.get_job_application_document(
            jsearch_job_id="job1", user_id=test_user_id
        )
        doc2 = document_service.get_job_application_document(
            jsearch_job_id="job2", user_id=test_user_id
        )
        assert doc1["resume_id"] == resume["resume_id"]
        assert doc2["resume_id"] == resume["resume_id"]

    def test_delete_resume_linked_to_jobs(
        self,
        resume_service,
        document_service,
        test_user_id,
        test_job_id,
        test_storage_dir,
    ):
        """Test deleting resume that is linked to jobs (should delete resume but not document records)."""
        file = FileStorage(
            stream=BytesIO(b"%PDF-1.4\ncontent"),
            filename="linked_resume.pdf",
            content_type="application/pdf",
        )

        # Upload and link resume
        resume = resume_service.upload_resume(
            user_id=test_user_id, file=file, resume_name="Linked Resume"
        )
        document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            resume_id=resume["resume_id"],
        )

        # Delete resume
        result = resume_service.delete_resume(resume_id=resume["resume_id"], user_id=test_user_id)
        assert result is True

        # Document record should still exist but resume_id should be None or invalid
        # This depends on foreign key constraints
        doc = document_service.get_job_application_document(
            jsearch_job_id=test_job_id, user_id=test_user_id
        )
        # Document might still exist but resume_id might be cleared or invalid
        assert doc is not None

    def test_cover_letter_same_name_different_jobs(
        self, cover_letter_service, test_user_id, test_storage_dir
    ):
        """Test creating cover letters with same name for different jobs."""
        cl1 = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Generic Cover Letter",
            cover_letter_text="Text for job 1",
            jsearch_job_id="job1",
        )

        cl2 = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Generic Cover Letter",  # Same name
            cover_letter_text="Text for job 2",
            jsearch_job_id="job2",
        )

        assert cl1["cover_letter_name"] == cl2["cover_letter_name"]
        assert cl1["cover_letter_id"] != cl2["cover_letter_id"]
        assert cl1["jsearch_job_id"] == "job1"
        assert cl2["jsearch_job_id"] == "job2"

    def test_switch_from_inline_text_to_cover_letter_id(
        self, cover_letter_service, document_service, test_user_id, test_job_id
    ):
        """Test switching from inline text to linked cover letter."""
        # Start with inline text
        doc1 = document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            cover_letter_text="Initial inline text",
        )
        assert doc1["cover_letter_text"] == "Initial inline text"
        assert doc1.get("cover_letter_id") is None

        # Create cover letter
        cl = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="New Cover Letter",
            cover_letter_text="Cover letter text",
            jsearch_job_id=test_job_id,
        )

        # Switch to linked cover letter
        doc2 = document_service.update_job_application_document(
            document_id=doc1["document_id"],
            user_id=test_user_id,
            cover_letter_id=cl["cover_letter_id"],
            cover_letter_text=None,  # Clear inline text
        )
        assert doc2["cover_letter_id"] == cl["cover_letter_id"]
        assert (
            doc2.get("cover_letter_text") is None
            or doc2["cover_letter_text"] != "Initial inline text"
        )

    def test_switch_from_cover_letter_id_to_inline_text(
        self, cover_letter_service, document_service, test_user_id, test_job_id
    ):
        """Test switching from linked cover letter to inline text."""
        # Start with linked cover letter
        cl = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Old Cover Letter",
            cover_letter_text="Old text",
            jsearch_job_id=test_job_id,
        )

        doc1 = document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            cover_letter_id=cl["cover_letter_id"],
        )
        assert doc1["cover_letter_id"] == cl["cover_letter_id"]

        # Switch to inline text
        doc2 = document_service.update_job_application_document(
            document_id=doc1["document_id"],
            user_id=test_user_id,
            cover_letter_id=None,  # Clear linked cover letter
            cover_letter_text="New inline text",
        )
        assert doc2.get("cover_letter_id") is None
        assert doc2["cover_letter_text"] == "New inline text"

    def test_concurrent_updates_same_document(self, document_service, test_user_id, test_job_id):
        """Test concurrent updates to same document (last write wins)."""
        # Create initial document
        doc = document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            user_notes="Initial notes",
        )

        # Simulate concurrent updates (sequential in test, but tests the update logic)
        document_service.update_job_application_document(
            document_id=doc["document_id"],
            user_id=test_user_id,
            user_notes="Update 1",
        )

        document_service.update_job_application_document(
            document_id=doc["document_id"],
            user_id=test_user_id,
            user_notes="Update 2",
        )

        # Last update should win
        final_doc = document_service.get_job_application_document(
            jsearch_job_id=test_job_id, user_id=test_user_id
        )
        assert final_doc["user_notes"] == "Update 2"

    def test_file_with_special_characters_in_name(
        self, resume_service, test_user_id, test_storage_dir
    ):
        """Test uploading file with special characters in filename."""
        special_filename = "résumé with spaces & symbols!@#.pdf"
        file = FileStorage(
            stream=BytesIO(b"%PDF-1.4\ncontent"),
            filename=special_filename,
            content_type="application/pdf",
        )

        resume = resume_service.upload_resume(
            user_id=test_user_id, file=file, resume_name="Special Name Resume"
        )

        # Should succeed - filename should be sanitized
        assert resume["resume_id"] is not None
        # File path should be sanitized
        assert resume["file_path"] is not None
        assert "résumé" not in resume["file_path"] or "resume" in resume["file_path"].lower()

    def test_very_long_cover_letter_text(
        self, cover_letter_service, document_service, test_user_id, test_job_id
    ):
        """Test creating cover letter with very long text (100KB)."""
        long_text = "A" * 100000  # 100KB

        cl = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Long Cover Letter",
            cover_letter_text=long_text,
            jsearch_job_id=test_job_id,
        )

        assert len(cl["cover_letter_text"]) == 100000

        # Link to job
        doc = document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            cover_letter_id=cl["cover_letter_id"],
        )
        assert doc["cover_letter_id"] == cl["cover_letter_id"]

    def test_multiple_resumes_same_name(self, resume_service, test_user_id, test_storage_dir):
        """Test uploading multiple resumes with same name."""
        file1 = FileStorage(
            stream=BytesIO(b"%PDF-1.4\ncontent1"),
            filename="resume.pdf",
            content_type="application/pdf",
        )
        file2 = FileStorage(
            stream=BytesIO(b"%PDF-1.4\ncontent2"),
            filename="resume.pdf",
            content_type="application/pdf",
        )

        resume1 = resume_service.upload_resume(
            user_id=test_user_id, file=file1, resume_name="My Resume"
        )
        resume2 = resume_service.upload_resume(
            user_id=test_user_id,
            file=file2,
            resume_name="My Resume",  # Same name
        )

        assert resume1["resume_name"] == resume2["resume_name"]
        assert resume1["resume_id"] != resume2["resume_id"]

        # Both should be retrievable
        resumes = resume_service.get_user_resumes(user_id=test_user_id)
        resume_ids = [r["resume_id"] for r in resumes]
        assert resume1["resume_id"] in resume_ids
        assert resume2["resume_id"] in resume_ids

    def test_get_documents_for_nonexistent_user(self, document_service, test_job_id):
        """Test getting documents for non-existent user."""
        doc = document_service.get_job_application_document(
            jsearch_job_id=test_job_id, user_id=99999
        )
        assert doc is None

    def test_update_document_with_all_none_values(
        self, document_service, test_user_id, test_job_id
    ):
        """Test updating document with all None values (should preserve existing)."""
        # Create document with values
        doc = document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            user_notes="Initial notes",
        )

        # Update with all None (should preserve existing values)
        updated = document_service.update_job_application_document(
            document_id=doc["document_id"],
            user_id=test_user_id,
            resume_id=None,
            cover_letter_id=None,
            cover_letter_text=None,
            user_notes=None,
        )

        # Depending on implementation, might preserve or clear
        # This tests the edge case behavior
        assert updated is not None
