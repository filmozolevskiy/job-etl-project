"""
Unit tests for Job Enricher service.

Tests skills extraction, seniority extraction, and enrichment logic.
"""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock

import pytest

from services.enricher.job_enricher import JobEnricher
from services.shared import Database


class MockDatabase:
    """Simple mock Database implementation for testing."""

    def __init__(self):
        self.cursor = MagicMock()

    @contextmanager
    def get_cursor(self):
        """Context manager that yields a mock cursor."""
        yield self.cursor


class TestJobEnricherSkillsExtraction:
    """Test skills extraction functionality."""

    def test_extract_skills_basic_technical_skills(self):
        """Test extraction of common technical skills."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        description = "We are looking for a Python developer with SQL and AWS experience."
        skills = enricher.extract_skills(description)

        assert "python" in skills
        assert "sql" in skills
        assert "aws" in skills

    def test_extract_skills_case_insensitive(self):
        """Test that skill extraction is case-insensitive."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        description = "Looking for JAVA and JavaScript developers."
        skills = enricher.extract_skills(description)

        assert "java" in skills
        assert "javascript" in skills

    def test_extract_skills_word_boundaries(self):
        """Test that skills are matched with word boundaries to avoid partial matches."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        # "javascript" should not match "java" in "javascript"
        description = "We need JavaScript developers, not Java developers."
        skills = enricher.extract_skills(description)

        # Both should be found separately
        assert "javascript" in skills
        assert "java" in skills

    def test_extract_skills_empty_description(self):
        """Test that empty description returns empty skills list."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        skills = enricher.extract_skills("")
        assert skills == []

    def test_extract_skills_no_matches(self):
        """Test that description with no skills returns empty list."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        description = "We are looking for a general office worker."
        skills = enricher.extract_skills(description)

        assert isinstance(skills, list)
        assert len(skills) == 0

    def test_extract_skills_with_title(self):
        """Test that job title is included in skills extraction."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Python Developer"
        description = "We need someone with SQL experience."
        skills = enricher.extract_skills(description, title)

        assert "python" in skills
        assert "sql" in skills

    def test_extract_skills_multiple_occurrences(self):
        """Test that skills are deduplicated."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        description = "Python Python Python developer with Python experience."
        skills = enricher.extract_skills(description)

        # Should only appear once
        assert skills.count("python") == 1
        assert "python" in skills

    def test_extract_skills_sorted(self):
        """Test that extracted skills are sorted alphabetically."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        description = "We need developers with AWS, Python, and SQL skills."
        skills = enricher.extract_skills(description)

        assert skills == sorted(skills)

    def test_extract_skills_category_based_iteration(self):
        """Test that skills from different categories are all detected."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        # Test skills from multiple categories
        description = (
            "We need a Python developer with AWS experience, "
            "PostgreSQL database skills, React frontend, and Docker containers."
        )
        skills = enricher.extract_skills(description)

        # Verify skills from different categories are found
        assert "python" in skills  # programming_languages
        assert "aws" in skills  # cloud_platforms
        assert "postgresql" in skills  # databases
        assert "react" in skills  # web_technologies
        assert "docker" in skills  # container_orchestration

    def test_extract_skills_multi_word_skills(self):
        """Test that multi-word skills are detected correctly."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        description = (
            "Looking for machine learning engineer with deep learning experience, "
            "familiar with data science and business intelligence tools."
        )
        skills = enricher.extract_skills(description)

        # Verify multi-word skills are found
        assert "machine learning" in skills
        assert "deep learning" in skills
        assert "data science" in skills
        assert "business intelligence" in skills

    def test_extract_skills_alternative_names(self):
        """Test that alternative names for skills are detected."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        description = (
            "We need someone with Amazon Web Services, Microsoft Azure, "
            "and Google Cloud Platform experience. Also need JavaScript (JS) and TypeScript (TS)."
        )
        skills = enricher.extract_skills(description)

        # Verify alternative names are found
        assert "aws" in skills or "amazon web services" in skills
        assert "azure" in skills or "microsoft azure" in skills
        assert "gcp" in skills or "google cloud platform" in skills
        assert "javascript" in skills or "js" in skills
        assert "typescript" in skills or "ts" in skills


class TestJobEnricherSeniorityExtraction:
    """Test seniority extraction functionality."""

    def test_extract_seniority_intern(self):
        """Test extraction of intern level."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Software Engineering Intern"
        seniority = enricher.extract_seniority(title)

        assert seniority == "intern"

    def test_extract_seniority_junior(self):
        """Test extraction of junior level."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Junior Software Developer"
        seniority = enricher.extract_seniority(title)

        assert seniority == "junior"

    def test_extract_seniority_mid(self):
        """Test extraction of mid-level."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Mid-Level Software Engineer"
        seniority = enricher.extract_seniority(title)

        assert seniority == "mid"

    def test_extract_seniority_senior(self):
        """Test extraction of senior level."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Senior Software Engineer"
        seniority = enricher.extract_seniority(title)

        assert seniority == "senior"

    def test_extract_seniority_lead(self):
        """Test extraction of lead level (mapped to senior)."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Lead Software Engineer"
        seniority = enricher.extract_seniority(title)

        assert seniority == "senior"

    def test_extract_seniority_executive(self):
        """Test extraction of executive level."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Director of Engineering"
        seniority = enricher.extract_seniority(title)

        assert seniority == "executive"

    def test_extract_seniority_no_match(self):
        """Test that title with no seniority returns None."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Software Developer"
        seniority = enricher.extract_seniority(title)

        assert seniority is None

    def test_extract_seniority_empty_title(self):
        """Test that empty title returns None."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        seniority = enricher.extract_seniority("")
        assert seniority is None

    def test_extract_seniority_case_insensitive(self):
        """Test that seniority extraction is case-insensitive."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "SENIOR SOFTWARE ENGINEER"
        seniority = enricher.extract_seniority(title)

        assert seniority == "senior"

    def test_extract_seniority_with_description(self):
        """Test that description is also checked for seniority when title has none."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Software Developer"
        description = "We are looking for a senior engineer."
        seniority = enricher.extract_seniority(title, description)

        assert seniority == "senior"

    def test_extract_seniority_title_priority(self):
        """Test that title takes priority over description when both have seniority indicators."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        # Title says "junior" but description says "senior" - title should win
        title = "Junior Software Developer"
        description = "We are looking for a senior engineer with 10+ years experience."
        seniority = enricher.extract_seniority(title, description)

        assert seniority == "junior"

    def test_extract_seniority_internship_vs_intern(self):
        """Test that 'internship' is matched correctly and not partially matched as 'intern'."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        # "Internship" should match as "intern" level (correct behavior)
        title = "Software Engineering Internship"
        seniority = enricher.extract_seniority(title)
        assert seniority == "intern"

        # "Intern" should also match as "intern" level
        title = "Software Engineering Intern"
        seniority = enricher.extract_seniority(title)
        assert seniority == "intern"

        # "Internship Coordinator" should match "internship" pattern, not "intern"
        title = "Internship Coordinator"
        seniority = enricher.extract_seniority(title)
        assert seniority == "intern"  # Both "intern" and "internship" map to "intern" level


class TestJobEnricherEnrichment:
    """Test job enrichment functionality."""

    def test_enrich_job_complete(self):
        """Test enriching a job with skills, seniority, remote type, and salary."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Senior Python Developer",
            "job_description": (
                "We need a Python developer with SQL and AWS experience. "
                "Compensation: $120k-$140k per year."
            ),
        }

        enrichment = enricher.enrich_job(job)

        assert "extracted_skills" in enrichment
        assert "seniority_level" in enrichment
        assert "remote_work_type" in enrichment
        assert enrichment["job_min_salary"] == 120000.0
        assert enrichment["job_max_salary"] == 140000.0
        assert enrichment["job_salary_period"] == "year"
        assert enrichment["job_salary_currency"] == "USD"  # Default for $
        assert "python" in enrichment["extracted_skills"]
        assert "sql" in enrichment["extracted_skills"]
        assert "aws" in enrichment["extracted_skills"]
        assert enrichment["seniority_level"] == "senior"

    def test_enrich_job_no_seniority(self):
        """Test enriching a job with no seniority level."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Developer",
            "job_description": "We need a Python developer. Pay is 80k per year.",
        }

        enrichment = enricher.enrich_job(job)

        assert "extracted_skills" in enrichment
        assert "seniority_level" in enrichment
        assert "remote_work_type" in enrichment
        assert "python" in enrichment["extracted_skills"]
        assert enrichment["seniority_level"] is None
        assert enrichment["job_min_salary"] == 80000.0
        assert enrichment["job_max_salary"] == 80000.0
        assert enrichment["job_salary_period"] == "year"
        # No explicit currency symbol or country; currency should remain None
        assert enrichment["job_salary_currency"] is None

    def test_enrich_job_empty_description(self):
        """Test enriching a job with empty description."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Developer",
            "job_description": "",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["extracted_skills"] == []
        assert enrichment["seniority_level"] is None
        assert enrichment["remote_work_type"] is None
        assert enrichment["job_min_salary"] is None
        assert enrichment["job_max_salary"] is None
        assert enrichment["job_salary_period"] is None
        assert enrichment["job_salary_currency"] is None

    def test_enrich_job_ignores_non_salary_numbers(self):
        """Test that non-salary numeric mentions are ignored by salary extraction."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Senior Python Developer",
            "job_description": (
                "We need a Python developer with 5+ years of experience, working on a team of 3-5."
            ),
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] is None
        assert enrichment["job_max_salary"] is None
        assert enrichment["job_salary_period"] is None
        assert enrichment["job_salary_currency"] is None

    def test_enrich_job_extracts_decimal_hourly_salary(self):
        """Test that decimal hourly salaries are extracted correctly."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Developer",
            "job_description": "The pay range for this position is $52.06 to $92.45 per hour.",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 52.06
        assert enrichment["job_max_salary"] == 92.45
        assert enrichment["job_salary_period"] == "hour"
        assert enrichment["job_salary_currency"] == "USD"  # Default for $

    def test_enrich_job_ignores_financial_market_amounts(self):
        """Test that large financial amounts (T/M/B suffixes) are not extracted as salary."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "CFO",
            "job_description": (
                "Private funds manage $15T in capital and are growing at 20% YoY, "
                "but with increasing regulatory scrutiny and investor demands for transparency, "
                "the need for world class software to help private fund CFOs is crucial."
            ),
        }

        enrichment = enricher.enrich_job(job)

        # Should NOT extract $15T as salary (15 trillion is financial data, not salary)
        assert enrichment["job_min_salary"] is None
        assert enrichment["job_max_salary"] is None
        assert enrichment["job_salary_period"] is None
        assert enrichment["job_salary_currency"] is None

    def test_enrich_job_extracts_per_annum_salary_range(self):
        """Test that salary ranges with 'per annum' are extracted correctly."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Engineer",
            "job_description": (
                "US: Hiring Range in USD from: $79,800 to $178,100 per annum. "
                "May be eligible for bonus and equity."
            ),
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 79800.0
        assert enrichment["job_max_salary"] == 178100.0
        assert enrichment["job_salary_period"] == "year"
        assert enrichment["job_salary_currency"] == "USD"  # Default for $

    def test_enrich_job_ignores_unrelated_per_week_context(self):
        """Test that 'per week' in unrelated context (telework) doesn't affect salary period."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Engineer",
            "job_description": (
                "Location: Annapolis Junction, Maryland / Partial Telework up to 2 days per week\n\n"
                "Salary Range: The salary range for this full-time position is $170,000 to $260,000. "
                "Our salary ranges are determined by position, level, skills, professional experience, "
                "relevant education and certifications."
            ),
        }

        enrichment = enricher.enrich_job(job)

        # Should extract salary range correctly
        assert enrichment["job_min_salary"] == 170000.0
        assert enrichment["job_max_salary"] == 260000.0
        # Should default to "year" for large salary ranges, not "week" from telework context
        assert enrichment["job_salary_period"] == "year"
        assert enrichment["job_salary_currency"] == "USD"  # Default for $

    def test_enrich_job_detects_cad_currency(self):
        """Test that CAD currency is detected from explicit mentions."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Developer",
            "job_description": "Salary: $80,000 to $100,000 CAD per year. Canadian dollars.",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 80000.0
        assert enrichment["job_max_salary"] == 100000.0
        assert enrichment["job_salary_period"] == "year"
        assert enrichment["job_salary_currency"] == "CAD"

    def test_enrich_job_detects_gbp_currency(self):
        """Test that GBP currency is detected from pound symbol."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Developer",
            "job_description": "Compensation: £50,000 - £70,000 per annum.",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 50000.0
        assert enrichment["job_max_salary"] == 70000.0
        assert enrichment["job_salary_period"] == "year"
        assert enrichment["job_salary_currency"] == "GBP"

    def test_enrich_job_extracts_hourly_range_with_slash_hr(self):
        """Test that hourly ranges with /hr format are extracted correctly."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Contract Developer",
            "job_description": (
                "RATE RANGE: $58/hr - $68/hr W2 (no health benefits no PTO while on contract)"
            ),
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 58.0
        assert enrichment["job_max_salary"] == 68.0
        assert enrichment["job_salary_period"] == "hour"
        assert enrichment["job_salary_currency"] == "USD"  # Default for $ without country

    def test_enrich_job_defaults_currency_to_country_ca(self):
        """Test that currency defaults to CAD for Canadian jobs when using $ symbol."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Engineer",
            "job_description": "Salary: $80,000 to $100,000 per year.",
            "job_country": "CA",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 80000.0
        assert enrichment["job_max_salary"] == 100000.0
        assert enrichment["job_salary_period"] == "year"
        # Should default to CAD for Canadian jobs with $ symbol
        assert enrichment["job_salary_currency"] == "CAD"

    def test_enrich_job_defaults_currency_to_country_us(self):
        """Test that currency defaults to USD for US jobs when using $ symbol."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Engineer",
            "job_description": "Salary: $120,000 to $150,000 per year.",
            "job_country": "US",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 120000.0
        assert enrichment["job_max_salary"] == 150000.0
        assert enrichment["job_salary_period"] == "year"
        # Should default to USD for US jobs with $ symbol
        assert enrichment["job_salary_currency"] == "USD"

    def test_enrich_job_extracts_canadian_dollar_prefix(self):
        """Test that C$ prefix (Canadian dollar) is detected correctly."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Engineer",
            "job_description": "Salary: C$170,000 to C$185,000 + equity, depending on seniority and years of experience",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 170000.0
        assert enrichment["job_max_salary"] == 185000.0
        assert enrichment["job_salary_period"] == "year"  # Default for large amounts
        assert enrichment["job_salary_currency"] == "CAD"

    def test_enrich_job_extracts_decimal_salary_ranges(self):
        """Test that decimal salary ranges like $108,000.00-$216,000.00 are extracted."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Engineer",
            "job_description": "The annual salary range for this position is $108,000.00-$216,000.00",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 108000.0
        assert enrichment["job_max_salary"] == 216000.0
        assert enrichment["job_salary_period"] == "year"
        assert enrichment["job_salary_currency"] == "USD"

    def test_enrich_job_extracts_salary_with_location_prefix(self):
        """Test that salary ranges with location prefixes are extracted."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Senior Software Engineer",
            "job_description": "McLean, VA: $158,600 - $181,000 for Senior Software Engineer",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 158600.0
        assert enrichment["job_max_salary"] == 181000.0
        assert enrichment["job_salary_period"] == "year"  # Default for large amounts
        assert enrichment["job_salary_currency"] == "USD"

    def test_enrich_job_extracts_salary_with_cad_suffix(self):
        """Test that salary ranges with CAD suffix are extracted."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Engineer",
            "job_description": "This position offers a competitive salary range of $99,000 - $110,000 CAD, along with other benefits.",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 99000.0
        assert enrichment["job_max_salary"] == 110000.0
        assert enrichment["job_salary_period"] == "year"  # Default for large amounts
        assert enrichment["job_salary_currency"] == "CAD"

    def test_enrich_job_excludes_sign_on_bonus(self):
        """Test that sign-on bonus amounts are not extracted as salary."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Engineer",
            "job_description": "This position is eligible for a sign-on bonus up to $30,000 for New Hires",
        }

        enrichment = enricher.enrich_job(job)

        # Should NOT extract sign-on bonus as salary
        assert enrichment["job_min_salary"] is None
        assert enrichment["job_max_salary"] is None
        assert enrichment["job_salary_period"] is None
        assert enrichment["job_salary_currency"] is None

    def test_enrich_job_extracts_with_doe_suffix(self):
        """Test that salary ranges with DOE (Depending On Experience) suffix are extracted."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Engineer",
            "job_description": "The Compensation Range for this role is $155,000 - $185,000 DOE.",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 155000.0
        assert enrichment["job_max_salary"] == 185000.0
        assert enrichment["job_salary_period"] == "year"  # Default for large amounts
        assert enrichment["job_salary_currency"] == "USD"

    def test_enrich_job_extracts_with_double_dash_and_annually(self):
        """Test that salary ranges with double dash and 'annually' are extracted."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Software Engineer",
            "job_description": "the U.S. pay range for this position is $170,500 -- $320,000 annually.",
        }

        enrichment = enricher.enrich_job(job)

        assert enrichment["job_min_salary"] == 170500.0
        assert enrichment["job_max_salary"] == 320000.0
        assert enrichment["job_salary_period"] == "year"  # Should detect "annually"
        assert enrichment["job_salary_currency"] == "USD"


class TestJobEnricherInitialization:
    """Test JobEnricher initialization."""

    def test_init_with_valid_params(self):
        """Test initialization with valid parameters."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=50)

        assert enricher.db == mock_db
        assert enricher.batch_size == 50

    def test_init_without_database(self):
        """Test that initialization fails without database."""
        with pytest.raises(ValueError, match="Database is required"):
            JobEnricher(database=None, batch_size=100)

    def test_init_with_invalid_batch_size(self):
        """Test that initialization fails with invalid batch_size."""
        mock_db = Mock(spec=Database)

        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            JobEnricher(database=mock_db, batch_size=0)

        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            JobEnricher(database=mock_db, batch_size=-1)

    def test_init_loads_nlp_model(self):
        """Test that NLP model is loaded during initialization."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        # Model may be None if spaCy model not installed, but initialization should not fail
        # The enricher should still work with basic pattern matching
        assert enricher.db == mock_db


class TestJobEnricherDatabaseOperations:
    """Test database operations."""

    def test_get_jobs_to_enrich(self):
        """Test getting jobs that need enrichment."""
        mock_db = MockDatabase()
        mock_db.cursor.description = [
            ("jsearch_job_postings_key",),
            ("jsearch_job_id",),
            ("job_title",),
            ("job_description",),
            ("extracted_skills",),
            ("seniority_level",),
            ("remote_work_type",),
            ("enrichment_status",),
        ]
        mock_db.cursor.fetchall.return_value = [
            (
                1,
                "job1",
                "Python Developer",
                "We need Python skills.",
                None,
                None,
                False,
                '{"skills_enriched": false, "seniority_enriched": false, "remote_type_enriched": false}',
            ),
            (
                2,
                "job2",
                "Java Developer",
                "We need Java skills.",
                None,
                None,
                False,
                '{"skills_enriched": false, "seniority_enriched": false, "remote_type_enriched": false}',
            ),
        ]

        enricher = JobEnricher(database=mock_db, batch_size=100)
        jobs = enricher.get_jobs_to_enrich(limit=10)

        assert len(jobs) == 2
        assert jobs[0]["jsearch_job_postings_key"] == 1
        assert jobs[0]["job_title"] == "Python Developer"

    def test_update_job_enrichment(self):
        """Test updating job enrichment in database."""
        mock_db = MockDatabase()
        # Mock the GET_JOB_INFO_FOR_HISTORY query result to return None (no job found)
        # This prevents status history recording from executing
        mock_db.cursor.fetchone.side_effect = [None]
        enricher = JobEnricher(database=mock_db, batch_size=100)

        skills = ["python", "sql", "aws"]
        seniority = "senior"
        remote_type = "remote"
        min_salary = 120000.0
        max_salary = 140000.0
        salary_period = "year"
        salary_currency = "USD"
        status_updates = (
            '{"skills_enriched": true, "seniority_enriched": true, "remote_type_enriched": true}'
        )

        enricher.update_job_enrichment(
            job_key=1,
            extracted_skills=skills,
            seniority_level=seniority,
            remote_work_type=remote_type,
            job_min_salary=min_salary,
            job_max_salary=max_salary,
            job_salary_period=salary_period,
            job_salary_currency=salary_currency,
            enrichment_status_updates=status_updates,
        )

        # Verify execute was called
        assert mock_db.cursor.execute.called
        # Get the first call (the enrichment update call)
        call_args = mock_db.cursor.execute.call_args_list[0]
        assert call_args is not None
        # Verify all parameters were passed
        assert (
            len(call_args[0][1]) == 9
        )  # skills_json, seniority, remote_type, min_salary, max_salary, salary_period, salary_currency, status_updates, job_key


class TestJobEnricherRemoteTypeExtraction:
    """Test remote work type extraction functionality."""

    def test_extract_remote_type_remote(self):
        """Test extraction of remote work type."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Software Developer"
        description = "A consulting firm is seeking a Dynamics Power BI Developer to join their team remotely within Canada."
        remote_type = enricher.extract_remote_type(title, description)

        assert remote_type == "remote"

    def test_extract_remote_type_hybrid(self):
        """Test extraction of hybrid work type."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Software Engineer"
        description = "We offer a hybrid work arrangement with 2 days in office."
        remote_type = enricher.extract_remote_type(title, description)

        assert remote_type == "hybrid"

    def test_extract_remote_type_onsite(self):
        """Test extraction of onsite work type."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Software Developer"
        description = "This is an on-site position requiring daily office attendance."
        remote_type = enricher.extract_remote_type(title, description)

        assert remote_type == "onsite"

    def test_extract_remote_type_no_match(self):
        """Test that description with no remote type returns None."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Software Developer"
        description = "We are looking for a developer with Python experience."
        remote_type = enricher.extract_remote_type(title, description)

        assert remote_type is None

    def test_extract_remote_type_empty_input(self):
        """Test that empty input returns None."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        remote_type = enricher.extract_remote_type("", "")
        assert remote_type is None

    def test_extract_remote_type_hybrid_working_environment(self):
        """Test extraction of hybrid from 'hybrid working environment' pattern."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Senior Java Engineer"
        description = "This role offers a hybrid working environment, allowing for both remote and on-site work as needed."
        remote_type = enricher.extract_remote_type(title, description)

        assert remote_type == "hybrid"

    def test_extract_remote_type_both_remote_and_onsite(self):
        """Test that 'both remote and on-site' matches hybrid pattern."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Software Engineer"
        description = "We offer both remote and on-site work options."
        remote_type = enricher.extract_remote_type(title, description)

        assert remote_type == "hybrid"


