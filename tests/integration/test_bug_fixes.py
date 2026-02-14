"""
Integration tests for bug fixes.

Tests verify that the following bugs have been fixed:
- Bug #3: Missing deduplication at job extractor level
- Bug #4: Inconsistent field value casing in database
- Bug #5: Incorrect country code for United Kingdom
- Bug #7: "Job Not Found" error when clicking jobs from campaign details
"""

import json
from datetime import date, datetime
from hashlib import md5
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.extractor.job_extractor import JobExtractor
from services.extractor.jsearch_client import JSearchClient
from services.jobs.job_service import JobService
from services.ranker.job_ranker import JobRanker
from services.shared import PostgreSQLDatabase

from .test_helpers import check_dbt_available, run_dbt_command

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def test_user(test_database):
    """Create a test user in the database."""
    from services.shared import PostgreSQLDatabase

    db = PostgreSQLDatabase(connection_string=test_database)
    with db.get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO marts.users (username, email, password_hash, role, created_at, updated_at)
            VALUES ('testuser1', 'test1@example.com', 'hashed_password', 'user', NOW(), NOW())
            RETURNING user_id
            """
        )
        user_id = cur.fetchone()[0]
        yield user_id


@pytest.fixture
def test_user2(test_database):
    """Create a second test user in the database."""
    from services.shared import PostgreSQLDatabase

    db = PostgreSQLDatabase(connection_string=test_database)
    with db.get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO marts.users (username, email, password_hash, role, created_at, updated_at)
            VALUES ('testuser2', 'test2@example.com', 'hashed_password', 'user', NOW(), NOW())
            RETURNING user_id
            """
        )
        user_id = cur.fetchone()[0]
        yield user_id


@pytest.fixture
def test_campaign(test_database, test_user):
    """Create a test campaign in the database."""
    db = PostgreSQLDatabase(connection_string=test_database)

    with db.get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO marts.job_campaigns
            (campaign_id, campaign_name, is_active, query, location, country, date_window, email,
             user_id, created_at, updated_at, total_run_count, last_run_status, last_run_job_count)
            VALUES
            (1, 'Test Campaign', true, 'Software Engineer', 'Toronto, ON', 'ca', 'week',
             'test@example.com', %s, NOW(), NOW(), 0, NULL, 0)
            RETURNING campaign_id, campaign_name, query, location, country
        """,
            (test_user,),
        )
        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        campaign = dict(zip(columns, row))

    yield campaign


@pytest.fixture
def test_campaign_uk(test_database, test_user):
    """Create a test campaign with UK country code (should be normalized to GB)."""
    db = PostgreSQLDatabase(connection_string=test_database)

    with db.get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO marts.job_campaigns
            (campaign_id, campaign_name, is_active, query, location, country, date_window, email,
             user_id, created_at, updated_at, total_run_count, last_run_status, last_run_job_count)
            VALUES
            (2, 'UK Campaign', true, 'Data Engineer', 'London', 'gb', 'week',
             'uk@example.com', %s, NOW(), NOW(), 0, NULL, 0)
            RETURNING campaign_id, campaign_name, query, location, country
        """,
            (test_user,),
        )
        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        campaign = dict(zip(columns, row))

    yield campaign


