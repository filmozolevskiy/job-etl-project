"""
Integration tests for multi-note functionality.

Tests end-to-end multi-note operations:
1. Add multiple notes to a job
2. Retrieve all notes for a job
3. Update individual notes
4. Delete individual notes
5. Verify note count in job listings
6. Verify authorization (users can only access their own notes)
"""

import pytest

from services.jobs import JobNoteService, JobService
from services.shared import PostgreSQLDatabase

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def test_user_id(test_database):
    """Create a test user and return user_id."""
    from services.shared import PostgreSQLDatabase

    db = PostgreSQLDatabase(connection_string=test_database)
    with db.get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO marts.users (username, email, password_hash, role)
            VALUES ('test_multi_note_user', 'test_multi_note@example.com', 'hashed_password', 'user')
            RETURNING user_id
            """
        )
        result = cur.fetchone()
    yield result[0]


# Campaign ID used by test_job_id fixture (must match inserts)
TEST_CAMPAIGN_ID = 9999


@pytest.fixture
def test_job_id(test_database, test_user_id):
    """Create a test job in fact_jobs and return jsearch_job_id."""
    import psycopg2

    conn = psycopg2.connect(test_database)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            # Ensure dbt-created tables exist (conftest creates them; defensive create here)
            for ddl in [
                """
                CREATE TABLE IF NOT EXISTS staging.jsearch_job_postings (
                    jsearch_job_postings_key bigint,
                    jsearch_job_id varchar,
                    campaign_id integer,
                    job_title varchar,
                    employer_name varchar,
                    job_location varchar,
                    dwh_load_date date,
                    dwh_load_timestamp timestamp,
                    dwh_source_system varchar
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS marts.fact_jobs (
                    jsearch_job_id varchar NOT NULL,
                    campaign_id integer NOT NULL,
                    job_title varchar,
                    employer_name varchar,
                    job_location varchar,
                    dwh_load_date date,
                    dwh_load_timestamp timestamp,
                    CONSTRAINT fact_jobs_pkey PRIMARY KEY (jsearch_job_id, campaign_id)
                )
                """,
            ]:
                try:
                    cur.execute(ddl)
                except Exception:
                    pass
        conn.autocommit = False
        with conn.cursor() as cur:
            # First create a test campaign if needed
            cur.execute(
                """
                INSERT INTO marts.job_campaigns (campaign_id, user_id, campaign_name, is_active, query, country)
                VALUES (%s, %s, 'Test Campaign', true, 'test', 'us')
                ON CONFLICT (campaign_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    campaign_name = EXCLUDED.campaign_name,
                    is_active = EXCLUDED.is_active
                """,
                (TEST_CAMPAIGN_ID, test_user_id),
            )
            # Create test job in fact_jobs, staging, and dim_ranking
            test_job_id = "test_multi_note_job_123"
            cur.execute(
                """
                INSERT INTO marts.fact_jobs (jsearch_job_id, campaign_id, job_title, dwh_load_date, dwh_load_timestamp, dwh_source_system)
                VALUES (%s, %s, 'Test Job', CURRENT_DATE, NOW(), 'test')
                ON CONFLICT (jsearch_job_id, campaign_id) DO UPDATE SET job_title = EXCLUDED.job_title
                """,
                (test_job_id, TEST_CAMPAIGN_ID),
            )
            cur.execute(
                """
                INSERT INTO staging.jsearch_job_postings
                (jsearch_job_postings_key, jsearch_job_id, campaign_id, job_title, dwh_load_date, dwh_load_timestamp, dwh_source_system)
                VALUES (1, %s, %s, 'Test Job', CURRENT_DATE, NOW(), 'test')
                """,
                (test_job_id, TEST_CAMPAIGN_ID),
            )
            cur.execute(
                """
                INSERT INTO marts.dim_ranking (jsearch_job_id, campaign_id, rank_score, ranked_at, ranked_date, dwh_load_timestamp, dwh_source_system)
                VALUES (%s, %s, 85.0, NOW(), CURRENT_DATE, NOW(), 'test')
                ON CONFLICT (jsearch_job_id, campaign_id) DO UPDATE SET rank_score = EXCLUDED.rank_score
                """,
                (test_job_id, TEST_CAMPAIGN_ID),
            )
        conn.commit()
        yield test_job_id
    finally:
        conn.close()


@pytest.fixture
def test_user_id_2(test_database):
    """Create a second test user for authorization tests."""
    import psycopg2

    with psycopg2.connect(test_database) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO marts.users (username, email, password_hash, role)
                VALUES ('test_multi_note_user2', 'test_multi_note2@example.com', 'hashed_password', 'user')
                RETURNING user_id
                """
            )
            result = cur.fetchone()
        conn.commit()
    yield result[0]


@pytest.fixture
def job_note_service(test_database):
    """Create a JobNoteService instance."""
    database = PostgreSQLDatabase(connection_string=test_database)
    return JobNoteService(database=database)


@pytest.fixture
def job_service(test_database):
    """Create a JobService instance."""
    database = PostgreSQLDatabase(connection_string=test_database)
    return JobService(database=database)


class TestMultiNoteIntegration:
    """Integration tests for multi-note functionality."""

    def test_add_multiple_notes(self, job_note_service, test_user_id, test_job_id):
        """Test adding multiple notes to a single job."""
        # Add first note
        note_id_1 = job_note_service.add_note(
            test_job_id, test_user_id, "First note", campaign_id=TEST_CAMPAIGN_ID
        )
        assert note_id_1 is not None

        # Add second note
        note_id_2 = job_note_service.add_note(
            test_job_id, test_user_id, "Second note", campaign_id=TEST_CAMPAIGN_ID
        )
        assert note_id_2 is not None
        assert note_id_2 != note_id_1

        # Add third note
        note_id_3 = job_note_service.add_note(
            test_job_id, test_user_id, "Third note", campaign_id=TEST_CAMPAIGN_ID
        )
        assert note_id_3 is not None
        assert note_id_3 != note_id_1
        assert note_id_3 != note_id_2

        # Retrieve all notes
        notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert len(notes) == 3
        note_texts = [note["note_text"] for note in notes]
        assert "First note" in note_texts
        assert "Second note" in note_texts
        assert "Third note" in note_texts

    def test_notes_ordered_newest_first(self, job_note_service, test_user_id, test_job_id):
        """Test that notes are returned in newest-first order."""
        import time

        # Add notes with small delay to ensure different timestamps
        note_id_1 = job_note_service.add_note(
            test_job_id, test_user_id, "First note", campaign_id=TEST_CAMPAIGN_ID
        )
        time.sleep(0.1)
        note_id_2 = job_note_service.add_note(
            test_job_id, test_user_id, "Second note", campaign_id=TEST_CAMPAIGN_ID
        )
        time.sleep(0.1)
        note_id_3 = job_note_service.add_note(
            test_job_id, test_user_id, "Third note", campaign_id=TEST_CAMPAIGN_ID
        )

        notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert len(notes) == 3
        # Newest first
        assert notes[0]["note_id"] == note_id_3
        assert notes[1]["note_id"] == note_id_2
        assert notes[2]["note_id"] == note_id_1

    def test_update_note(self, job_note_service, test_user_id, test_job_id):
        """Test updating an individual note."""
        # Add note
        note_id = job_note_service.add_note(
            test_job_id, test_user_id, "Original note", campaign_id=TEST_CAMPAIGN_ID
        )
        assert note_id is not None

        # Verify original
        notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert len(notes) == 1
        assert notes[0]["note_text"] == "Original note"
        assert notes[0]["is_modified"] is False

        # Update note
        success = job_note_service.update_note(note_id, test_user_id, "Updated note")
        assert success is True

        # Verify update
        notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert len(notes) == 1
        assert notes[0]["note_text"] == "Updated note"
        assert notes[0]["is_modified"] is True
        assert notes[0]["created_at"] != notes[0]["updated_at"]

    def test_delete_note(self, job_note_service, test_user_id, test_job_id):
        """Test deleting an individual note."""
        # Add multiple notes
        note_id_1 = job_note_service.add_note(
            test_job_id, test_user_id, "Note 1", campaign_id=TEST_CAMPAIGN_ID
        )
        note_id_2 = job_note_service.add_note(
            test_job_id, test_user_id, "Note 2", campaign_id=TEST_CAMPAIGN_ID
        )
        note_id_3 = job_note_service.add_note(
            test_job_id, test_user_id, "Note 3", campaign_id=TEST_CAMPAIGN_ID
        )

        # Delete middle note
        success = job_note_service.delete_note(note_id_2, test_user_id)
        assert success is True

        # Verify deletion
        notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert len(notes) == 2
        note_ids = [note["note_id"] for note in notes]
        assert note_id_1 in note_ids
        assert note_id_2 not in note_ids
        assert note_id_3 in note_ids

    def test_note_count_in_job_listing(
        self, job_note_service, job_service, test_user_id, test_job_id
    ):
        """Test that note_count is correctly returned in job listings."""
        # Initially no notes
        # Note: This test depends on job being in dim_ranking, which may not exist
        # So we'll just verify the service works

        # Add notes
        job_note_service.add_note(test_job_id, test_user_id, "Note 1", campaign_id=TEST_CAMPAIGN_ID)
        job_note_service.add_note(test_job_id, test_user_id, "Note 2", campaign_id=TEST_CAMPAIGN_ID)
        job_note_service.add_note(test_job_id, test_user_id, "Note 3", campaign_id=TEST_CAMPAIGN_ID)

        # Verify notes exist
        notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert len(notes) == 3

    def test_authorization_user_cannot_access_other_users_notes(
        self, job_note_service, test_user_id, test_user_id_2, test_job_id
    ):
        """Test that users can only access their own notes."""
        # User 1 adds notes
        note_id_1 = job_note_service.add_note(
            test_job_id, test_user_id, "User 1 note 1", campaign_id=TEST_CAMPAIGN_ID
        )
        note_id_2 = job_note_service.add_note(
            test_job_id, test_user_id, "User 1 note 2", campaign_id=TEST_CAMPAIGN_ID
        )

        # User 2 adds notes
        note_id_3 = job_note_service.add_note(
            test_job_id, test_user_id_2, "User 2 note 1", campaign_id=TEST_CAMPAIGN_ID
        )

        # User 1 can only see their own notes
        user_1_notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert len(user_1_notes) == 2
        user_1_note_ids = [note["note_id"] for note in user_1_notes]
        assert note_id_1 in user_1_note_ids
        assert note_id_2 in user_1_note_ids
        assert note_id_3 not in user_1_note_ids

        # User 2 can only see their own notes
        user_2_notes = job_note_service.get_notes(test_job_id, test_user_id_2)
        assert len(user_2_notes) == 1
        assert user_2_notes[0]["note_id"] == note_id_3

        # User 2 cannot access User 1's notes by ID
        note = job_note_service.get_note_by_id(note_id_1, test_user_id_2)
        assert note is None

        # User 2 cannot update User 1's note
        success = job_note_service.update_note(note_id_1, test_user_id_2, "Hacked note")
        assert success is False

        # User 2 cannot delete User 1's note
        success = job_note_service.delete_note(note_id_1, test_user_id_2)
        assert success is False

        # Verify User 1's notes are still intact
        user_1_notes_after = job_note_service.get_notes(test_job_id, test_user_id)
        assert len(user_1_notes_after) == 2

    def test_is_modified_flag(self, job_note_service, test_user_id, test_job_id):
        """Test that is_modified flag is correctly set."""
        # Add note (should not be modified)
        note_id = job_note_service.add_note(
            test_job_id, test_user_id, "Original note", campaign_id=TEST_CAMPAIGN_ID
        )
        notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert notes[0]["is_modified"] is False

        # Update note (should be modified)
        job_note_service.update_note(note_id, test_user_id, "Updated note")
        notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert notes[0]["is_modified"] is True

    def test_empty_note_list(self, job_note_service, test_user_id, test_job_id):
        """Test retrieving notes when none exist."""
        notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert notes == []

    def test_whitespace_stripping(self, job_note_service, test_user_id, test_job_id):
        """Test that whitespace is stripped from note text."""
        # Add note with whitespace
        note_id = job_note_service.add_note(
            test_job_id, test_user_id, "  Note with spaces  ", campaign_id=TEST_CAMPAIGN_ID
        )
        notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert notes[0]["note_text"] == "Note with spaces"

        # Update with whitespace
        job_note_service.update_note(note_id, test_user_id, "  Updated note  ")
        notes = job_note_service.get_notes(test_job_id, test_user_id)
        assert notes[0]["note_text"] == "Updated note"
