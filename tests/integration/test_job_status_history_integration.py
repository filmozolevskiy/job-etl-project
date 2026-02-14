"""
Integration tests for job status history tracking.

Tests end-to-end history recording across all services:
1. Job extraction records job_found
2. AI enrichment records updated_by_ai/updated_by_chatgpt
3. Document changes record documents_uploaded/documents_changed
4. Note changes record note_added/note_updated/note_deleted
5. Status changes record status_changed
"""

import pytest

from services.documents import DocumentService
from services.jobs import JobNoteService, JobStatusService
from services.shared import PostgreSQLDatabase

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


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
                VALUES ('test_history_user', 'test_history@example.com', 'hashed_password', 'user')
                RETURNING user_id
                """
            )
            result = cur.fetchone()
            if not result:
                raise ValueError("Failed to create test user")
            user_id = result[0]
            yield user_id
    finally:
        conn.close()


@pytest.fixture
def test_campaign_id(test_database, test_user_id):
    """Create a test campaign and return campaign_id."""
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
                INSERT INTO marts.job_campaigns (
                    campaign_id, user_id, campaign_name, is_active, query, location, country
                )
                VALUES (1, %s, 'Test Campaign', true, 'test query', 'Toronto', 'CA')
                RETURNING campaign_id
                """,
                (test_user_id,),
            )
            result = cur.fetchone()
            if not result:
                raise ValueError("Failed to create test campaign")
            campaign_id = result[0]
            yield campaign_id
    finally:
        conn.close()


@pytest.fixture
def test_job_id():
    """Return a test job ID."""
    return "test_job_history_123"


@pytest.fixture
def job_status_service(test_database):
    """Create JobStatusService with test database."""
    return JobStatusService(database=PostgreSQLDatabase(connection_string=test_database))


@pytest.fixture
def job_note_service(test_database):
    """Create JobNoteService with test database."""
    return JobNoteService(database=PostgreSQLDatabase(connection_string=test_database))


@pytest.fixture
def document_service(test_database):
    """Create DocumentService with test database."""
    return DocumentService(database=PostgreSQLDatabase(connection_string=test_database))


@pytest.fixture
def test_job_setup(test_database, test_user_id, test_campaign_id, test_job_id):
    """Set up fact_jobs and dim_companies tables needed for job queries."""
    from services.shared import PostgreSQLDatabase

    db = PostgreSQLDatabase(connection_string=test_database)
    with db.get_cursor() as cur:
        # Insert test job into fact_jobs and dim_ranking
        cur.execute(
            """
            INSERT INTO marts.fact_jobs (
                jsearch_job_id, campaign_id, job_title, employer_name, job_location,
                employment_type, dwh_load_date, dwh_load_timestamp, dwh_source_system
            )
            VALUES (%s, %s, 'Test Job', 'Test Company', 'Test Location',
                'FULLTIME', CURRENT_DATE, CURRENT_TIMESTAMP, 'test')
            """,
            (test_job_id, test_campaign_id),
        )
        cur.execute(
            """
            INSERT INTO marts.dim_ranking (jsearch_job_id, campaign_id, rank_score, ranked_at)
            VALUES (%s, %s, 80.0, CURRENT_TIMESTAMP)
            """,
            (test_job_id, test_campaign_id),
        )
    yield


