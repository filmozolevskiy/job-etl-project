"""
Integration tests for campaign deletion and uniqueness.

Tests that:
1. Campaign IDs are unique
2. Deleting a campaign removes all related data
3. New campaigns don't show old jobs from deleted campaigns
"""

import pytest

from services.campaign_management import CampaignService
from services.jobs import JobService
from services.shared import PostgreSQLDatabase


@pytest.fixture
def campaign_service(test_database):
    """Create campaign service instance."""
    db = PostgreSQLDatabase(test_database)
    return CampaignService(db)


@pytest.fixture
def job_service(test_database):
    """Create job service instance."""
    db = PostgreSQLDatabase(test_database)
    return JobService(db)


@pytest.fixture
def test_user(test_database):
    """Create a test user."""
    db = PostgreSQLDatabase(test_database)
    with db.get_cursor() as cur:
        # Create test user
        cur.execute(
            """
            INSERT INTO marts.users (username, email, password_hash, role, created_at, updated_at)
            VALUES ('test_campaign_user', 'test_campaign@example.com', 'dummy_hash', 'user', NOW(), NOW())
            ON CONFLICT (username) DO UPDATE SET username = 'test_campaign_user'
            RETURNING user_id
            """
        )
        result = cur.fetchone()
        user_id = result[0] if result else None
        if not user_id:
            # User already exists, get the ID
            cur.execute("SELECT user_id FROM marts.users WHERE username = 'test_campaign_user'")
            user_id = cur.fetchone()[0]
    yield user_id
    # Cleanup
    with db.get_cursor() as cur:
        try:
            cur.execute("DELETE FROM marts.users WHERE user_id = %s", (user_id,))
        except Exception:
            pass


class TestCampaignUniqueness:
    """Test that campaign IDs are unique."""

    def test_campaign_ids_are_unique(self, campaign_service, test_user):
        """Test that created campaigns have unique IDs."""
        campaign_id_1 = campaign_service.create_campaign(
            campaign_name="Test Campaign 1",
            query="Software Engineer",
            country="us",
            user_id=test_user,
        )
        campaign_id_2 = campaign_service.create_campaign(
            campaign_name="Test Campaign 2",
            query="Data Engineer",
            country="us",
            user_id=test_user,
        )

        assert campaign_id_1 != campaign_id_2, "Campaign IDs must be unique"

        # Cleanup
        try:
            campaign_service.delete_campaign(campaign_id_1)
            campaign_service.delete_campaign(campaign_id_2)
        except Exception:
            pass

    def test_campaign_ids_increment(self, campaign_service, test_user):
        """Test that campaign IDs increment properly."""
        campaign_id_1 = campaign_service.create_campaign(
            campaign_name="Test Campaign 1",
            query="Software Engineer",
            country="us",
            user_id=test_user,
        )
        campaign_id_2 = campaign_service.create_campaign(
            campaign_name="Test Campaign 2",
            query="Data Engineer",
            country="us",
            user_id=test_user,
        )

        assert campaign_id_2 > campaign_id_1, "Campaign IDs should increment"

        # Cleanup
        try:
            campaign_service.delete_campaign(campaign_id_1)
            campaign_service.delete_campaign(campaign_id_2)
        except Exception:
            pass

    def test_campaign_id_primary_key_constraint(self, test_database, test_user):
        """Test that campaign_id has PRIMARY KEY constraint (prevents duplicates)."""
        db = PostgreSQLDatabase(test_database)
        campaign_service = CampaignService(db)

        # Create a campaign
        campaign_id = campaign_service.create_campaign(
            campaign_name="Test Campaign",
            query="Software Engineer",
            country="us",
            user_id=test_user,
        )

        # Try to insert duplicate campaign_id - should fail
        with db.get_cursor() as cur:
            with pytest.raises(Exception) as exc_info:  # Should raise unique constraint violation
                cur.execute(
                    """
                    INSERT INTO marts.job_campaigns
                    (campaign_id, user_id, campaign_name, query, country, created_at, updated_at, total_run_count, last_run_status)
                    VALUES (%s, %s, 'Duplicate', 'test', 'us', NOW(), NOW(), 0, 'pending')
                    """,
                    (campaign_id, test_user),
                )
            # Verify it's a unique constraint violation (or similar constraint error)
            assert (
                "unique" in str(exc_info.value).lower()
                or "duplicate" in str(exc_info.value).lower()
            )

        # Cleanup
        try:
            campaign_service.delete_campaign(campaign_id)
        except Exception:
            pass


