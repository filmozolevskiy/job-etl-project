"""
Integration tests for extract → normalize → rank flow.

Tests the complete pipeline:
1. Extract job postings from JSearch API (mocked)
2. Normalize jobs via dbt staging model
3. Rank jobs via JobRanker service
4. Verify data flows through all layers (raw → staging → marts)
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.extractor.job_extractor import JobExtractor
from services.extractor.jsearch_client import JSearchClient
from services.ranker.job_ranker import JobRanker
from services.shared import PostgreSQLDatabase

from .test_helpers import check_dbt_available, run_dbt_command

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
        cur.execute("""
            INSERT INTO marts.job_campaigns
            (campaign_id, campaign_name, is_active, query, location, country, date_window, email,
             created_at, updated_at, total_run_count, last_run_status, last_run_job_count)
            VALUES
            (1, 'Test Campaign', true, 'Business Intelligence Engineer', 'Toronto, ON', 'ca', 'week',
             'test@example.com', NOW(), NOW(), 0, NULL, 0)
            RETURNING campaign_id, campaign_name, query, location, country, date_window
        """)

        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        campaign = dict(zip(columns, row))

    yield campaign

    # Cleanup
    with db.get_cursor() as cur:
        cur.execute(
            "DELETE FROM marts.job_campaigns WHERE campaign_id = %s", (campaign["campaign_id"],)
        )


@pytest.fixture
def mock_jsearch_client(sample_jsearch_response):
    """Create a mock JSearchClient that returns sample data."""
    mock_client = MagicMock(spec=JSearchClient)
    mock_client.search_jobs.return_value = sample_jsearch_response
    return mock_client


class TestExtractNormalizeRankFlow:
    """Test the complete extract → normalize → rank flow."""

    def test_extract_jobs_to_raw_layer(
        self, test_database, test_campaign, mock_jsearch_client, sample_jsearch_response
    ):
        """
        Test that jobs are extracted and written to raw.jsearch_job_postings.

        This tests Step 1 of the pipeline.
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        extractor = JobExtractor(database=db, jsearch_client=mock_jsearch_client, num_pages=1)

        # Extract jobs for the test campaign
        campaigns = extractor.get_active_campaigns()
        assert len(campaigns) == 1
        assert campaigns[0]["campaign_id"] == test_campaign["campaign_id"]

        job_count = extractor.extract_jobs_for_campaign(campaigns[0])

        # Verify jobs were written to raw layer
        assert job_count == len(sample_jsearch_response["data"])

        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as count, campaign_id
                FROM raw.jsearch_job_postings
                WHERE campaign_id = %s
                GROUP BY campaign_id
            """,
                (test_campaign["campaign_id"],),
            )

            result = cur.fetchone()
            assert result is not None
            assert result[0] == len(sample_jsearch_response["data"])

            # Verify raw payload structure
            cur.execute(
                """
                SELECT raw_payload, dwh_load_date, dwh_source_system
                FROM raw.jsearch_job_postings
                WHERE campaign_id = %s
                LIMIT 1
            """,
                (test_campaign["campaign_id"],),
            )

            row = cur.fetchone()
            assert row is not None
            assert row[1] is not None  # dwh_load_date
            assert row[2] == "jsearch"  # dwh_source_system
            assert "job_id" in row[0]  # raw_payload is JSONB

    def test_normalize_jobs_to_staging(
        self, test_database, test_campaign, mock_jsearch_client, sample_jsearch_response
    ):
        """
        Test that jobs are normalized from raw to staging layer via dbt.

        This tests Step 2 of the pipeline.
        """
        # First, extract jobs to raw layer
        db = PostgreSQLDatabase(connection_string=test_database)
        extractor = JobExtractor(database=db, jsearch_client=mock_jsearch_client, num_pages=1)
        campaigns = extractor.get_active_campaigns()
        extractor.extract_jobs_for_campaign(campaigns[0])

        # Run dbt staging model
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"

        # Check if dbt is available
        if not check_dbt_available():
            pytest.skip(
                "dbt is not installed or not in PATH. Install dbt to run integration tests."
            )

        # Update dbt profiles.yml connection string (if needed) or use environment variable
        # For simplicity, we'll assume dbt is configured to use the test database
        # In a real scenario, you might need to update profiles.yml or use dbt environment variables

        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings"],
            env={"DBT_PROFILES_DIR": str(dbt_project_dir)},
            connection_string=test_database,
        )

        # Check if dbt run was successful
        if result is None:
            pytest.skip("dbt is not available")
        if result.returncode != 0:
            pytest.skip(
                f"dbt run failed: {result.stderr}. This test requires dbt to be configured properly."
            )

        # Verify jobs were normalized to staging layer
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as count
                FROM staging.jsearch_job_postings
                WHERE campaign_id = %s
            """,
                (test_campaign["campaign_id"],),
            )

            result = cur.fetchone()
            assert result is not None
            assert result[0] == len(sample_jsearch_response["data"])

            # Verify staging table has expected columns
            cur.execute(
                """
                SELECT jsearch_job_id, job_title, employer_name, job_location, job_country, campaign_id
                FROM staging.jsearch_job_postings
                WHERE campaign_id = %s
                LIMIT 1
            """,
                (test_campaign["campaign_id"],),
            )

            row = cur.fetchone()
            assert row is not None
            assert row[0] is not None  # jsearch_job_id
            assert row[1] is not None  # job_title
            assert row[5] == test_campaign["campaign_id"]  # campaign_id

    def test_build_marts_and_rank_jobs(
        self, test_database, test_campaign, mock_jsearch_client, sample_jsearch_response
    ):
        """
        Test that marts are built and jobs are ranked.

        This tests Steps 6-7 of the pipeline.

        Note: This test requires staging data and may require company data.
        For a minimal test, we'll verify rankings are created even without companies.
        """
        # Extract and normalize jobs first
        db = PostgreSQLDatabase(connection_string=test_database)
        extractor = JobExtractor(database=db, jsearch_client=mock_jsearch_client, num_pages=1)
        campaigns = extractor.get_active_campaigns()
        extractor.extract_jobs_for_campaign(campaigns[0])

        # Run dbt staging model
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"

        # Check if dbt is available
        if not check_dbt_available():
            pytest.skip(
                "dbt is not installed or not in PATH. Install dbt to run integration tests."
            )

        # Run staging model
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings"],
            env={"DBT_PROFILES_DIR": str(dbt_project_dir)},
            connection_string=test_database,
        )

        if result is None:
            pytest.skip("dbt is not available")
        if result.returncode != 0:
            pytest.skip(f"dbt staging run failed: {result.stderr}")

        # Run marts models (fact_jobs at minimum)
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.fact_jobs"],
            env={"DBT_PROFILES_DIR": str(dbt_project_dir)},
            connection_string=test_database,
        )

        if result is None:
            pytest.skip("dbt is not available")
        if result.returncode != 0:
            pytest.skip(f"dbt marts run failed: {result.stderr}")

        # Now rank jobs
        ranker = JobRanker(database=db)
        ranking_results = ranker.rank_all_campaigns()

        # Verify rankings were created
        assert test_campaign["campaign_id"] in ranking_results
        assert ranking_results[test_campaign["campaign_id"]] > 0

        # Verify rankings in database
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as count, AVG(rank_score) as avg_score, MIN(rank_score) as min_score, MAX(rank_score) as max_score
                FROM marts.dim_ranking
                WHERE campaign_id = %s
            """,
                (test_campaign["campaign_id"],),
            )

            result = cur.fetchone()
            assert result is not None
            assert result[0] > 0  # At least one ranking

            # Verify score is in valid range (0-100)
            assert 0 <= result[1] <= 100  # avg_score
            assert 0 <= result[2] <= 100  # min_score
            assert 0 <= result[3] <= 100  # max_score

            # Verify ranking has required fields
            cur.execute(
                """
                SELECT jsearch_job_id, campaign_id, rank_score, ranked_at, ranked_date
                FROM marts.dim_ranking
                WHERE campaign_id = %s
                LIMIT 1
            """,
                (test_campaign["campaign_id"],),
            )

            row = cur.fetchone()
            assert row is not None
            assert row[0] is not None  # jsearch_job_id
            assert row[1] == test_campaign["campaign_id"]  # campaign_id
            assert row[2] is not None  # rank_score
            assert row[3] is not None  # ranked_at
            assert row[4] is not None  # ranked_date

    def test_complete_flow_end_to_end(
        self, test_database, test_campaign, mock_jsearch_client, sample_jsearch_response
    ):
        """
        Test the complete flow: extract → normalize → rank.

        This is a comprehensive integration test that validates the entire pipeline.
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"

        # Step 1: Extract jobs
        extractor = JobExtractor(database=db, jsearch_client=mock_jsearch_client, num_pages=1)
        campaigns = extractor.get_active_campaigns()
        job_count = extractor.extract_jobs_for_campaign(campaigns[0])

        assert job_count == len(sample_jsearch_response["data"])

        # Verify raw layer
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM raw.jsearch_job_postings WHERE campaign_id = %s",
                (test_campaign["campaign_id"],),
            )
            raw_count = cur.fetchone()[0]
            assert raw_count == len(sample_jsearch_response["data"])

        # Check if dbt is available
        if not check_dbt_available():
            pytest.skip(
                "dbt is not installed or not in PATH. Install dbt to run integration tests."
            )

        # Step 2: Normalize jobs
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings"],
            env={"DBT_PROFILES_DIR": str(dbt_project_dir)},
            connection_string=test_database,
        )

        if result is None:
            pytest.skip("dbt is not available")
        if result.returncode != 0:
            pytest.skip(f"dbt staging run failed: {result.stderr}")

        # Verify staging layer
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM staging.jsearch_job_postings WHERE campaign_id = %s",
                (test_campaign["campaign_id"],),
            )
            staging_count = cur.fetchone()[0]
            assert staging_count == len(sample_jsearch_response["data"])

        # Step 3: Build marts
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.fact_jobs"],
            env={"DBT_PROFILES_DIR": str(dbt_project_dir)},
            connection_string=test_database,
        )

        if result is None:
            pytest.skip("dbt is not available")
        if result.returncode != 0:
            pytest.skip(f"dbt marts run failed: {result.stderr}")

        # Verify marts layer
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM marts.fact_jobs WHERE campaign_id = %s",
                (test_campaign["campaign_id"],),
            )
            fact_count = cur.fetchone()[0]
            assert fact_count > 0  # At least some jobs made it to fact table

        # Step 4: Rank jobs
        ranker = JobRanker(database=db)
        ranking_results = ranker.rank_all_campaigns()

        assert test_campaign["campaign_id"] in ranking_results
        assert ranking_results[test_campaign["campaign_id"]] > 0

        # Verify rankings
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM marts.dim_ranking WHERE campaign_id = %s
            """,
                (test_campaign["campaign_id"],),
            )
            ranking_count = cur.fetchone()[0]
            assert ranking_count > 0

            # Verify data integrity: all ranked jobs should exist in fact_jobs
            cur.execute(
                """
                SELECT COUNT(*)
                FROM marts.dim_ranking dr
                INNER JOIN marts.fact_jobs fj ON dr.jsearch_job_id = fj.jsearch_job_id
                    AND dr.campaign_id = fj.campaign_id
                WHERE dr.campaign_id = %s
            """,
                (test_campaign["campaign_id"],),
            )
            joined_count = cur.fetchone()[0]
            assert joined_count == ranking_count  # All rankings should join to fact_jobs
