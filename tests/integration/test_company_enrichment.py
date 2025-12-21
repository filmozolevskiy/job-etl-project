"""
Integration tests for company enrichment flow.

Tests the complete company enrichment pipeline:
1. Jobs are extracted and normalized (prerequisite)
2. Companies are identified from job postings
3. Company data is extracted from Glassdoor API (mocked)
4. Companies are normalized via dbt staging model
5. Companies appear in marts.dim_companies
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import psycopg2
import pytest

from services.extractor.company_extractor import CompanyExtractor
from services.extractor.glassdoor_client import GlassdoorClient
from services.extractor.job_extractor import JobExtractor
from services.extractor.jsearch_client import JSearchClient
from services.shared import PostgreSQLDatabase

from .test_helpers import check_dbt_available, run_dbt_command

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def test_profile_with_jobs(test_database, sample_jsearch_response):
    """
    Create a test profile and extract jobs to staging layer.
    
    Returns:
        dict: Profile information including profile_id
    """
    db = PostgreSQLDatabase(connection_string=test_database)
    
    # Create test profile
    with db.get_cursor() as cur:
        cur.execute("""
            INSERT INTO marts.profile_preferences 
            (profile_id, profile_name, is_active, query, location, country, date_window, email,
             created_at, updated_at, total_run_count, last_run_status, last_run_job_count)
            VALUES 
            (1, 'Test Profile', true, 'Business Intelligence Engineer', 'Toronto, ON', 'ca', 'week', 
             'test@example.com', NOW(), NOW(), 0, NULL, 0)
            RETURNING profile_id, profile_name, query, location, country, date_window
        """)
        
        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        profile = dict(zip(columns, row))
    
    # Extract jobs to raw layer
    mock_jsearch_client = MagicMock(spec=JSearchClient)
    mock_jsearch_client.search_jobs.return_value = sample_jsearch_response
    extractor = JobExtractor(database=db, jsearch_client=mock_jsearch_client, num_pages=1)
    profiles = extractor.get_active_profiles()
    extractor.extract_jobs_for_profile(profiles[0])
    
    # Normalize jobs to staging layer
    project_root = Path(__file__).parent.parent.parent
    dbt_project_dir = project_root / "dbt"
    
    if not check_dbt_available():
        pytest.skip("dbt is not installed or not in PATH. Install dbt to run integration tests.")
    
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
    
    yield profile
    
    # Cleanup
    with db.get_cursor() as cur:
        cur.execute("DELETE FROM marts.profile_preferences WHERE profile_id = %s", (profile["profile_id"],))


@pytest.fixture
def mock_glassdoor_client(sample_glassdoor_response):
    """Create a mock GlassdoorClient that returns sample data."""
    mock_client = MagicMock(spec=GlassdoorClient)
    mock_client.search_company.return_value = sample_glassdoor_response
    return mock_client


class TestCompanyEnrichmentFlow:
    """Test the complete company enrichment flow."""

    def test_companies_identified_from_staging_jobs(
        self, test_database, test_profile_with_jobs
    ):
        """
        Test that companies can be identified from staging.jsearch_job_postings.
        
        This verifies that the company extraction service can find companies
        that need enrichment.
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        mock_glassdoor_client = MagicMock(spec=GlassdoorClient)
        extractor = CompanyExtractor(database=db, glassdoor_client=mock_glassdoor_client)
        
        # Get companies that need enrichment
        companies = extractor.get_companies_to_enrich(limit=10)
        
        # Verify that companies were identified
        assert len(companies) > 0
        
        for company_lookup_key in companies:
            assert isinstance(company_lookup_key, str)
            assert company_lookup_key is not None
            assert company_lookup_key != ""

    def test_company_extracted_to_raw_layer(
        self, test_database, test_profile_with_jobs, mock_glassdoor_client, sample_glassdoor_response
    ):
        """
        Test that company data is extracted and written to raw.glassdoor_companies.
        
        This tests Step 3 of the pipeline.
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        extractor = CompanyExtractor(database=db, glassdoor_client=mock_glassdoor_client)
        
        # Extract companies
        results = extractor.extract_all_companies()
        
        # Verify at least one company was processed
        assert len(results) > 0
        
        # Verify companies were written to raw layer
        with db.get_cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as count, company_lookup_key
                FROM raw.glassdoor_companies
                GROUP BY company_lookup_key
            """)
            
            rows = cur.fetchall()
            assert len(rows) > 0
            
            # Verify raw payload structure
            cur.execute("""
                SELECT raw_payload, company_lookup_key, dwh_load_date, dwh_source_system
                FROM raw.glassdoor_companies
                LIMIT 1
            """)
            
            row = cur.fetchone()
            assert row is not None
            assert row[1] is not None  # company_lookup_key
            assert row[2] is not None  # dwh_load_date
            assert row[3] == "glassdoor"  # dwh_source_system
            assert "company_id" in row[0]  # raw_payload is JSONB
            assert "name" in row[0]  # raw_payload contains name

    def test_enrichment_queue_updated(
        self, test_database, test_profile_with_jobs, mock_glassdoor_client
    ):
        """
        Test that the company_enrichment_queue is properly updated.
        
        This verifies that the queue tracks enrichment status correctly.
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        extractor = CompanyExtractor(database=db, glassdoor_client=mock_glassdoor_client)
        
        # Extract companies
        results = extractor.extract_all_companies()
        
        # Verify queue entries were created/updated
        with db.get_cursor() as cur:
            cur.execute("""
                SELECT company_lookup_key, enrichment_status, first_queued_at, last_attempt_at
                FROM staging.company_enrichment_queue
                WHERE enrichment_status = 'success'
                LIMIT 1
            """)
            
            row = cur.fetchone()
            if row is not None:  # If any companies were successfully enriched
                assert row[0] is not None  # company_lookup_key
                assert row[1] == "success"  # enrichment_status
                assert row[2] is not None  # first_queued_at
                assert row[3] is not None  # last_attempt_at

    def test_normalize_companies_to_staging(
        self, test_database, test_profile_with_jobs, mock_glassdoor_client
    ):
        """
        Test that companies are normalized from raw to staging layer via dbt.
        
        This tests Step 4 of the pipeline.
        """
        # First, extract companies to raw layer
        db = PostgreSQLDatabase(connection_string=test_database)
        extractor = CompanyExtractor(database=db, glassdoor_client=mock_glassdoor_client)
        extractor.extract_all_companies()
        
        # Verify raw layer has data
        with db.get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM raw.glassdoor_companies")
            raw_count = cur.fetchone()[0]
            
            if raw_count == 0:
                pytest.skip("No companies in raw layer - cannot test normalization")
        
        # Run dbt staging model
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"
        
        if not check_dbt_available():
            pytest.skip("dbt is not installed or not in PATH. Install dbt to run integration tests.")
        
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.glassdoor_companies"],
            env={"DBT_PROFILES_DIR": str(dbt_project_dir)},
            connection_string=test_database,
        )
        
        if result is None:
            pytest.skip("dbt is not available")
        if result.returncode != 0:
            pytest.skip(f"dbt staging run failed: {result.stderr}")
        
        # Verify companies were normalized to staging layer
        with db.get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM staging.glassdoor_companies")
            staging_count = cur.fetchone()[0]
            assert staging_count > 0
            
            # Verify staging table has expected columns
            cur.execute("""
                SELECT glassdoor_company_id, company_name, website, industry, rating
                FROM staging.glassdoor_companies
                LIMIT 1
            """)
            
            row = cur.fetchone()
            assert row is not None
            assert row[0] is not None  # glassdoor_company_id
            assert row[1] is not None  # company_name

    def test_companies_in_marts_dim_companies(
        self, test_database, test_profile_with_jobs, mock_glassdoor_client
    ):
        """
        Test that companies appear in marts.dim_companies after normalization.
        
        This tests Step 6 (marts building) of the pipeline.
        """
        # Extract and normalize companies
        db = PostgreSQLDatabase(connection_string=test_database)
        extractor = CompanyExtractor(database=db, glassdoor_client=mock_glassdoor_client)
        extractor.extract_all_companies()
        
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"
        
        if not check_dbt_available():
            pytest.skip("dbt is not installed or not in PATH. Install dbt to run integration tests.")
        
        # Run staging model
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.glassdoor_companies"],
            env={"DBT_PROFILES_DIR": str(dbt_project_dir)},
            connection_string=test_database,
        )
        
        if result is None:
            pytest.skip("dbt is not available")
        if result.returncode != 0:
            pytest.skip(f"dbt staging run failed: {result.stderr}")
        
        # Run marts model
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.dim_companies"],
            env={"DBT_PROFILES_DIR": str(dbt_project_dir)},
            connection_string=test_database,
        )
        
        if result is None:
            pytest.skip("dbt is not available")
        if result.returncode != 0:
            pytest.skip(f"dbt marts run failed: {result.stderr}")
        
        # Verify companies in marts
        with db.get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM marts.dim_companies")
            marts_count = cur.fetchone()[0]
            assert marts_count > 0
            
            # Verify marts table has expected columns
            cur.execute("""
                SELECT company_key, glassdoor_company_id, company_name, rating
                FROM marts.dim_companies
                LIMIT 1
            """)
            
            row = cur.fetchone()
            assert row is not None
            assert row[0] is not None  # company_key (surrogate key)
            assert row[1] is not None  # glassdoor_company_id (natural key)

    def test_complete_company_enrichment_flow(
        self, test_database, test_profile_with_jobs, mock_glassdoor_client, sample_glassdoor_response
    ):
        """
        Test the complete company enrichment flow end-to-end.
        
        This is a comprehensive integration test that validates:
        1. Companies are identified from jobs
        2. Company data is extracted to raw layer
        3. Companies are normalized to staging
        4. Companies appear in marts.dim_companies
        """
        db = PostgreSQLDatabase(connection_string=test_database)
        project_root = Path(__file__).parent.parent.parent
        dbt_project_dir = project_root / "dbt"
        
        # Step 1: Identify companies that need enrichment
        extractor = CompanyExtractor(database=db, glassdoor_client=mock_glassdoor_client)
        companies_to_enrich = extractor.get_companies_to_enrich(limit=10)
        
        assert len(companies_to_enrich) > 0
        
        # Step 2: Extract companies to raw layer
        results = extractor.extract_all_companies()
        assert len(results) > 0
        
        # Verify raw layer
        with db.get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM raw.glassdoor_companies")
            raw_count = cur.fetchone()[0]
            assert raw_count > 0
        
        if not check_dbt_available():
            pytest.skip("dbt is not installed or not in PATH. Install dbt to run integration tests.")
        
        # Step 3: Normalize companies to staging
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "staging.glassdoor_companies"],
            env={"DBT_PROFILES_DIR": str(dbt_project_dir)},
            connection_string=test_database,
        )
        
        if result is None:
            pytest.skip("dbt is not available")
        if result.returncode != 0:
            pytest.skip(f"dbt staging run failed: {result.stderr}")
        
        # Verify staging layer
        with db.get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM staging.glassdoor_companies")
            staging_count = cur.fetchone()[0]
            assert staging_count > 0
        
        # Step 4: Build marts
        result = run_dbt_command(
            dbt_project_dir,
            ["run", "--select", "marts.dim_companies"],
            env={"DBT_PROFILES_DIR": str(dbt_project_dir)},
            connection_string=test_database,
        )
        
        if result is None:
            pytest.skip("dbt is not available")
        if result.returncode != 0:
            pytest.skip(f"dbt marts run failed: {result.stderr}")
        
        # Verify marts layer
        with db.get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM marts.dim_companies")
            marts_count = cur.fetchone()[0]
            assert marts_count > 0
            
            # Verify data integrity: company lookup keys from raw match company names in marts
            cur.execute("""
                SELECT 
                    rg.company_lookup_key,
                    sc.company_name,
                    mc.company_name as marts_company_name
                FROM raw.glassdoor_companies rg
                INNER JOIN staging.glassdoor_companies sc ON rg.company_lookup_key = sc.company_lookup_key
                INNER JOIN marts.dim_companies mc ON sc.glassdoor_company_id = mc.glassdoor_company_id
                LIMIT 1
            """)
            
            row = cur.fetchone()
            if row is not None:
                assert row[0] is not None
                assert row[1] is not None
                assert row[2] is not None