class TestCampaignDeletion:
    """Test that deleting a campaign removes all related data."""

    def test_delete_campaign_removes_rankings(self, campaign_service, test_database, test_user):
        """Test that deleting a campaign removes rankings."""
        db = PostgreSQLDatabase(test_database)

        # Create campaign
        campaign_id = campaign_service.create_campaign(
            campaign_name="Test Campaign",
            query="Software Engineer",
            country="us",
            user_id=test_user,
        )

        # Insert a ranking
        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO marts.dim_ranking
                (jsearch_job_id, campaign_id, rank_score, ranked_at, ranked_date, dwh_load_timestamp, dwh_source_system)
                VALUES ('test_job_123', %s, 85.5, NOW(), CURRENT_DATE, NOW(), 'test')
                """,
                (campaign_id,),
            )

        # Verify ranking exists
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM marts.dim_ranking WHERE campaign_id = %s", (campaign_id,)
            )
            count_before = cur.fetchone()[0]
            assert count_before == 1, "Ranking should exist before deletion"

        # Delete campaign
        campaign_service.delete_campaign(campaign_id)

        # Verify ranking is deleted
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM marts.dim_ranking WHERE campaign_id = %s", (campaign_id,)
            )
            count_after = cur.fetchone()[0]
            assert count_after == 0, "Ranking should be deleted when campaign is deleted"

    def test_delete_campaign_removes_fact_jobs(self, campaign_service, test_database, test_user):
        """Test that deleting a campaign removes fact_jobs."""
        db = PostgreSQLDatabase(test_database)

        # Create campaign
        campaign_id = campaign_service.create_campaign(
            campaign_name="Test Campaign",
            query="Software Engineer",
            country="us",
            user_id=test_user,
        )

        # Create fact_jobs table if it doesn't exist (it's created by dbt normally)
        with db.get_cursor() as cur:
            # Drop and recreate to ensure proper schema with all columns
            cur.execute("DROP TABLE IF EXISTS marts.fact_jobs CASCADE")
            cur.execute(
                """
                CREATE TABLE marts.fact_jobs (
                    jsearch_job_id varchar,
                    campaign_id integer,
                    job_title varchar,
                    job_summary text,
                    employer_name varchar,
                    job_location varchar,
                    employment_type varchar,
                    job_posted_at_datetime_utc timestamp,
                    apply_options jsonb,
                    job_apply_link varchar,
                    job_google_link varchar,
                    extracted_skills jsonb,
                    job_min_salary numeric,
                    job_max_salary numeric,
                    job_salary_period varchar,
                    job_salary_currency varchar,
                    remote_work_type varchar,
                    seniority_level varchar,
                    company_key varchar,
                    dwh_load_date date,
                    dwh_load_timestamp timestamp,
                    dwh_source_system varchar,
                    PRIMARY KEY (jsearch_job_id, campaign_id)
                )
                """
            )
            # Create dim_companies table (required by job queries)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS marts.dim_companies (
                    company_key varchar PRIMARY KEY,
                    company_name varchar,
                    company_size varchar,
                    rating numeric,
                    company_link varchar,
                    logo varchar
                )
                """
            )
            # Create user_job_status table (required by job queries)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS marts.user_job_status (
                    user_job_status_id SERIAL PRIMARY KEY,
                    jsearch_job_id varchar NOT NULL,
                    user_id integer NOT NULL,
                    status varchar NOT NULL,
                    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_user_job_status UNIQUE (user_id, jsearch_job_id)
                )
                """
            )
            # Create job_notes table (required by job queries)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS marts.job_notes (
                    note_id SERIAL PRIMARY KEY,
                    jsearch_job_id varchar NOT NULL,
                    user_id integer NOT NULL,
                    note_text text,
                    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_job_user_note UNIQUE (jsearch_job_id, user_id)
                )
                """
            )

        # Insert a fact_job
        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO marts.fact_jobs
                (jsearch_job_id, campaign_id, job_title, employer_name, job_location, dwh_load_date, dwh_load_timestamp, dwh_source_system)
                VALUES ('test_job_123', %s, 'Software Engineer', 'Test Company', 'Remote', CURRENT_DATE, NOW(), 'test')
                """,
                (campaign_id,),
            )

        # Verify fact_job exists
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM marts.fact_jobs WHERE campaign_id = %s", (campaign_id,)
            )
            count_before = cur.fetchone()[0]
            assert count_before == 1, "Fact job should exist before deletion"

        # Delete campaign
        campaign_service.delete_campaign(campaign_id)

        # Verify fact_job is deleted
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM marts.fact_jobs WHERE campaign_id = %s", (campaign_id,)
            )
            count_after = cur.fetchone()[0]
            assert count_after == 0, "Fact job should be deleted when campaign is deleted"

    def test_delete_campaign_removes_staging_jobs(self, campaign_service, test_database, test_user):
        """Test that deleting a campaign removes staging jobs."""
        db = PostgreSQLDatabase(test_database)

        # Create campaign
        campaign_id = campaign_service.create_campaign(
            campaign_name="Test Campaign",
            query="Software Engineer",
            country="us",
            user_id=test_user,
        )

        # Create staging.jsearch_job_postings table if it doesn't exist (it's created by dbt normally)
        with db.get_cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS staging.jsearch_job_postings (
                    jsearch_job_postings_key bigint PRIMARY KEY,
                    jsearch_job_id varchar,
                    campaign_id integer,
                    job_title varchar,
                    employer_name varchar,
                    job_location varchar,
                    dwh_load_date date,
                    dwh_load_timestamp timestamp,
                    dwh_source_system varchar
                )
                """
            )

        # Insert a staging job
        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO staging.jsearch_job_postings
                (jsearch_job_postings_key, jsearch_job_id, campaign_id, job_title, employer_name, job_location,
                 dwh_load_date, dwh_load_timestamp, dwh_source_system)
                VALUES (1, 'test_job_123', %s, 'Software Engineer', 'Test Company', 'Remote',
                        CURRENT_DATE, NOW(), 'test')
                """,
                (campaign_id,),
            )

        # Verify staging job exists
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM staging.jsearch_job_postings WHERE campaign_id = %s",
                (campaign_id,),
            )
            count_before = cur.fetchone()[0]
            assert count_before == 1, "Staging job should exist before deletion"

        # Delete campaign
        campaign_service.delete_campaign(campaign_id)

        # Verify staging job is deleted
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM staging.jsearch_job_postings WHERE campaign_id = %s",
                (campaign_id,),
            )
            count_after = cur.fetchone()[0]
            assert count_after == 0, "Staging job should be deleted when campaign is deleted"

    def test_delete_campaign_removes_etl_metrics(self, campaign_service, test_database, test_user):
        """Test that deleting a campaign removes ETL metrics."""
        db = PostgreSQLDatabase(test_database)

        # Create campaign
        campaign_id = campaign_service.create_campaign(
            campaign_name="Test Campaign",
            query="Software Engineer",
            country="us",
            user_id=test_user,
        )

        # Insert ETL metrics
        with db.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO marts.etl_run_metrics
                (run_id, dag_run_id, campaign_id, task_name, task_status, run_timestamp,
                 rows_processed_raw, rows_processed_staging, rows_processed_marts,
                 processing_duration_seconds)
                VALUES ('test_run_1', 'dag_run_1', %s, 'extract_job_postings', 'success', NOW(),
                        10, 10, 10, 5.5)
                """,
                (campaign_id,),
            )

        # Verify ETL metrics exist
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM marts.etl_run_metrics WHERE campaign_id = %s", (campaign_id,)
            )
            count_before = cur.fetchone()[0]
            assert count_before >= 1, "ETL metrics should exist before deletion"

        # Delete campaign
        campaign_service.delete_campaign(campaign_id)

        # Verify ETL metrics are deleted
        with db.get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM marts.etl_run_metrics WHERE campaign_id = %s", (campaign_id,)
            )
            count_after = cur.fetchone()[0]
            assert count_after == 0, "ETL metrics should be deleted when campaign is deleted"

    def test_delete_campaign_comprehensive_cleanup(
        self, campaign_service, test_database, test_user
    ):
        """Test comprehensive cleanup when deleting a campaign."""
        db = PostgreSQLDatabase(test_database)

        # Create campaign
        campaign_id = campaign_service.create_campaign(
            campaign_name="Test Campaign",
            query="Software Engineer",
            country="us",
            user_id=test_user,
        )

        # Create tables if they don't exist (they're created by dbt normally)
        with db.get_cursor() as cur:
            # Create staging table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS staging.jsearch_job_postings (
                    jsearch_job_postings_key bigint PRIMARY KEY,
                    jsearch_job_id varchar,
                    campaign_id integer,
                    job_title varchar,
                    employer_name varchar,
                    job_location varchar,
                    dwh_load_date date,
                    dwh_load_timestamp timestamp,
                    dwh_source_system varchar
                )
                """
            )
            # Create fact_jobs table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS marts.fact_jobs (
                    jsearch_job_id varchar,
                    campaign_id integer,
                    job_title varchar,
                    job_summary text,
                    employer_name varchar,
                    job_location varchar,
                    employment_type varchar,
                    job_posted_at_datetime_utc timestamp,
                    apply_options jsonb,
                    job_apply_link varchar,
                    job_google_link varchar,
                    extracted_skills jsonb,
                    job_min_salary numeric,
                    job_max_salary numeric,
                    job_salary_period varchar,
                    job_salary_currency varchar,
                    remote_work_type varchar,
                    seniority_level varchar,
                    company_key varchar,
                    dwh_load_date date,
                    dwh_load_timestamp timestamp,
                    dwh_source_system varchar,
                    PRIMARY KEY (jsearch_job_id, campaign_id)
                )
                """
            )
            # Create chatgpt_enrichments table if it doesn't exist
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS staging.chatgpt_enrichments (
                    jsearch_job_postings_key bigint PRIMARY KEY,
                    chatgpt_enriched_at timestamp,
                    chatgpt_enrichment_status jsonb,
                    dwh_load_date date,
                    dwh_load_timestamp timestamp
                )
                """
            )

        # Insert data in all related tables
        with db.get_cursor() as cur:
            # Raw job
            cur.execute(
                """
                INSERT INTO raw.jsearch_job_postings
                (jsearch_job_postings_key, raw_payload, dwh_load_date, dwh_load_timestamp,
                 dwh_source_system, campaign_id)
                VALUES (1, '{}'::jsonb, CURRENT_DATE, NOW(), 'test', %s)
                """,
                (campaign_id,),
            )

            # Staging job
            cur.execute(
                """
                INSERT INTO staging.jsearch_job_postings
                (jsearch_job_postings_key, jsearch_job_id, campaign_id, job_title, employer_name,
                 job_location, dwh_load_date, dwh_load_timestamp, dwh_source_system)
                VALUES (1, 'test_job_123', %s, 'Software Engineer', 'Test Company', 'Remote',
                        CURRENT_DATE, NOW(), 'test')
                """,
                (campaign_id,),
            )

            # Staging ChatGPT enrichment
            cur.execute(
                """
                INSERT INTO staging.chatgpt_enrichments
                (jsearch_job_postings_key, chatgpt_enriched_at, chatgpt_enrichment_status,
                 dwh_load_date, dwh_load_timestamp)
                VALUES (1, NOW(), '{}'::jsonb, CURRENT_DATE, NOW())
                """
            )

            # Fact job
            cur.execute(
                """
                INSERT INTO marts.fact_jobs
                (jsearch_job_id, campaign_id, job_title, employer_name, job_location,
                 dwh_load_date, dwh_load_timestamp, dwh_source_system)
                VALUES ('test_job_123', %s, 'Software Engineer', 'Test Company', 'Remote',
                        CURRENT_DATE, NOW(), 'test')
                """,
                (campaign_id,),
            )

            # Ranking
            cur.execute(
                """
                INSERT INTO marts.dim_ranking
                (jsearch_job_id, campaign_id, rank_score, ranked_at, ranked_date,
                 dwh_load_timestamp, dwh_source_system)
                VALUES ('test_job_123', %s, 85.5, NOW(), CURRENT_DATE, NOW(), 'test')
                """,
                (campaign_id,),
            )

        # Delete campaign
        campaign_service.delete_campaign(campaign_id)

        # Verify all data is deleted
        with db.get_cursor() as cur:
            # Check raw jobs
            cur.execute(
                "SELECT COUNT(*) FROM raw.jsearch_job_postings WHERE campaign_id = %s",
                (campaign_id,),
            )
            assert cur.fetchone()[0] == 0, "Raw jobs should be deleted"

            # Check staging jobs
            cur.execute(
                "SELECT COUNT(*) FROM staging.jsearch_job_postings WHERE campaign_id = %s",
                (campaign_id,),
            )
            assert cur.fetchone()[0] == 0, "Staging jobs should be deleted"

            # Check fact jobs
            cur.execute(
                "SELECT COUNT(*) FROM marts.fact_jobs WHERE campaign_id = %s", (campaign_id,)
            )
            assert cur.fetchone()[0] == 0, "Fact jobs should be deleted"

            # Check rankings
            cur.execute(
                "SELECT COUNT(*) FROM marts.dim_ranking WHERE campaign_id = %s", (campaign_id,)
            )
            assert cur.fetchone()[0] == 0, "Rankings should be deleted"

    def test_new_campaign_does_not_show_old_jobs(
        self, campaign_service, job_service, test_database, test_user
    ):
        """Test that a new campaign doesn't show jobs from a deleted campaign."""
        db = PostgreSQLDatabase(test_database)

        # Create first campaign
        campaign_id_1 = campaign_service.create_campaign(
            campaign_name="Campaign 1",
            query="Software Engineer",
            country="us",
            user_id=test_user,
        )

        # Create fact_jobs and dim_companies tables (ensure company_key column exists)
        with db.get_cursor() as cur:
            # Create fact_jobs table if it doesn't exist (with all columns used by queries)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS marts.fact_jobs (
                    jsearch_job_id varchar,
                    campaign_id integer,
                    job_title varchar,
                    job_summary text,
                    employer_name varchar,
                    job_location varchar,
                    employment_type varchar,
                    job_posted_at_datetime_utc timestamp,
                    apply_options jsonb,
                    job_apply_link varchar,
                    job_google_link varchar,
                    extracted_skills jsonb,
                    job_min_salary numeric,
                    job_max_salary numeric,
                    job_salary_period varchar,
                    job_salary_currency varchar,
                    remote_work_type varchar,
                    seniority_level varchar,
                    company_key varchar,
                    dwh_load_date date,
                    dwh_load_timestamp timestamp,
                    dwh_source_system varchar,
                    PRIMARY KEY (jsearch_job_id, campaign_id)
                )
                """
            )
            # Add company_key column if it doesn't exist
            cur.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'marts'
                        AND table_name = 'fact_jobs'
                        AND column_name = 'company_key'
                    ) THEN
                        ALTER TABLE marts.fact_jobs ADD COLUMN company_key varchar;
                    END IF;
                END $$;
                """
            )
            # Create dim_companies table (required by job queries)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS marts.dim_companies (
                    company_key varchar PRIMARY KEY,
                    company_name varchar,
                    company_size varchar,
                    rating numeric,
                    company_link varchar,
                    logo varchar
                )
                """
            )
            # Create user_job_status table (required by job queries)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS marts.user_job_status (
                    user_job_status_id SERIAL PRIMARY KEY,
                    jsearch_job_id varchar NOT NULL,
                    user_id integer NOT NULL,
                    status varchar NOT NULL,
                    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_user_job_status UNIQUE (user_id, jsearch_job_id)
                )
                """
            )
            # Create job_notes table (required by job queries)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS marts.job_notes (
                    note_id SERIAL PRIMARY KEY,
                    jsearch_job_id varchar NOT NULL,
                    user_id integer NOT NULL,
                    note_text text,
                    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_job_user_note UNIQUE (jsearch_job_id, user_id)
                )
                """
            )

        # Insert job data for first campaign
        with db.get_cursor() as cur:
            # Fact job
            cur.execute(
                """
                INSERT INTO marts.fact_jobs
                (jsearch_job_id, campaign_id, job_title, employer_name, job_location,
                 dwh_load_date, dwh_load_timestamp, dwh_source_system)
                VALUES ('old_job_123', %s, 'Old Job', 'Old Company', 'Remote',
                        CURRENT_DATE, NOW(), 'test')
                """,
                (campaign_id_1,),
            )
            # Ranking
            cur.execute(
                """
                INSERT INTO marts.dim_ranking
                (jsearch_job_id, campaign_id, rank_score, ranked_at, ranked_date,
                 dwh_load_timestamp, dwh_source_system)
                VALUES ('old_job_123', %s, 85.5, NOW(), CURRENT_DATE, NOW(), 'test')
                """,
                (campaign_id_1,),
            )

        # Delete first campaign
        campaign_service.delete_campaign(campaign_id_1)

        # Create new campaign (might get same ID if not using sequence, but shouldn't matter)
        campaign_id_2 = campaign_service.create_campaign(
            campaign_name="Campaign 2",
            query="Data Engineer",
            country="us",
            user_id=test_user,
        )

        # Get jobs for new campaign - should be empty
        jobs = job_service.get_jobs_for_campaign(campaign_id_2, user_id=test_user)
        assert len(jobs) == 0, "New campaign should not show jobs from deleted campaign"

        # Cleanup
        try:
            campaign_service.delete_campaign(campaign_id_2)
        except Exception:
            pass

    def test_job_queries_only_show_existing_campaigns(
        self, campaign_service, job_service, test_database, test_user
    ):
        """Test that job queries only return jobs for existing campaigns."""
        db = PostgreSQLDatabase(test_database)

        # Create campaign
        campaign_id = campaign_service.create_campaign(
            campaign_name="Test Campaign",
            query="Software Engineer",
            country="us",
            user_id=test_user,
        )

        # Create fact_jobs and dim_companies tables (ensure company_key column exists)
        with db.get_cursor() as cur:
            # Create fact_jobs table if it doesn't exist (with all columns used by queries)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS marts.fact_jobs (
                    jsearch_job_id varchar,
                    campaign_id integer,
                    job_title varchar,
                    job_summary text,
                    employer_name varchar,
                    job_location varchar,
                    employment_type varchar,
                    job_posted_at_datetime_utc timestamp,
                    apply_options jsonb,
                    job_apply_link varchar,
                    job_google_link varchar,
                    extracted_skills jsonb,
                    job_min_salary numeric,
                    job_max_salary numeric,
                    job_salary_period varchar,
                    job_salary_currency varchar,
                    remote_work_type varchar,
                    seniority_level varchar,
                    company_key varchar,
                    dwh_load_date date,
                    dwh_load_timestamp timestamp,
                    dwh_source_system varchar,
                    PRIMARY KEY (jsearch_job_id, campaign_id)
                )
                """
            )
            # Add company_key column if it doesn't exist
            cur.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'marts'
                        AND table_name = 'fact_jobs'
                        AND column_name = 'company_key'
                    ) THEN
                        ALTER TABLE marts.fact_jobs ADD COLUMN company_key varchar;
                    END IF;
                END $$;
                """
            )
            # Create dim_companies table (required by job queries)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS marts.dim_companies (
                    company_key varchar PRIMARY KEY,
                    company_name varchar,
                    company_size varchar,
                    rating numeric,
                    company_link varchar,
                    logo varchar
                )
                """
            )

        # Insert job data
        with db.get_cursor() as cur:
            # Fact job
            cur.execute(
                """
                INSERT INTO marts.fact_jobs
                (jsearch_job_id, campaign_id, job_title, employer_name, job_location,
                 dwh_load_date, dwh_load_timestamp, dwh_source_system)
                VALUES ('test_job_123', %s, 'Test Job', 'Test Company', 'Remote',
                        CURRENT_DATE, NOW(), 'test')
                """,
                (campaign_id,),
            )
            # Ranking
            cur.execute(
                """
                INSERT INTO marts.dim_ranking
                (jsearch_job_id, campaign_id, rank_score, ranked_at, ranked_date,
                 dwh_load_timestamp, dwh_source_system)
                VALUES ('test_job_123', %s, 85.5, NOW(), CURRENT_DATE, NOW(), 'test')
                """,
                (campaign_id,),
            )

        # Verify jobs are returned for existing campaign
        jobs = job_service.get_jobs_for_campaign(campaign_id, user_id=test_user)
        assert len(jobs) == 1, "Should return job for existing campaign"

        # Delete campaign
        campaign_service.delete_campaign(campaign_id)

        # Verify jobs are NOT returned for deleted campaign
        # (This tests the INNER JOIN with job_campaigns in the query)
        jobs = job_service.get_jobs_for_campaign(campaign_id, user_id=test_user)
        assert len(jobs) == 0, "Should not return jobs for deleted campaign"