class TestJobStatusHistoryIntegration:
    """Integration tests for job status history tracking."""

    def test_record_job_found_creates_history(
        self, job_status_service, test_user_id, test_job_id, test_campaign_id
    ):
        """Test that record_job_found creates a history entry."""
        history_id = job_status_service.record_job_found(
            jsearch_job_id=test_job_id, user_id=test_user_id, campaign_id=test_campaign_id
        )

        assert history_id is not None

        # Verify history entry
        history = job_status_service.get_status_history(test_job_id, test_user_id)
        assert len(history) == 1
        assert history[0]["status"] == "job_found"
        assert history[0]["change_type"] == "extraction"
        assert history[0]["changed_by"] == "system"
        assert history[0]["user_id"] == test_user_id
        assert history[0]["jsearch_job_id"] == test_job_id
        if history[0].get("metadata"):
            assert history[0]["metadata"].get("campaign_id") == test_campaign_id

    def test_record_ai_update_creates_history(self, job_status_service, test_user_id, test_job_id):
        """Test that record_ai_update creates a history entry."""
        enrichment_details = {
            "skills_extracted": 5,
            "seniority_level": "senior",
            "remote_work_type": "remote",
        }

        history_id = job_status_service.record_ai_update(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            enrichment_type="ai_enricher",
            enrichment_details=enrichment_details,
        )

        assert history_id is not None

        # Verify history entry
        history = job_status_service.get_status_history(test_job_id, test_user_id)
        assert len(history) == 1
        assert history[0]["status"] == "updated_by_ai"
        assert history[0]["change_type"] == "enrichment"
        assert history[0]["changed_by"] == "ai_enricher"
        assert history[0]["metadata"]["skills_extracted"] == 5

    def test_record_chatgpt_update_creates_history(
        self, job_status_service, test_user_id, test_job_id
    ):
        """Test that ChatGPT enrichment creates history entry."""
        enrichment_details = {"summary_extracted": True, "skills_extracted": 3}

        history_id = job_status_service.record_ai_update(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            enrichment_type="ai_enricher",  # Changed from "chatgpt_enricher"
            enrichment_details=enrichment_details,
        )

        assert history_id is not None

        # Verify history entry
        history = job_status_service.get_status_history(test_job_id, test_user_id)
        assert len(history) == 1
        assert history[0]["status"] == "updated_by_ai"
        assert history[0]["change_type"] == "enrichment"
        assert history[0]["changed_by"] == "ai_enricher"

    def test_record_document_change_creates_history(
        self,
        job_status_service,
        document_service,
        resume_service,
        cover_letter_service,
        test_user_id,
        test_job_id,
        test_job_setup,
    ):
        """Test that document changes create history entries."""
        from io import BytesIO

        from werkzeug.datastructures import FileStorage

        # Create a test resume
        resume_file = FileStorage(
            stream=BytesIO(b"%PDF-1.4\nresume content"),
            filename="test_resume.pdf",
            content_type="application/pdf",
        )
        resume = resume_service.upload_resume(
            user_id=test_user_id, file=resume_file, resume_name="Test Resume"
        )

        # First link (should be "uploaded")
        document_service.link_documents_to_job(
            jsearch_job_id=test_job_id, user_id=test_user_id, resume_id=resume["resume_id"]
        )

        # Verify history
        history = job_status_service.get_status_history(test_job_id, test_user_id)
        assert len(history) == 1
        assert history[0]["status"] == "documents_uploaded"
        assert history[0]["change_type"] == "document_change"
        assert history[0]["changed_by"] == "user"
        assert history[0]["changed_by_user_id"] == test_user_id

        # Create a test cover letter
        cover_letter = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Test Cover Letter",
            cover_letter_text="Test cover letter text",
        )

        # Get document_id from the linked document
        doc = document_service.get_job_application_document(test_job_id, test_user_id)
        assert doc is not None

        # Update (should be "changed")
        document_service.update_job_application_document(
            document_id=doc["document_id"],
            user_id=test_user_id,
            cover_letter_id=cover_letter["cover_letter_id"],
        )

        # Verify new history entry (history is ordered ASC - oldest first)
        history = job_status_service.get_status_history(test_job_id, test_user_id)
        assert len(history) == 2
        assert history[0]["status"] == "documents_uploaded"  # Oldest first
        assert history[1]["status"] == "documents_changed"  # Most recent last

    def test_record_note_change_creates_history(
        self,
        job_status_service,
        job_note_service,
        test_user_id,
        test_job_id,
        test_job_setup,
    ):
        """Test that note changes do NOT create history entries (functionality removed)."""
        # Add note
        note_id = job_note_service.add_note(
            jsearch_job_id=test_job_id, user_id=test_user_id, note_text="Test note"
        )

        # Verify NO history is created for notes (note changes are no longer tracked)
        history = job_status_service.get_status_history(test_job_id, test_user_id)
        assert len(history) == 0

        # Update note
        job_note_service.update_note(
            note_id=note_id, user_id=test_user_id, note_text="Updated note"
        )

        # Verify NO update history
        history = job_status_service.get_status_history(test_job_id, test_user_id)
        assert len(history) == 0

        # Delete note
        job_note_service.delete_note(note_id=note_id, user_id=test_user_id)

        # Verify NO history is created for note deletion either (functionality removed)
        history = job_status_service.get_status_history(test_job_id, test_user_id)
        assert len(history) == 0

    def test_upsert_status_records_history(
        self, job_status_service, test_user_id, test_job_id, test_job_setup
    ):
        """Test that status changes create history entries."""
        # Set initial status
        job_status_service.upsert_status(test_job_id, test_user_id, "waiting")

        # Verify history for initial status (should record status_changed)
        # History is ordered by created_at ASC (oldest first)
        history = job_status_service.get_status_history(test_job_id, test_user_id)
        assert len(history) == 1
        assert history[0]["status"] == "status_changed"
        assert history[0]["metadata"]["new_status"] == "waiting"
        assert history[0]["metadata"]["old_status"] is None

        # Change status
        job_status_service.upsert_status(test_job_id, test_user_id, "applied")

        # Verify new history entry (ordered oldest first)
        history = job_status_service.get_status_history(test_job_id, test_user_id)
        assert len(history) == 2
        # First entry (oldest) should be "waiting"
        assert history[0]["status"] == "status_changed"
        assert history[0]["metadata"]["new_status"] == "waiting"
        assert history[0]["metadata"]["old_status"] is None
        # Last entry (newest) should be "applied"
        assert history[1]["status"] == "status_changed"
        assert history[1]["metadata"]["new_status"] == "applied"
        assert history[1]["metadata"]["old_status"] == "waiting"

    def test_get_user_status_history_returns_all_jobs(self, job_status_service, test_user_id):
        """Test that get_user_status_history returns history for all user's jobs."""
        # Create history for multiple jobs
        job_status_service.record_job_found("job1", test_user_id)
        job_status_service.record_job_found("job2", test_user_id)
        job_status_service.record_ai_update("job1", test_user_id, "ai_enricher", {})

        # Get all user history
        history = job_status_service.get_user_status_history(test_user_id)

        assert len(history) == 3
        # Should be ordered by created_at ASC (oldest first)
        # The last entry should be the most recent (updated_by_ai for job1)
        assert history[-1]["jsearch_job_id"] == "job1"
        assert history[-1]["status"] == "updated_by_ai"

    def test_get_job_status_history_returns_all_users(self, job_status_service, test_database):
        """Test that get_job_status_history returns history for all users."""
        import psycopg2

        # Create two test users
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
                    VALUES ('user1', 'user1@test.com', 'hash1', 'user'),
                           ('user2', 'user2@test.com', 'hash2', 'user')
                    RETURNING user_id
                    """
                )
                user_ids = [row[0] for row in cur.fetchall()]
                user1_id, user2_id = user_ids[0], user_ids[1]

                # Create history for same job by different users
                job_status_service.record_job_found("shared_job", user1_id)
                job_status_service.record_job_found("shared_job", user2_id)

                # Get all job history
                history = job_status_service.get_job_status_history("shared_job")

                assert len(history) == 2
                assert {h["user_id"] for h in history} == {user1_id, user2_id}
        finally:
            conn.close()

    def test_history_metadata_stores_json_correctly(
        self, job_status_service, test_user_id, test_job_id
    ):
        """Test that metadata is stored and retrieved as JSON correctly."""
        complex_metadata = {
            "campaign_id": 1,
            "skills_extracted": ["Python", "SQL", "Airflow"],
            "enrichment_details": {"model": "gpt-4", "cost": 0.05},
        }

        history_id = job_status_service.record_status_history(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            status="updated_by_ai",
            change_type="enrichment",
            changed_by="ai_enricher",
            metadata=complex_metadata,
        )

        assert history_id is not None

        # Verify metadata is correctly stored and retrieved
        history = job_status_service.get_status_history(test_job_id, test_user_id)
        assert len(history) == 1
        retrieved_metadata = history[0]["metadata"]
        assert retrieved_metadata["campaign_id"] == 1
        assert retrieved_metadata["skills_extracted"] == ["Python", "SQL", "Airflow"]
        assert retrieved_metadata["enrichment_details"]["model"] == "gpt-4"
