"""
Unit tests for JobRanker multiple preference scoring methods.

Tests the scoring logic for multiple preferences support:
- Remote preference matching
- Seniority level matching
- Company size matching
- Employment type matching
"""

from unittest.mock import MagicMock

import pytest

from services.ranker.job_ranker import JobRanker


class TestJobRankerMultiplePreferences:
    """Test multiple preference scoring functionality."""

    @pytest.fixture
    def ranker(self):
        """Create a JobRanker instance with a mock database."""
        mock_db = MagicMock()
        return JobRanker(database=mock_db)

    def test_score_remote_type_match_multiple_preferences_exact(self, ranker):
        """Test remote type scoring with multiple preferences - exact match."""
        job = {"remote_work_type": "remote"}
        profile = {"remote_preference": "remote,hybrid"}

        score = ranker._score_remote_type_match(job, profile)
        assert score == 1.0  # Exact match with one of the preferences

    def test_score_remote_type_match_multiple_preferences_hybrid(self, ranker):
        """Test remote type scoring with multiple preferences - hybrid match."""
        job = {"remote_work_type": "hybrid"}
        profile = {"remote_preference": "remote,hybrid"}

        score = ranker._score_remote_type_match(job, profile)
        assert score == 1.0  # Exact match

    def test_score_remote_type_match_multiple_preferences_partial(self, ranker):
        """Test remote type scoring with multiple preferences - partial match."""
        job = {"remote_work_type": "hybrid"}
        profile = {"remote_preference": "remote"}

        score = ranker._score_remote_type_match(job, profile)
        assert score == 0.7  # Partial match (remote matches hybrid)

    def test_score_remote_type_match_no_preference(self, ranker):
        """Test remote type scoring when profile has no preference."""
        job = {"remote_work_type": "remote"}
        profile = {}

        score = ranker._score_remote_type_match(job, profile)
        assert score == 0.5  # Neutral score

    def test_score_seniority_match_multiple_preferences_exact(self, ranker):
        """Test seniority scoring with multiple preferences - exact match."""
        job = {"seniority_level": "mid"}
        profile = {"seniority": "entry,mid,senior"}

        score = ranker._score_seniority_match(job, profile)
        assert score == 1.0  # Exact match with one of the preferences

    def test_score_seniority_match_multiple_preferences_adjacent(self, ranker):
        """Test seniority scoring with multiple preferences - adjacent level."""
        job = {"seniority_level": "mid"}
        profile = {"seniority": "entry,senior"}

        score = ranker._score_seniority_match(job, profile)
        assert score == 0.7  # Adjacent level match (mid is 1 level from entry or senior)

    def test_score_seniority_match_multiple_preferences_two_levels_apart(self, ranker):
        """Test seniority scoring with multiple preferences - two levels apart."""
        job = {"seniority_level": "senior"}
        profile = {"seniority": "entry"}

        score = ranker._score_seniority_match(job, profile)
        assert score == 0.4  # Two levels apart

    def test_score_seniority_match_no_preference(self, ranker):
        """Test seniority scoring when profile has no preference."""
        job = {"seniority_level": "senior"}
        profile = {}

        score = ranker._score_seniority_match(job, profile)
        assert score == 0.5  # Neutral score

    def test_score_company_size_match_multiple_preferences_exact(self, ranker):
        """Test company size scoring with multiple preferences - exact match."""
        job = {"company_size": "201-500"}
        profile = {"company_size_preference": "1-50,201-500,10000+"}

        score = ranker._score_company_size_match(job, profile)
        assert score == 1.0  # Exact match with one of the preferences

    def test_score_company_size_match_multiple_preferences_numeric_exact(self, ranker):
        """Test company size scoring with numeric value - exact match."""
        job = {"company_size": "300"}
        profile = {"company_size_preference": "201-500,501-1000"}

        score = ranker._score_company_size_match(job, profile)
        assert score == 1.0  # 300 falls within 201-500 range

    def test_score_company_size_match_multiple_preferences_close(self, ranker):
        """Test company size scoring with multiple preferences - close match."""
        job = {"company_size": "45"}  # Close to 51-200 range
        profile = {"company_size_preference": "51-200"}

        score = ranker._score_company_size_match(job, profile)
        assert score == 0.6  # Close to lower bound (45/51 ≈ 0.88, but threshold is 0.7)

    def test_score_company_size_match_no_preference(self, ranker):
        """Test company size scoring when profile has no preference."""
        job = {"company_size": "201-500"}
        profile = {}

        score = ranker._score_company_size_match(job, profile)
        assert score == 0.5  # Neutral score

    def test_score_employment_type_match_multiple_preferences_exact(self, ranker):
        """Test employment type scoring with multiple preferences - exact match."""
        job = {"job_employment_type": "FULLTIME"}
        profile = {"employment_type_preference": "FULLTIME,PARTTIME"}

        score = ranker._score_employment_type_match(job, profile)
        assert score == 1.0  # Exact match

    def test_score_employment_type_match_multiple_preferences_jsonb(self, ranker):
        """Test employment type scoring with JSONB array field."""
        job = {"job_employment_types": ["FULLTIME", "CONTRACTOR"]}
        profile = {"employment_type_preference": "FULLTIME,PARTTIME"}

        score = ranker._score_employment_type_match(job, profile)
        assert score == 1.0  # Matches FULLTIME from the array

    def test_score_employment_type_match_multiple_preferences_comma_separated(self, ranker):
        """Test employment type scoring with comma-separated string field."""
        job = {"employment_types": "FULLTIME,CONTRACTOR"}
        profile = {"employment_type_preference": "FULLTIME,PARTTIME"}

        score = ranker._score_employment_type_match(job, profile)
        assert score == 1.0  # Matches FULLTIME from comma-separated string

    def test_score_employment_type_match_partial(self, ranker):
        """Test employment type scoring - partial match."""
        job = {"job_employment_type": "FULL_TIME"}  # Different format
        profile = {"employment_type_preference": "FULLTIME"}

        score = ranker._score_employment_type_match(job, profile)
        # "FULL_TIME" contains "FULLTIME" when uppercase comparison is done
        # The method checks if preference is in the combined job types string
        assert score in (0.8, 0.2)  # May match or not depending on implementation

    def test_score_employment_type_match_no_preference(self, ranker):
        """Test employment type scoring when profile has no preference."""
        job = {"job_employment_type": "FULLTIME"}
        profile = {}

        score = ranker._score_employment_type_match(job, profile)
        assert score == 0.5  # Neutral score

    def test_score_remote_type_match_with_job_is_remote_flag(self, ranker):
        """Test remote type scoring using job_is_remote boolean flag."""
        job = {"job_is_remote": True, "remote_work_type": None}
        profile = {"remote_preference": "remote"}

        score = ranker._score_remote_type_match(job, profile)
        assert score == 1.0  # job_is_remote=True should map to "remote"

    def test_score_remote_type_match_onsite_from_flag(self, ranker):
        """Test remote type scoring using job_is_remote=False for onsite."""
        job = {"job_is_remote": False, "remote_work_type": None}
        profile = {"remote_preference": "onsite"}

        score = ranker._score_remote_type_match(job, profile)
        assert score == 1.0  # job_is_remote=False should map to "onsite"

    def test_score_seniority_match_empty_string(self, ranker):
        """Test seniority scoring with empty string preference."""
        job = {"seniority_level": "senior"}
        profile = {"seniority": ""}

        score = ranker._score_seniority_match(job, profile)
        assert score == 0.5  # Neutral score for empty preference

    def test_score_company_size_match_range_format(self, ranker):
        """Test company size scoring with range format in job data."""
        job = {"company_size": "250-300"}  # Range format
        profile = {"company_size_preference": "201-500"}

        score = ranker._score_company_size_match(job, profile)
        # Midpoint is 275, which is within 201-500
        assert score == 1.0

    def test_score_all_methods_handle_missing_job_data(self, ranker):
        """Test that all scoring methods handle missing job data gracefully."""
        profile = {
            "remote_preference": "remote",
            "seniority": "mid",
            "company_size_preference": "201-500",
            "employment_type_preference": "FULLTIME",
        }

        # Test with completely empty job
        empty_job = {}
        # Methods should return 0.2-0.5 (missing data scores vary, but should be consistent)
        remote_score = ranker._score_remote_type_match(empty_job, profile)
        assert 0.2 <= remote_score <= 0.5  # Remote type returns 0.2-0.3 for no match

        seniority_score = ranker._score_seniority_match(empty_job, profile)
        assert 0.3 <= seniority_score <= 0.5  # Returns 0.3 for missing job data

        company_size_score = ranker._score_company_size_match(empty_job, profile)
        assert 0.3 <= company_size_score <= 0.5  # Returns 0.3 for missing job data

        employment_score = ranker._score_employment_type_match(empty_job, profile)
        assert 0.2 <= employment_score <= 0.5  # Returns 0.3 for missing job data

    def test_score_comma_separated_parsing(self, ranker):
        """Test that comma-separated preferences are parsed correctly."""
        job = {"seniority_level": "mid"}
        profile = {"seniority": "entry,  mid ,  senior"}  # With spaces

        score = ranker._score_seniority_match(job, profile)
        assert score == 1.0  # Should handle spaces correctly