class TestJobEnricherEnrichmentStatus:
    """Test enrichment status tracking functionality."""

    def test_enrich_jobs_with_status_tracking(self):
        """Test that enrich_jobs updates enrichment_status correctly."""
        mock_db = MockDatabase()
        mock_db.cursor.description = [
            ("jsearch_job_postings_key",),
            ("jsearch_job_id",),
            ("job_title",),
            ("job_description",),
            ("job_country",),
            ("extracted_skills",),
            ("seniority_level",),
            ("remote_work_type",),
            ("job_min_salary",),
            ("job_max_salary",),
            ("job_salary_period",),
            ("job_salary_currency",),
            ("enrichment_status",),
        ]
        mock_db.cursor.fetchall.return_value = [
            (
                1,
                "job1",
                "Senior Python Developer",
                "We need a Python developer with SQL. This is a remote position.",
                None,  # job_country
                None,  # extracted_skills
                None,  # seniority_level
                False,  # remote_work_type (default)
                None,  # job_min_salary
                None,  # job_max_salary
                None,  # job_salary_period
                None,  # job_salary_currency
                '{"skills_enriched": false, "seniority_enriched": false, "remote_type_enriched": false, "salary_enriched": false}',  # enrichment_status
            ),
        ]

        enricher = JobEnricher(database=mock_db, batch_size=100)
        stats = enricher.enrich_jobs()

        assert stats["processed"] == 1
        assert stats["enriched"] == 1
        assert stats["errors"] == 0

        # Verify update was called with enrichment_status_updates
        assert mock_db.cursor.execute.called
        call_args = mock_db.cursor.execute.call_args
        assert call_args is not None
        # Check that enrichment_status_updates parameter was passed
        params = call_args[0][1]
        assert (
            len(params) == 9
        )  # skills_json, seniority, remote_type, min_salary, max_salary, salary_period, salary_currency, status_updates, job_key
        status_updates = json.loads(params[7])  # enrichment_status_updates is at index 7
        assert "skills_enriched" in status_updates
        assert "seniority_enriched" in status_updates
        assert "remote_type_enriched" in status_updates

    def test_enrich_jobs_partial_enrichment(self):
        """Test that jobs with partial enrichment only process missing fields."""
        mock_db = MockDatabase()
        mock_db.cursor.description = [
            ("jsearch_job_postings_key",),
            ("jsearch_job_id",),
            ("job_title",),
            ("job_description",),
            ("job_country",),
            ("extracted_skills",),
            ("seniority_level",),
            ("remote_work_type",),
            ("job_min_salary",),
            ("job_max_salary",),
            ("job_salary_period",),
            ("job_salary_currency",),
            ("enrichment_status",),
        ]
        mock_db.cursor.fetchall.return_value = [
            (
                1,
                "job1",
                "Senior Python Developer",
                "We need a Python developer. This is a remote position.",
                None,  # job_country
                '["python"]',  # extracted_skills already set
                None,  # seniority_level not set
                False,  # remote_work_type not set
                None,  # job_min_salary
                None,  # job_max_salary
                None,  # job_salary_period
                None,  # job_salary_currency
                '{"skills_enriched": true, "seniority_enriched": false, "remote_type_enriched": false, "salary_enriched": false}',  # Only skills processed
            ),
        ]
        # Mock GET_JOB_INFO_FOR_HISTORY query to return None (no job found)
        # This prevents status history recording from executing
        mock_db.cursor.fetchone.return_value = None

        enricher = JobEnricher(database=mock_db, batch_size=100)
        stats = enricher.enrich_jobs()

        assert stats["processed"] == 1
        assert stats["enriched"] == 1

        # Verify update was called - get the first call (enrichment update)
        call_args = mock_db.cursor.execute.call_args_list[0]
        params = call_args[0][1]
        status_updates = json.loads(params[7])  # enrichment_status_updates is at index 7
        # Should only update seniority, remote_type, and salary flags, not skills
        assert status_updates.get("skills_enriched") is None  # Not in updates
        assert status_updates.get("seniority_enriched") is True
        assert status_updates.get("remote_type_enriched") is True
        assert status_updates.get("salary_enriched") is True

    def test_enrich_jobs_marks_salary_enriched_when_salary_exists(self):
        """Jobs with existing salary should not be overwritten, but flag should be set to true."""
        mock_db = MockDatabase()
        mock_db.cursor.description = [
            ("jsearch_job_postings_key",),
            ("jsearch_job_id",),
            ("job_title",),
            ("job_description",),
            ("job_country",),
            ("extracted_skills",),
            ("seniority_level",),
            ("remote_work_type",),
            ("job_min_salary",),
            ("job_max_salary",),
            ("job_salary_period",),
            ("job_salary_currency",),
            ("enrichment_status",),
        ]
        mock_db.cursor.fetchall.return_value = [
            (
                1,
                "job1",
                "Senior Python Developer",
                "We need a Python developer. Salary is already set.",
                None,  # job_country
                '["python"]',
                "senior",
                "remote",
                120000.0,
                140000.0,
                "year",
                None,  # job_salary_currency
                '{"skills_enriched": true, "seniority_enriched": true, "remote_type_enriched": true, "salary_enriched": false}',
            ),
        ]
        # Mock GET_JOB_INFO_FOR_HISTORY query to return None (no job found)
        # This prevents status history recording from executing
        mock_db.cursor.fetchone.return_value = None

        enricher = JobEnricher(database=mock_db, batch_size=100)
        stats = enricher.enrich_jobs()

        assert stats["processed"] == 1
        assert stats["enriched"] == 1

        # Get the first call (enrichment update)
        call_args = mock_db.cursor.execute.call_args_list[0]
        params = call_args[0][1]
        # Existing salary values should be preserved (None passed -> COALESCE keeps current)
        assert params[3] is None  # job_min_salary
        assert params[4] is None  # job_max_salary
        assert params[5] is None  # job_salary_period
        status_updates = json.loads(params[7])  # enrichment_status_updates is at index 7
        assert status_updates.get("salary_enriched") is True

    def test_enrich_jobs_handles_malformed_enrichment_status(self):
        """Test that enrich_jobs handles malformed JSON in enrichment_status gracefully."""
        mock_db = MockDatabase()
        mock_db.cursor.description = [
            ("jsearch_job_postings_key",),
            ("jsearch_job_id",),
            ("job_title",),
            ("job_description",),
            ("job_country",),
            ("extracted_skills",),
            ("seniority_level",),
            ("remote_work_type",),
            ("job_min_salary",),
            ("job_max_salary",),
            ("job_salary_period",),
            ("job_salary_currency",),
            ("enrichment_status",),
        ]
        mock_db.cursor.fetchall.return_value = [
            (
                1,
                "job1",
                "Senior Python Developer",
                "We need a Python developer with SQL. This is a remote position.",
                None,  # job_country
                None,  # extracted_skills
                None,  # seniority_level
                False,  # remote_work_type (default)
                None,  # job_min_salary
                None,  # job_max_salary
                None,  # job_salary_period
                None,  # job_salary_currency
                '{"skills_enriched": true, invalid json}',  # Malformed JSON
            ),
        ]

        enricher = JobEnricher(database=mock_db, batch_size=100)
        stats = enricher.enrich_jobs()

        # Should not crash, should default to empty dict and process the job
        assert stats["processed"] == 1
        assert stats["enriched"] == 1
        assert stats["errors"] == 0

        # Verify update was called (job should be processed despite malformed JSON)
        assert mock_db.cursor.execute.called
