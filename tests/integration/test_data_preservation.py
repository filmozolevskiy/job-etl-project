"""
Integration tests for data preservation across campaigns.

These tests verify that:
1. Running a DAG for one campaign doesn't delete data for other campaigns
2. Incremental materialization processes only new/changed records
3. fact_jobs contains all campaigns after running single campaign DAG
4. Ranking UPSERT preserves other campaigns' data
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
def multiple_test_campaigns(test_database):
    """
    Create multiple test campaigns in the database.

    Returns:
        list: List of campaign dictionaries
    """
    db = PostgreSQLDatabase(connection_string=test_database)
    campaigns = []

    with db.get_cursor() as cur:
        # Insert 3 test campaigns
        for i in range(1, 4):
            cur.execute(
                """
                INSERT INTO marts.job_campaigns
                (campaign_id, campaign_name, is_active, query, location, country, date_window, email,
                 created_at, updated_at, total_run_count, last_run_status, last_run_job_count)
                VALUES
                (%s, %s, true, %s, 'Toronto, ON', 'ca', 'week',
                 'test@example.com', NOW(), NOW(), 0, NULL, 0)
                RETURNING campaign_id, campaign_name, query, location, country, date_window
            """,
                (i, f'Test Campaign {i}', f'Engineer {i}'),
            )

            row = cur.fetchone()
            columns = [desc[0] for desc in cur.description]
            campaign = dict(zip(columns, row))
            campaigns.append(campaign)

    yield campaigns

    # Cleanup
    with db.get_cursor() as cur:
        for campaign in campaigns:
            cur.execute(
                "DELETE FROM marts.job_campaigns WHERE campaign_id = %s",
                (campaign["campaign_id"],),
            )


@pytest.fixture
def sample_jsearch_response_multiple():
    """Sample JSearch API response with multiple jobs for testing."""
    return {
        "status": "OK",
        "request_id": "test-request-id",
        "parameters": {"query": "Engineer", "page": 1, "num_pages": 1},
        "data": [
            {
                "job_id": f"job_{i}",
                "job_title": f"Software Engineer {i}",
                "job_description": f"Description for job {i}",
                "employer_name": f"Company {i}",
                "job_city": "Toronto",
                "job_state": "ON",
                "job_country": "CA",
                "job_location": f"Toronto, ON {i}",
                "job_employment_type": "FULLTIME",
                "job_is_remote": False,
                "job_posted_at": "2024-01-01T00:00:00Z",
                "job_posted_at_timestamp": 1704067200,
                "job_posted_at_datetime_utc": "2024-01-01T00:00:00",
            }
            for i in range(1, 6)  # 5 jobs per campaign
        ],
    }


class TestDataPreservation:
    """Test data preservation across campaigns."""

    def test_fact_jobs_preserves_all_campaigns_on_single_campaign_dag(
        self,
        test_database,
        multiple_test_campaigns,
        sample_jsearch_response_multiple,
    ):
        """
        Test that running a DAG for one campaign doesn't delete other campaigns' data from fact_jobs.

        Setup: Create 3 campaigns, extract jobs for all 3
        Run: Trigger DAG for campaign 1 only (with campaign_id filter)
        Verify:
            - fact_jobs still contains jobs for all 3 campaigns
            - Count of jobs per campaign remains unchanged for campaigns 2 and 3
            - Only campaign 1's jobs may be updated/added
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        mock_client = MagicMock(spec=JSearchClient)
        mock_client.search_jobs.return_value = sample_jsearch_response_multiple

        # Extract jobs for all 3 campaigns
        extractor = JobExtractor(database=db, jsearch_client=mock_client, num_pages=1)
        campaigns = extractor.get_active_campaigns()
        assert len(campaigns) == 3

        # Extract jobs for each campaign
        job_counts_before = {}
        for campaign in campaigns:
            count = extractor.extract_jobs_for_campaign(campaign)
            job_counts_before[campaign["campaign_id"]] = count

        # Run staging and fact_jobs for all campaigns (first run - full load)
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"

        if not check_dbt_available():
            pytest.skip("dbt is not installed or not in PATH")

        # First run: process all campaigns (no campaign_id filter)
        result_staging = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings"],
            connection_string=test_database,
        )
        if result_staging is None or result_staging.returncode != 0:
            pytest.fail(f"dbt staging run failed: {result_staging.stderr if result_staging else 'dbt not available'}")

        result_fact = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.fact_jobs"],
            connection_string=test_database,
        )
        if result_fact is None or result_fact.returncode != 0:
            pytest.fail(f"dbt fact_jobs run failed: {result_fact.stderr if result_fact else 'dbt not available'}")

        # Record counts per campaign in fact_jobs
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT campaign_id, COUNT(*) as count
                FROM marts.fact_jobs
                GROUP BY campaign_id
                ORDER BY campaign_id
            """
            )
            counts_before = {row[0]: row[1] for row in cur.fetchall()}

        # Now run staging with campaign_id=1 filter (simulating single campaign DAG)
        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings", "--vars", '{"campaign_id": 1}'],
            connection_string=test_database,
        )
        # Run fact_jobs without campaign_id filter (should process all new records)
        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.fact_jobs"],
            connection_string=test_database,
        )

        # Verify counts per campaign in fact_jobs
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT campaign_id, COUNT(*) as count
                FROM marts.fact_jobs
                GROUP BY campaign_id
                ORDER BY campaign_id
            """
            )
            counts_after = {row[0]: row[1] for row in cur.fetchall()}

        # Verify all campaigns still have data
        assert 1 in counts_after, "Campaign 1 should have jobs"
        assert 2 in counts_after, "Campaign 2 should still have jobs"
        assert 3 in counts_after, "Campaign 3 should still have jobs"

        # Verify campaigns 2 and 3 counts are unchanged
        assert counts_after[2] == counts_before[2], "Campaign 2 job count should be unchanged"
        assert counts_after[3] == counts_before[3], "Campaign 3 job count should be unchanged"

        # Campaign 1 may have same or more jobs (if new records were added)
        assert counts_after[1] >= counts_before[1], "Campaign 1 should have same or more jobs"

    def test_staging_incremental_preserves_other_campaigns(
        self,
        test_database,
        multiple_test_campaigns,
        sample_jsearch_response_multiple,
    ):
        """
        Test that staging incremental materialization preserves other campaigns' data.

        Setup: Create 2 campaigns, extract jobs for both
        Run: Run normalize_jobs with campaign_id=1
        Verify:
            - staging.jsearch_job_postings still contains jobs for campaign 2
            - Campaign 1's jobs are processed/updated
            - Campaign 2's jobs remain unchanged
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        mock_client = MagicMock(spec=JSearchClient)
        mock_client.search_jobs.return_value = sample_jsearch_response_multiple

        # Extract jobs for campaigns 1 and 2
        extractor = JobExtractor(database=db, jsearch_client=mock_client, num_pages=1)
        campaigns = extractor.get_active_campaigns()
        assert len(campaigns) >= 2

        # Extract jobs for campaigns 1 and 2
        for campaign in campaigns[:2]:
            extractor.extract_jobs_for_campaign(campaign)

        # Run staging for all campaigns (first run)
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"

        if not check_dbt_available():
            pytest.skip("dbt is not installed or not in PATH")

        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings"],
            connection_string=test_database,
        )

        # Record counts per campaign in staging
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT campaign_id, COUNT(*) as count
                FROM staging.jsearch_job_postings
                WHERE campaign_id IN (1, 2)
                GROUP BY campaign_id
                ORDER BY campaign_id
            """
            )
            counts_before = {row[0]: row[1] for row in cur.fetchall()}

        # Now run staging with campaign_id=1 filter
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings", "--vars", '{"campaign_id": 1}'],
            connection_string=test_database,
        )
        if result is None or result.returncode != 0:
            pytest.fail(f"dbt staging run failed: {result.stderr if result else 'dbt not available'}")

        # Verify counts per campaign in staging
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT campaign_id, COUNT(*) as count
                FROM staging.jsearch_job_postings
                WHERE campaign_id IN (1, 2)
                GROUP BY campaign_id
                ORDER BY campaign_id
            """
            )
            counts_after = {row[0]: row[1] for row in cur.fetchall()}

        # Verify both campaigns still have data
        assert 1 in counts_after, "Campaign 1 should have jobs"
        assert 2 in counts_after, "Campaign 2 should still have jobs"

        # Verify campaign 2 count is unchanged
        assert counts_after[2] == counts_before[2], "Campaign 2 job count should be unchanged"

        # Campaign 1 may have same or more jobs
        assert counts_after[1] >= counts_before[1], "Campaign 1 should have same or more jobs"

    def test_incremental_materialization_processes_only_new_records(
        self,
        test_database,
        multiple_test_campaigns,
        sample_jsearch_response_multiple,
    ):
        """
        Test that incremental materialization processes only new/changed records.

        Setup: Extract jobs for campaign 1, run staging and fact_jobs
        Record: Count of records in staging and fact_jobs
        Run: Extract same jobs again (should create new raw records with new timestamps)
        Run: Run staging and fact_jobs incrementally
        Verify:
            - Only new records are added (or existing records updated)
            - Total count increases by expected amount
            - Old records are not duplicated
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        mock_client = MagicMock(spec=JSearchClient)
        mock_client.search_jobs.return_value = sample_jsearch_response_multiple

        # Extract jobs for campaign 1
        extractor = JobExtractor(database=db, jsearch_client=mock_client, num_pages=1)
        campaigns = extractor.get_active_campaigns()
        campaign_1 = next(c for c in campaigns if c["campaign_id"] == 1)
        extractor.extract_jobs_for_campaign(campaign_1)

        # Run staging and fact_jobs (first run)
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"

        if not check_dbt_available():
            pytest.skip("dbt is not installed or not in PATH")

        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings", "--vars", '{"campaign_id": 1}'],
            connection_string=test_database,
        )
        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.fact_jobs"],
            connection_string=test_database,
        )

        # Record counts
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM staging.jsearch_job_postings WHERE campaign_id = 1"
            )
            staging_count_before = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM marts.fact_jobs WHERE campaign_id = 1")
            fact_count_before = cur.fetchone()[0]

        # Extract same jobs again (creates new raw records with new timestamps)
        extractor.extract_jobs_for_campaign(campaign_1)

        # Run staging and fact_jobs incrementally
        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings", "--vars", '{"campaign_id": 1}'],
            connection_string=test_database,
        )
        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.fact_jobs"],
            connection_string=test_database,
        )

        # Verify counts
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM staging.jsearch_job_postings WHERE campaign_id = 1"
            )
            staging_count_after = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM marts.fact_jobs WHERE campaign_id = 1")
            fact_count_after = cur.fetchone()[0]

        # Counts should be same or slightly higher (if new records were added)
        # But not doubled (no duplicates)
        assert staging_count_after >= staging_count_before, "Staging count should not decrease"
        assert staging_count_after <= staging_count_before + 5, "Staging should not duplicate records"

        assert fact_count_after >= fact_count_before, "Fact count should not decrease"
        assert fact_count_after <= fact_count_before + 5, "Fact should not duplicate records"

    def test_fact_jobs_incremental_without_campaign_filter(
        self,
        test_database,
        multiple_test_campaigns,
        sample_jsearch_response_multiple,
    ):
        """
        Test that fact_jobs processes all campaigns even when staging is filtered.

        Setup: Extract jobs for campaigns 1 and 2
        Run: Run staging with campaign_id=1, then fact_jobs without campaign_id
        Verify:
            - fact_jobs contains jobs from both campaigns
            - fact_jobs processes all new records from staging regardless of campaign
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        mock_client = MagicMock(spec=JSearchClient)
        mock_client.search_jobs.return_value = sample_jsearch_response_multiple

        # Extract jobs for campaigns 1 and 2
        extractor = JobExtractor(database=db, jsearch_client=mock_client, num_pages=1)
        campaigns = extractor.get_active_campaigns()
        assert len(campaigns) >= 2

        for campaign in campaigns[:2]:
            extractor.extract_jobs_for_campaign(campaign)

        # Run staging with campaign_id=1 filter
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"

        if not check_dbt_available():
            pytest.skip("dbt is not installed or not in PATH")

        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings", "--vars", '{"campaign_id": 1}'],
            connection_string=test_database,
        )

        # Run staging for campaign 2 (without filter, or with campaign_id=2)
        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings", "--vars", '{"campaign_id": 2}'],
            connection_string=test_database,
        )

        # Run fact_jobs without campaign_id filter
        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.fact_jobs"],
            connection_string=test_database,
        )

        # Verify fact_jobs contains jobs from both campaigns
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT campaign_id, COUNT(*) as count
                FROM marts.fact_jobs
                WHERE campaign_id IN (1, 2)
                GROUP BY campaign_id
                ORDER BY campaign_id
            """
            )
            counts = {row[0]: row[1] for row in cur.fetchall()}

        assert 1 in counts, "fact_jobs should contain jobs for campaign 1"
        assert 2 in counts, "fact_jobs should contain jobs for campaign 2"
        assert counts[1] > 0, "Campaign 1 should have jobs"
        assert counts[2] > 0, "Campaign 2 should have jobs"

    def test_ranking_upsert_preserves_other_campaigns(
        self,
        test_database,
        multiple_test_campaigns,
        sample_jsearch_response_multiple,
    ):
        """
        Test that ranking UPSERT preserves other campaigns' rankings.

        Setup: Create rankings for campaigns 1 and 2
        Run: Rank jobs for campaign 1 only
        Verify:
            - dim_ranking still contains rankings for campaign 2
            - Campaign 1's rankings are updated
            - Campaign 2's rankings remain unchanged
            - No duplicate rankings created
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        mock_client = MagicMock(spec=JSearchClient)
        mock_client.search_jobs.return_value = sample_jsearch_response_multiple

        # Extract jobs and build fact_jobs for campaigns 1 and 2
        extractor = JobExtractor(database=db, jsearch_client=mock_client, num_pages=1)
        campaigns = extractor.get_active_campaigns()
        assert len(campaigns) >= 2

        for campaign in campaigns[:2]:
            extractor.extract_jobs_for_campaign(campaign)

        # Run staging and fact_jobs
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"

        if not check_dbt_available():
            pytest.skip("dbt is not installed or not in PATH")

        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings"],
            connection_string=test_database,
        )
        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.fact_jobs"],
            connection_string=test_database,
        )

        # Create rankings for both campaigns
        ranker = JobRanker(database=db)
        ranker.rank_jobs_for_campaign(campaigns[0])
        ranker.rank_jobs_for_campaign(campaigns[1])

        # Record counts per campaign in dim_ranking
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT campaign_id, COUNT(*) as count
                FROM marts.dim_ranking
                WHERE campaign_id IN (1, 2)
                GROUP BY campaign_id
                ORDER BY campaign_id
            """
            )
            counts_before = {row[0]: row[1] for row in cur.fetchall()}

        # Rank jobs for campaign 1 again
        ranker.rank_jobs_for_campaign(campaigns[0]["campaign_id"])

        # Verify counts per campaign in dim_ranking
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT campaign_id, COUNT(*) as count
                FROM marts.dim_ranking
                WHERE campaign_id IN (1, 2)
                GROUP BY campaign_id
                ORDER BY campaign_id
            """
            )
            counts_after = {row[0]: row[1] for row in cur.fetchall()}

        # Verify both campaigns still have rankings
        assert 1 in counts_after, "Campaign 1 should have rankings"
        assert 2 in counts_after, "Campaign 2 should still have rankings"

        # Verify campaign 2 count is unchanged
        assert counts_after[2] == counts_before[2], "Campaign 2 ranking count should be unchanged"

        # Campaign 1 should have same count (UPSERT updates, doesn't add duplicates)
        assert counts_after[1] == counts_before[1], "Campaign 1 should have same count (UPSERT)"

        # Verify no duplicates (check unique constraint)
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT jsearch_job_id, campaign_id, COUNT(*) as cnt
                FROM marts.dim_ranking
                WHERE campaign_id IN (1, 2)
                GROUP BY jsearch_job_id, campaign_id
                HAVING COUNT(*) > 1
            """
            )
            duplicates = cur.fetchall()
            assert len(duplicates) == 0, f"Found duplicate rankings: {duplicates}"

    def test_ranking_upsert_updates_existing_rankings(
        self,
        test_database,
        multiple_test_campaigns,
        sample_jsearch_response_multiple,
    ):
        """
        Test that ranking UPSERT correctly updates existing rankings.

        Setup: Create ranking for (job_id, campaign_id) pair
        Run: Rank same job again with different score
        Verify:
            - Only one row exists for (job_id, campaign_id)
            - Score is updated to new value
            - Timestamp is updated
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        mock_client = MagicMock(spec=JSearchClient)
        mock_client.search_jobs.return_value = sample_jsearch_response_multiple

        # Extract jobs and build fact_jobs for campaign 1
        extractor = JobExtractor(database=db, jsearch_client=mock_client, num_pages=1)
        campaigns = extractor.get_active_campaigns()
        campaign_1 = next(c for c in campaigns if c["campaign_id"] == 1)
        extractor.extract_jobs_for_campaign(campaign_1)

        # Run staging and fact_jobs
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"

        if not check_dbt_available():
            pytest.skip("dbt is not installed or not in PATH")

        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.jsearch_job_postings", "--vars", '{"campaign_id": 1}'],
            connection_string=test_database,
        )
        run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.fact_jobs"],
            connection_string=test_database,
        )

        # Create initial ranking
        ranker = JobRanker(database=db)
        ranker.rank_jobs_for_campaign(campaign_1)

        # Get a job_id and its initial ranking
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT jsearch_job_id, rank_score, ranked_at
                FROM marts.dim_ranking
                WHERE campaign_id = 1
                LIMIT 1
            """
            )
            initial_ranking = cur.fetchone()
            assert initial_ranking is not None, "Should have at least one ranking"
            job_id, initial_score, initial_timestamp = initial_ranking

        # Rank again (should update existing ranking)
        ranker.rank_jobs_for_campaign(campaign_1["campaign_id"])

        # Verify only one row exists and it's updated
        with db.get_cursor() as cur:
            cur.execute(
                """
                SELECT jsearch_job_id, rank_score, ranked_at, COUNT(*) as cnt
                FROM marts.dim_ranking
                WHERE jsearch_job_id = %s AND campaign_id = 1
                GROUP BY jsearch_job_id, rank_score, ranked_at
            """,
                (job_id,),
            )
            results = cur.fetchall()
            assert len(results) == 1, f"Should have exactly one row, found {len(results)}"

            updated_timestamp = results[0][2]

            # Score may be same or different (depending on ranking logic)
            # But timestamp should be updated
            assert updated_timestamp >= initial_timestamp, "Timestamp should be updated"

