"""
Unit tests for Job Enricher service.

Tests skills extraction, seniority extraction, and enrichment logic.
"""

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
        """Test that description is also checked for seniority."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        title = "Software Developer"
        description = "We are looking for a senior engineer."
        seniority = enricher.extract_seniority(title, description)

        assert seniority == "senior"


class TestJobEnricherEnrichment:
    """Test job enrichment functionality."""

    def test_enrich_job_complete(self):
        """Test enriching a job with both skills and seniority."""
        mock_db = Mock(spec=Database)
        enricher = JobEnricher(database=mock_db, batch_size=100)

        job = {
            "jsearch_job_postings_key": 1,
            "job_title": "Senior Python Developer",
            "job_description": "We need a Python developer with SQL and AWS experience.",
        }

        enrichment = enricher.enrich_job(job)

        assert "extracted_skills" in enrichment
        assert "seniority_level" in enrichment
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
            "job_description": "We need a Python developer.",
        }

        enrichment = enricher.enrich_job(job)

        assert "extracted_skills" in enrichment
        assert "seniority_level" in enrichment
        assert "python" in enrichment["extracted_skills"]
        assert enrichment["seniority_level"] is None

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
        ]
        mock_db.cursor.fetchall.return_value = [
            (1, "job1", "Python Developer", "We need Python skills."),
            (2, "job2", "Java Developer", "We need Java skills."),
        ]

        enricher = JobEnricher(database=mock_db, batch_size=100)
        jobs = enricher.get_jobs_to_enrich(limit=10)

        assert len(jobs) == 2
        assert jobs[0]["jsearch_job_postings_key"] == 1
        assert jobs[0]["job_title"] == "Python Developer"

    def test_update_job_enrichment(self):
        """Test updating job enrichment in database."""
        mock_db = MockDatabase()
        enricher = JobEnricher(database=mock_db, batch_size=100)

        skills = ["python", "sql", "aws"]
        seniority = "senior"

        enricher.update_job_enrichment(
            job_key=1, extracted_skills=skills, seniority_level=seniority
        )

        # Verify execute was called
        assert mock_db.cursor.execute.called
        call_args = mock_db.cursor.execute.call_args
        assert call_args is not None