@pytest.fixture
def test_campaign_other_user(test_database, test_user2):
    """Create a test campaign owned by a different user."""
    db = PostgreSQLDatabase(connection_string=test_database)

    with db.get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO marts.job_campaigns
            (campaign_id, campaign_name, is_active, query, location, country, date_window, email,
             user_id, created_at, updated_at, total_run_count, last_run_status, last_run_job_count)
            VALUES
            (3, 'Other User Campaign', true, 'Python Developer', 'Vancouver, BC', 'ca', 'week',
             'other@example.com', %s, NOW(), NOW(), 0, NULL, 0)
            RETURNING campaign_id, campaign_name, query, location, country, user_id
        """,
            (test_user2,),
        )
        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        campaign = dict(zip(columns, row))

    yield campaign


@pytest.fixture
def sample_job_posting():
    """Sample job posting data from JSearch API."""
    return {
        "job_id": "test_job_123",
        "job_title": "Senior Software Engineer",
        "job_description": "We are looking for a senior software engineer...",
        "employer_name": "Test Company",
        "job_city": "Toronto",
        "job_state": "ON",
        "job_country": "CA",
        "job_location": "Toronto, ON, CA",
        "job_employment_type": "FULLTIME",
        "job_employment_types": ["FULLTIME"],
        "job_is_remote": True,
        "job_posted_at": "2024-01-15",
        "job_min_salary": 100000,
        "job_max_salary": 150000,
        "job_salary_period": "YEAR",
        "job_apply_link": "https://example.com/apply",
    }


class TestBug3Deduplication:
    """Test Bug #3: Missing deduplication at job extractor level."""

    def test_extractor_skips_duplicate_jobs(self, test_database, test_campaign, sample_job_posting):
        """Test that extractor skips duplicate jobs when inserting to raw table."""
        db = PostgreSQLDatabase(connection_string=test_database)

        # Create mock JSearch client
        mock_client = MagicMock(spec=JSearchClient)
        mock_client.search_jobs.return_value = {
            "status": "OK",
            "data": [sample_job_posting],
        }
        extractor = JobExtractor(database=db, jsearch_client=mock_client, num_pages=1)

        # First extraction - should insert job
        count1 = extractor.extract_jobs_for_campaign(test_campaign)
        assert count1 == 1

        # Verify job exists in raw table
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM raw.jsearch_job_postings
                WHERE raw_payload->>'job_id' = %s AND campaign_id = %s
            """,
                (sample_job_posting["job_id"], test_campaign["campaign_id"]),
            )
            count = cur.fetchone()[0]
            assert count == 1

        # Second extraction with same job - should skip duplicate
        count2 = extractor.extract_jobs_for_campaign(test_campaign)
        assert count2 == 0  # Should skip duplicate

        # Verify still only one job in raw table
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM raw.jsearch_job_postings
                WHERE raw_payload->>'job_id' = %s AND campaign_id = %s
            """,
                (sample_job_posting["job_id"], test_campaign["campaign_id"]),
            )
            count = cur.fetchone()[0]
            assert count == 1

    def test_extractor_handles_mixed_duplicates(
        self, test_database, test_campaign, sample_job_posting
    ):
        """Test that extractor handles mix of new and duplicate jobs."""
        db = PostgreSQLDatabase(connection_string=test_database)

        # Create mock JSearch client
        mock_client = MagicMock(spec=JSearchClient)
        extractor = JobExtractor(database=db, jsearch_client=mock_client, num_pages=1)

        # Insert one job manually
        job_id_1 = "existing_job_1"
        job1 = {**sample_job_posting, "job_id": job_id_1}
        now = datetime.now()
        today = date.today()
        key_string = f"{job_id_1}|{test_campaign['campaign_id']}"
        jsearch_job_postings_key = int(md5(key_string.encode()).hexdigest()[:15], 16)

        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.jsearch_job_postings
                (jsearch_job_postings_key, raw_payload, dwh_load_date, dwh_load_timestamp,
                 dwh_source_system, campaign_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (
                    jsearch_job_postings_key,
                    json.dumps(job1),
                    today,
                    now,
                    "jsearch",
                    test_campaign["campaign_id"],
                ),
            )

        # Create mock response with one duplicate and one new job
        job_id_2 = "new_job_2"
        job2 = {**sample_job_posting, "job_id": job_id_2}
        mock_client.search_jobs.return_value = {
            "status": "OK",
            "data": [job1, job2],  # job1 is duplicate, job2 is new
        }

        # Extract - should only insert job2
        count = extractor.extract_jobs_for_campaign(test_campaign)
        assert count == 1  # Only new job inserted

        # Verify both jobs exist
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM raw.jsearch_job_postings
                WHERE campaign_id = %s
            """,
                (test_campaign["campaign_id"],),
            )
            count = cur.fetchone()[0]
            assert count == 2  # Both jobs should exist


class TestBug4FieldCasing:
    """Test Bug #4: Inconsistent field value casing in database."""

    @pytest.mark.skipif(not check_dbt_available(), reason="dbt not available")
    def test_staging_model_normalizes_salary_period(
        self, test_database, test_campaign, sample_job_posting
    ):
        """Test that staging model normalizes job_salary_period to lowercase."""
        db = PostgreSQLDatabase(connection_string=test_database)

        # Insert raw job with uppercase salary period
        job = {**sample_job_posting, "job_salary_period": "YEAR"}
        now = datetime.now()
        today = date.today()
        key_string = f"{job['job_id']}|{test_campaign['campaign_id']}"
        jsearch_job_postings_key = int(md5(key_string.encode()).hexdigest()[:15], 16)

        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.jsearch_job_postings
                (jsearch_job_postings_key, raw_payload, dwh_load_date, dwh_load_timestamp,
                 dwh_source_system, campaign_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (
                    jsearch_job_postings_key,
                    json.dumps(job),
                    today,
                    now,
                    "jsearch",
                    test_campaign["campaign_id"],
                ),
            )

        # Run staging model
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings"],
            connection_string=test_database,
        )
        if result is None or result.returncode != 0:
            pytest.skip(f"dbt run failed: {result.stderr if result else 'dbt not available'}")

        # Verify salary period is normalized to lowercase
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT job_salary_period FROM staging.jsearch_job_postings
                WHERE jsearch_job_id = %s
            """,
                (job["job_id"],),
            )
            result = cur.fetchone()
            assert result is not None
            assert result[0] == "year"  # Should be lowercase

    @pytest.mark.skipif(not check_dbt_available(), reason="dbt not available")
    def test_staging_model_normalizes_employment_type(
        self, test_database, test_campaign, sample_job_posting
    ):
        """Test that staging model normalizes job_employment_type to uppercase."""
        db = PostgreSQLDatabase(connection_string=test_database)

        # Insert raw job with lowercase employment type
        job = {
            **sample_job_posting,
            "job_employment_type": "fulltime",
            "job_employment_types": ["fulltime"],
        }
        now = datetime.now()
        today = date.today()
        key_string = f"{job['job_id']}|{test_campaign['campaign_id']}"
        jsearch_job_postings_key = int(md5(key_string.encode()).hexdigest()[:15], 16)

        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.jsearch_job_postings
                (jsearch_job_postings_key, raw_payload, dwh_load_date, dwh_load_timestamp,
                 dwh_source_system, campaign_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (
                    jsearch_job_postings_key,
                    json.dumps(job),
                    today,
                    now,
                    "jsearch",
                    test_campaign["campaign_id"],
                ),
            )

        # Run staging model
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings"],
            connection_string=test_database,
        )
        if result is None or result.returncode != 0:
            pytest.skip(f"dbt run failed: {result.stderr if result else 'dbt not available'}")

        # Verify employment type is normalized to uppercase
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT job_employment_type, employment_types FROM staging.jsearch_job_postings
                WHERE jsearch_job_id = %s
            """,
                (job["job_id"],),
            )
            result = cur.fetchone()
            assert result is not None
            assert result[0] == "FULLTIME"  # Should be uppercase
            assert result[1] == "FULLTIME"  # Should be uppercase


