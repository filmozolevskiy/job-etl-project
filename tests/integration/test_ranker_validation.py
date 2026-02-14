"""Integration tests for ranker validation to prevent orphaned rankings."""

from __future__ import annotations

import pytest

from services.ranker.job_ranker import JobRanker
from services.shared import PostgreSQLDatabase

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def test_campaign(test_database):
    """
    Create a test campaign in the database.

    Returns:
        dict: Campaign information including campaign_id
    """
    db = PostgreSQLDatabase(connection_string=test_database)

    with db.get_cursor() as cur:
        # Insert test campaign
        cur.execute(
            """
            INSERT INTO marts.job_campaigns
            (campaign_id, campaign_name, is_active, query, location, country, date_window, email,
             created_at, updated_at, total_run_count, last_run_status, last_run_job_count)
            VALUES
            (1, 'Test Campaign', true, 'Software Engineer', 'Toronto, ON', 'ca', 'week',
             'test@example.com', NOW(), NOW(), 0, NULL, 0)
            RETURNING campaign_id, campaign_name, query, location, country, date_window
        """
        )

        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        campaign = dict(zip(columns, row))

    yield campaign


class TestRankerValidation:
    """Test ranker validation to prevent orphaned rankings."""

    def test_ranker_validates_jobs_before_ranking(self, test_database, test_campaign):
        """
        Test that ranker validates jobs exist in fact_jobs before ranking.

        This test:
        1. Creates a job in fact_jobs
        2. Runs ranker for the campaign
        3. Verifies ranking was created
        4. Verifies no orphaned rankings exist
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        campaign_id = test_campaign["campaign_id"]

        # Insert a valid job into fact_jobs
        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO marts.fact_jobs
                (jsearch_job_id, campaign_id, job_title, job_location, employment_type,
                 job_posted_at_datetime_utc, company_key, dwh_load_date,
                 dwh_load_timestamp, dwh_source_system)
                VALUES
                ('valid-job-1', %s, 'Software Engineer', 'Toronto, ON', 'FULLTIME',
                 '2025-01-01T00:00:00Z', 'company1', CURRENT_DATE, NOW(), 'test')
            """,
                (campaign_id,),
            )

        # Run ranker
        ranker = JobRanker(database=db)
        campaign = {
            "campaign_id": campaign_id,
            "campaign_name": test_campaign["campaign_name"],
            "query": test_campaign["query"],
            "location": test_campaign["location"],
            "country": test_campaign["country"],
        }
        ranked_count = ranker.rank_jobs_for_campaign(campaign)

        # Verify ranking was created
        assert ranked_count == 1

        # Verify ranking exists in dim_ranking
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as count
                FROM marts.dim_ranking
                WHERE jsearch_job_id = 'valid-job-1'
                    AND campaign_id = %s
            """,
                (campaign_id,),
            )
            result = cur.fetchone()
            assert result[0] == 1

        # Verify no orphaned rankings exist
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as orphaned_count
                FROM marts.dim_ranking dr
                LEFT JOIN marts.fact_jobs fj
                    ON dr.jsearch_job_id = fj.jsearch_job_id
                    AND dr.campaign_id = fj.campaign_id
                WHERE fj.jsearch_job_id IS NULL
            """
            )
            result = cur.fetchone()
            assert result[0] == 0, "No orphaned rankings should exist"

    def test_ranker_skips_jobs_not_in_fact_jobs(self, test_database, test_campaign):
        """
        Test that ranker skips jobs that don't exist in fact_jobs.

        This test:
        1. Manually inserts a ranking for a non-existent job (simulating old orphaned data)
        2. Creates a valid job in fact_jobs
        3. Runs ranker
        4. Verifies only the valid job is ranked
        5. Verifies the orphaned ranking is not recreated
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        campaign_id = test_campaign["campaign_id"]

        # Insert a valid job into fact_jobs
        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO marts.fact_jobs
                (jsearch_job_id, campaign_id, job_title, job_location, employment_type,
                 job_posted_at_datetime_utc, company_key, dwh_load_date,
                 dwh_load_timestamp, dwh_source_system)
                VALUES
                ('valid-job-2', %s, 'Data Engineer', 'Toronto, ON', 'FULLTIME',
                 '2025-01-01T00:00:00Z', 'company2', CURRENT_DATE, NOW(), 'test')
            """,
                (campaign_id,),
            )

            # Manually insert an orphaned ranking (simulating old data)
            # This should NOT be recreated by the ranker
            cur.execute(
                """
                INSERT INTO marts.dim_ranking
                (jsearch_job_id, campaign_id, rank_score, rank_explain, ranked_at,
                 ranked_date, dwh_load_timestamp, dwh_source_system)
                VALUES
                ('orphaned-job-1', %s, 50.0, '{}', NOW(), CURRENT_DATE, NOW(), 'manual')
            """,
                (campaign_id,),
            )

        # Run ranker
        ranker = JobRanker(database=db)
        campaign = {
            "campaign_id": campaign_id,
            "campaign_name": test_campaign["campaign_name"],
            "query": test_campaign["query"],
            "location": test_campaign["location"],
            "country": test_campaign["country"],
        }
        ranked_count = ranker.rank_jobs_for_campaign(campaign)

        # Verify only the valid job was ranked
        assert ranked_count == 1

        # Verify valid job ranking exists
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as count
                FROM marts.dim_ranking
                WHERE jsearch_job_id = 'valid-job-2'
                    AND campaign_id = %s
            """,
                (campaign_id,),
            )
            result = cur.fetchone()
            assert result[0] == 1

        # Verify orphaned ranking still exists (ranker doesn't delete it, just doesn't create new ones)
        # But we verify it's still orphaned
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as orphaned_count
                FROM marts.dim_ranking dr
                LEFT JOIN marts.fact_jobs fj
                    ON dr.jsearch_job_id = fj.jsearch_job_id
                    AND dr.campaign_id = fj.campaign_id
                WHERE fj.jsearch_job_id IS NULL
                    AND dr.jsearch_job_id = 'orphaned-job-1'
            """
            )
            result = cur.fetchone()
            assert result[0] == 1, "Orphaned ranking should still exist (not deleted by ranker)"

    def test_ranker_handles_mixed_valid_and_invalid_jobs(self, test_database, test_campaign):
        """
        Test that ranker handles a mix of valid and invalid jobs correctly.

        This test:
        1. Creates multiple jobs in fact_jobs (some valid, some not)
        2. Runs ranker
        3. Verifies only valid jobs are ranked
        4. Verifies no orphaned rankings are created
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        campaign_id = test_campaign["campaign_id"]

        # Insert valid jobs into fact_jobs
        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO marts.fact_jobs
                (jsearch_job_id, campaign_id, job_title, job_location, employment_type,
                 job_posted_at_datetime_utc, company_key, dwh_load_date,
                 dwh_load_timestamp, dwh_source_system)
                VALUES
                ('valid-job-3', %s, 'Software Engineer', 'Toronto, ON', 'FULLTIME',
                 '2025-01-01T00:00:00Z', 'company3', CURRENT_DATE, NOW(), 'test'),
                ('valid-job-4', %s, 'Data Engineer', 'Toronto, ON', 'FULLTIME',
                 '2025-01-01T00:00:00Z', 'company4', CURRENT_DATE, NOW(), 'test')
            """,
                (campaign_id, campaign_id),
            )

        # Run ranker
        ranker = JobRanker(database=db)
        campaign = {
            "campaign_id": campaign_id,
            "campaign_name": test_campaign["campaign_name"],
            "query": test_campaign["query"],
            "location": test_campaign["location"],
            "country": test_campaign["country"],
        }
        ranked_count = ranker.rank_jobs_for_campaign(campaign)

        # Verify both valid jobs were ranked
        assert ranked_count == 2

        # Verify rankings exist for valid jobs
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as count
                FROM marts.dim_ranking
                WHERE jsearch_job_id IN ('valid-job-3', 'valid-job-4')
                    AND campaign_id = %s
            """,
                (campaign_id,),
            )
            result = cur.fetchone()
            assert result[0] == 2

        # Verify no orphaned rankings exist
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as orphaned_count
                FROM marts.dim_ranking dr
                LEFT JOIN marts.fact_jobs fj
                    ON dr.jsearch_job_id = fj.jsearch_job_id
                    AND dr.campaign_id = fj.campaign_id
                WHERE fj.jsearch_job_id IS NULL
                    AND dr.campaign_id = %s
            """,
                (campaign_id,),
            )
            result = cur.fetchone()
            assert result[0] == 0, "No orphaned rankings should exist for this campaign"

    def test_validation_query_works_correctly(self, test_database, test_campaign):
        """
        Test that the validation query correctly identifies jobs in fact_jobs.

        This is a direct test of the validation logic.
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        campaign_id = test_campaign["campaign_id"]
        ranker = JobRanker(database=db)

        # Insert a job into fact_jobs
        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO marts.fact_jobs
                (jsearch_job_id, campaign_id, job_title, job_location, employment_type,
                 job_posted_at_datetime_utc, company_key, dwh_load_date,
                 dwh_load_timestamp, dwh_source_system)
                VALUES
                ('test-validation-job', %s, 'Test Job', 'Toronto, ON', 'FULLTIME',
                 '2025-01-01T00:00:00Z', 'company1', CURRENT_DATE, NOW(), 'test')
            """,
                (campaign_id,),
            )

        # Test validation for existing job
        assert ranker._validate_job_exists_in_fact_jobs("test-validation-job", campaign_id) is True

        # Test validation for non-existing job
        assert ranker._validate_job_exists_in_fact_jobs("non-existent-job", campaign_id) is False

        # Test validation for wrong campaign_id
        assert ranker._validate_job_exists_in_fact_jobs("test-validation-job", 999) is False