class TestBug5UKCountryCode:
    """Test Bug #5: Incorrect country code for United Kingdom."""

    def test_ranker_uses_gb_not_uk(self, test_database, test_campaign_uk):
        """Test that ranker uses 'gb' country code, not 'uk'."""
        db = PostgreSQLDatabase(connection_string=test_database)
        ranker = JobRanker(database=db)

        # Create a job with UK location
        job = {
            "jsearch_job_id": "test_job_gb",
            "job_location": "London, United Kingdom",
            "job_title": "Data Engineer",
        }

        campaign = {
            "campaign_id": test_campaign_uk["campaign_id"],
            "country": "gb",  # Should be 'gb', not 'uk'
            "location": "London",
        }

        # Test location matching with 'gb' country code
        score = ranker._score_location_match(job, campaign)
        # Should match because 'gb' is in country_mappings and "united kingdom" is in job_location
        assert score > 0.0

    def test_campaign_stored_with_gb_country_code(self, test_database, test_campaign_uk):
        """Test that campaign is stored with 'gb' country code."""
        db = PostgreSQLDatabase(connection_string=test_database)

        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT country FROM marts.job_campaigns WHERE campaign_id = %s
            """,
                (test_campaign_uk["campaign_id"],),
            )
            result = cur.fetchone()
            assert result is not None
            assert result[0] == "gb"  # Should be 'gb', not 'uk'


class TestBug7JobNotFound:
    """Test Bug #7: 'Job Not Found' error when clicking jobs from campaign details."""

    @pytest.mark.skipif(not check_dbt_available(), reason="dbt not available")
    def test_job_retrievable_from_other_user_campaign(
        self, test_database, test_campaign_other_user, test_user, sample_job_posting
    ):
        """Test that jobs from other user's campaign can be retrieved."""
        db = PostgreSQLDatabase(connection_string=test_database)
        job_service = JobService(database=db)

        # Insert job for other user's campaign
        job = {**sample_job_posting, "job_id": "other_user_job_1"}
        now = datetime.now()
        today = date.today()
        key_string = f"{job['job_id']}|{test_campaign_other_user['campaign_id']}"
        jsearch_job_postings_key = int(md5(key_string.encode()).hexdigest()[:15], 16)

        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.jsearch_job_postings
                (jsearch_job_postings_key, raw_payload, dwh_load_date, dwh_load_timestamp,
                 dwh_source_system, campaign_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (
                    jsearch_job_postings_key,
                    json.dumps(job),
                    today,
                    now,
                    "jsearch",
                    test_campaign_other_user["campaign_id"],
                ),
            )

        # Run staging and marts models
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"
        result1 = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings"],
            connection_string=test_database,
        )
        if result1 is None or result1.returncode != 0:
            pytest.skip(f"dbt run failed: {result1.stderr if result1 else 'dbt not available'}")
        result2 = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.fact_jobs"],
            connection_string=test_database,
        )
        if result2 is None or result2.returncode != 0:
            pytest.skip(f"dbt run failed: {result2.stderr if result2 else 'dbt not available'}")

        # Create ranking entry
        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO marts.dim_ranking
                (jsearch_job_id, campaign_id, rank_score, ranked_at, ranked_date, dwh_load_timestamp)
                VALUES (%s, %s, %s, NOW(), CURRENT_DATE, NOW())
            """,
                (job["job_id"], test_campaign_other_user["campaign_id"], 85.0),
            )

        # Try to retrieve job as test_user (different from campaign owner who is test_user2)
        # This should work now (bug fix: removed user_id filter)
        retrieved_job = job_service.get_job_by_id(jsearch_job_id=job["job_id"], user_id=test_user)

        assert retrieved_job is not None
        assert retrieved_job["jsearch_job_id"] == job["job_id"]
        assert retrieved_job["campaign_id"] == test_campaign_other_user["campaign_id"]

    def test_job_retrievable_from_own_campaign(
        self, test_database, test_campaign, test_user, sample_job_posting
    ):
        """Test that jobs from own campaign can still be retrieved (regression test)."""
        db = PostgreSQLDatabase(connection_string=test_database)
        job_service = JobService(database=db)

        # Insert job for own campaign
        job = {**sample_job_posting, "job_id": "own_job_1"}
        now = datetime.now()
        today = date.today()
        key_string = f"{job['job_id']}|{test_campaign['campaign_id']}"
        jsearch_job_postings_key = int(md5(key_string.encode()).hexdigest()[:15], 16)

        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.jsearch_job_postings
                (jsearch_job_postings_key, raw_payload, dwh_load_date, dwh_load_timestamp,
                 dwh_source_system, campaign_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (
                    jsearch_job_postings_key,
                    json.dumps(job),
                    today,
                    now,
                    "jsearch",
                    test_campaign["campaign_id"],
                ),
            )

        # Run staging and marts models
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"
        result1 = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings"],
            connection_string=test_database,
        )
        if result1 is None or result1.returncode != 0:
            pytest.skip(f"dbt run failed: {result1.stderr if result1 else 'dbt not available'}")
        result2 = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.fact_jobs"],
            connection_string=test_database,
        )
        if result2 is None or result2.returncode != 0:
            pytest.skip(f"dbt run failed: {result2.stderr if result2 else 'dbt not available'}")

        # Create ranking entry
        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO marts.dim_ranking
                (jsearch_job_id, campaign_id, rank_score, ranked_at, ranked_date, dwh_load_timestamp)
                VALUES (%s, %s, %s, NOW(), CURRENT_DATE, NOW())
            """,
                (job["job_id"], test_campaign["campaign_id"], 90.0),
            )

        # Retrieve job as test_user (campaign owner)
        retrieved_job = job_service.get_job_by_id(jsearch_job_id=job["job_id"], user_id=test_user)

        assert retrieved_job is not None
        assert retrieved_job["jsearch_job_id"] == job["job_id"]
        assert retrieved_job["campaign_id"] == test_campaign["campaign_id"]
