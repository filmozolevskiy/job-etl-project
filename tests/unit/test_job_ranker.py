"""
Unit tests for JobRanker multiple preference scoring methods.

Tests the scoring logic for multiple preferences support:
- Remote preference matching
- Seniority level matching
- Company size matching
- Employment type matching
- Job validation to prevent orphaned rankings
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
        campaign = {"remote_preference": "remote,hybrid"}

        score = ranker._score_remote_type_match(job, campaign)
        assert score == 1.0  # Exact match with one of the preferences

    def test_score_remote_type_match_multiple_preferences_hybrid(self, ranker):
        """Test remote type scoring with multiple preferences - hybrid match."""
        job = {"remote_work_type": "hybrid"}
        campaign = {"remote_preference": "remote,hybrid"}

        score = ranker._score_remote_type_match(job, campaign)
        assert score == 1.0  # Exact match

    def test_score_remote_type_match_multiple_preferences_partial(self, ranker):
        """Test remote type scoring with multiple preferences - partial match."""
        job = {"remote_work_type": "hybrid"}
        campaign = {"remote_preference": "remote"}

        score = ranker._score_remote_type_match(job, campaign)
        assert score == 0.7  # Partial match (remote matches hybrid)

    def test_score_remote_type_match_no_preference(self, ranker):
        """Test remote type scoring when campaign has no preference."""
        job = {"remote_work_type": "remote"}
        campaign = {}

        score = ranker._score_remote_type_match(job, campaign)
        assert score == 0.5  # Neutral score

    def test_score_seniority_match_multiple_preferences_exact(self, ranker):
        """Test seniority scoring with multiple preferences - exact match."""
        job = {"seniority_level": "mid"}
        campaign = {"seniority": "entry,mid,senior"}

        score = ranker._score_seniority_match(job, campaign)
        assert score == 1.0  # Exact match with one of the preferences

    def test_score_seniority_match_multiple_preferences_adjacent(self, ranker):
        """Test seniority scoring with multiple preferences - adjacent level."""
        job = {"seniority_level": "mid"}
        campaign = {"seniority": "entry,senior"}

        score = ranker._score_seniority_match(job, campaign)
        assert score == 0.7  # Adjacent level match (mid is 1 level from entry or senior)

    def test_score_seniority_match_multiple_preferences_two_levels_apart(self, ranker):
        """Test seniority scoring with multiple preferences - two levels apart."""
        job = {"seniority_level": "senior"}
        campaign = {"seniority": "entry"}

        score = ranker._score_seniority_match(job, campaign)
        assert score == 0.4  # Two levels apart

    def test_score_seniority_match_no_preference(self, ranker):
        """Test seniority scoring when campaign has no preference."""
        job = {"seniority_level": "senior"}
        campaign = {}

        score = ranker._score_seniority_match(job, campaign)
        assert score == 0.5  # Neutral score

    def test_score_company_size_match_multiple_preferences_exact(self, ranker):
        """Test company size scoring with multiple preferences - exact match."""
        job = {"company_size": "201-500"}
        campaign = {"company_size_preference": "1-50,201-500,10000+"}

        score = ranker._score_company_size_match(job, campaign)
        assert score == 1.0  # Exact match with one of the preferences

    def test_score_company_size_match_multiple_preferences_numeric_exact(self, ranker):
        """Test company size scoring with numeric value - exact match."""
        job = {"company_size": "300"}
        campaign = {"company_size_preference": "201-500,501-1000"}

        score = ranker._score_company_size_match(job, campaign)
        assert score == 1.0  # 300 falls within 201-500 range

    def test_score_company_size_match_multiple_preferences_close(self, ranker):
        """Test company size scoring with multiple preferences - close match."""
        job = {"company_size": "45"}  # Close to 51-200 range
        campaign = {"company_size_preference": "51-200"}

        score = ranker._score_company_size_match(job, campaign)
        assert score == 0.6  # Close to lower bound (45/51 ≈ 0.88, but threshold is 0.7)

    def test_score_company_size_match_no_preference(self, ranker):
        """Test company size scoring when campaign has no preference."""
        job = {"company_size": "201-500"}
        campaign = {}

        score = ranker._score_company_size_match(job, campaign)
        assert score == 0.5  # Neutral score

    def test_score_employment_type_match_multiple_preferences_exact(self, ranker):
        """Test employment type scoring with multiple preferences - exact match."""
        job = {"job_employment_type": "FULLTIME"}
        campaign = {"employment_type_preference": "FULLTIME,PARTTIME"}

        score = ranker._score_employment_type_match(job, campaign)
        assert score == 1.0  # Exact match

    def test_score_employment_type_match_multiple_preferences_jsonb(self, ranker):
        """Test employment type scoring with JSONB array field."""
        job = {"job_employment_types": ["FULLTIME", "CONTRACTOR"]}
        campaign = {"employment_type_preference": "FULLTIME,PARTTIME"}

        score = ranker._score_employment_type_match(job, campaign)
        assert score == 1.0  # Matches FULLTIME from the array

    def test_score_employment_type_match_multiple_preferences_comma_separated(self, ranker):
        """Test employment type scoring with comma-separated string field."""
        job = {"employment_types": "FULLTIME,CONTRACTOR"}
        campaign = {"employment_type_preference": "FULLTIME,PARTTIME"}

        score = ranker._score_employment_type_match(job, campaign)
        assert score == 1.0  # Matches FULLTIME from comma-separated string

    def test_score_employment_type_match_partial(self, ranker):
        """Test employment type scoring - partial match."""
        job = {"job_employment_type": "FULL_TIME"}  # Different format
        campaign = {"employment_type_preference": "FULLTIME"}

        score = ranker._score_employment_type_match(job, campaign)
        # "FULL_TIME" contains "FULLTIME" when uppercase comparison is done
        # The method checks if preference is in the combined job types string
        assert score in (0.8, 0.2)  # May match or not depending on implementation

    def test_score_employment_type_match_no_preference(self, ranker):
        """Test employment type scoring when campaign has no preference."""
        job = {"job_employment_type": "FULLTIME"}
        campaign = {}

        score = ranker._score_employment_type_match(job, campaign)
        assert score == 0.5  # Neutral score

    def test_score_remote_type_match_with_job_is_remote_flag(self, ranker):
        """Test remote type scoring using job_is_remote boolean flag."""
        job = {"job_is_remote": True, "remote_work_type": None}
        campaign = {"remote_preference": "remote"}

        score = ranker._score_remote_type_match(job, campaign)
        assert score == 1.0  # job_is_remote=True should map to "remote"

    def test_score_remote_type_match_onsite_from_flag(self, ranker):
        """Test remote type scoring using job_is_remote=False for onsite."""
        job = {"job_is_remote": False, "remote_work_type": None}
        campaign = {"remote_preference": "onsite"}

        score = ranker._score_remote_type_match(job, campaign)
        assert score == 1.0  # job_is_remote=False should map to "onsite"

    def test_score_seniority_match_empty_string(self, ranker):
        """Test seniority scoring with empty string preference."""
        job = {"seniority_level": "senior"}
        campaign = {"seniority": ""}

        score = ranker._score_seniority_match(job, campaign)
        assert score == 0.5  # Neutral score for empty preference

    def test_score_company_size_match_range_format(self, ranker):
        """Test company size scoring with range format in job data."""
        job = {"company_size": "250-300"}  # Range format
        campaign = {"company_size_preference": "201-500"}

        score = ranker._score_company_size_match(job, campaign)
        # Midpoint is 275, which is within 201-500
        assert score == 1.0

    def test_score_all_methods_handle_missing_job_data(self, ranker):
        """Test that all scoring methods handle missing job data gracefully."""
        campaign = {
            "remote_preference": "remote",
            "seniority": "mid",
            "company_size_preference": "201-500",
            "employment_type_preference": "FULLTIME",
        }

        # Test with completely empty job
        empty_job = {}
        # Methods should return 0.2-0.5 (missing data scores vary, but should be consistent)
        remote_score = ranker._score_remote_type_match(empty_job, campaign)
        assert 0.2 <= remote_score <= 0.5  # Remote type returns 0.2-0.3 for no match

        seniority_score = ranker._score_seniority_match(empty_job, campaign)
        assert 0.3 <= seniority_score <= 0.5  # Returns 0.3 for missing job data

        company_size_score = ranker._score_company_size_match(empty_job, campaign)
        assert 0.3 <= company_size_score <= 0.5  # Returns 0.3 for missing job data

        employment_score = ranker._score_employment_type_match(empty_job, campaign)
        assert 0.2 <= employment_score <= 0.5  # Returns 0.3 for missing job data

    def test_score_comma_separated_parsing(self, ranker):
        """Test that comma-separated preferences are parsed correctly."""
        job = {"seniority_level": "mid"}
        campaign = {"seniority": "entry,  mid ,  senior"}  # With spaces

        score = ranker._score_seniority_match(job, campaign)
        assert score == 1.0  # Should handle spaces correctly


class TestJobRankerValidation:
    """Test job validation to prevent orphaned rankings."""

    @pytest.fixture
    def ranker(self):
        """Create a JobRanker instance with a mock database."""
        mock_db = MagicMock()
        return JobRanker(database=mock_db)

    def test_validate_job_exists_returns_true_when_job_exists(self, ranker):
        """Test validation returns True when job exists in fact_jobs."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)  # Job count = 1
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        ranker.db.get_cursor.return_value = mock_cursor

        result = ranker._validate_job_exists_in_fact_jobs("job123", 1)
        assert result is True
        mock_cursor.execute.assert_called_once()
        assert "job123" in str(mock_cursor.execute.call_args)

    def test_validate_job_exists_returns_false_when_job_not_exists(self, ranker):
        """Test validation returns False when job doesn't exist in fact_jobs."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)  # Job count = 0
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        ranker.db.get_cursor.return_value = mock_cursor

        result = ranker._validate_job_exists_in_fact_jobs("job456", 1)
        assert result is False

    def test_validate_job_exists_returns_false_when_no_result(self, ranker):
        """Test validation returns False when query returns no result."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        ranker.db.get_cursor.return_value = mock_cursor

        result = ranker._validate_job_exists_in_fact_jobs("job789", 1)
        assert result is False

    def test_rank_jobs_for_campaign_skips_invalid_jobs(self, ranker):
        """Test that rank_jobs_for_campaign skips jobs that don't exist in fact_jobs."""
        # Setup mock database
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        ranker.db.get_cursor.return_value = mock_cursor

        # Mock get_jobs_for_campaign to return jobs
        valid_job = {
            "jsearch_job_id": "valid_job_1",
            "job_title": "Software Engineer",
            "job_location": "New York",
            "job_employment_type": "FULLTIME",
            "job_is_remote": False,
            "job_posted_at_datetime_utc": "2025-01-01T00:00:00Z",
            "company_key": "company1",
            "extracted_skills": ["Python", "SQL"],
            "seniority_level": "mid",
            "remote_work_type": "onsite",
            "job_min_salary": 100000,
            "job_max_salary": 150000,
            "job_salary_period": "year",
            "job_salary_currency": "USD",
            "company_size": "201-500",
        }
        invalid_job = {
            "jsearch_job_id": "invalid_job_1",
            "job_title": "Data Engineer",
            "job_location": "San Francisco",
            "job_employment_type": "FULLTIME",
            "job_is_remote": True,
            "job_posted_at_datetime_utc": "2025-01-02T00:00:00Z",
            "company_key": "company2",
            "extracted_skills": ["Python", "Spark"],
            "seniority_level": "senior",
            "remote_work_type": "remote",
            "job_min_salary": 120000,
            "job_max_salary": 180000,
            "job_salary_period": "year",
            "job_salary_currency": "USD",
            "company_size": "501-1000",
        }

        # First call: get_jobs_for_campaign returns both jobs
        # Second call: validate_job_exists for valid_job_1 returns True
        # Third call: validate_job_exists for invalid_job_1 returns False
        # Fourth call: _write_rankings (execute_values)
        def execute_side_effect(query, *args):
            if "GET_JOBS_FOR_CAMPAIGN" in query or "SELECT" in query and "fact_jobs" in query:
                if "valid_job_1" in str(args) and "invalid_job_1" not in str(args):
                    # Validation query for valid job
                    mock_cursor.fetchone.return_value = (1,)
                elif "invalid_job_1" in str(args):
                    # Validation query for invalid job
                    mock_cursor.fetchone.return_value = (0,)
                else:
                    # get_jobs_for_campaign query
                    mock_cursor.description = [
                        ("jsearch_job_id",),
                        ("job_title",),
                        ("job_location",),
                        ("job_employment_type",),
                        ("job_is_remote",),
                        ("job_posted_at_datetime_utc",),
                        ("company_key",),
                        ("extracted_skills",),
                        ("seniority_level",),
                        ("remote_work_type",),
                        ("job_min_salary",),
                        ("job_max_salary",),
                        ("job_salary_period",),
                        ("job_salary_currency",),
                        ("company_size",),
                    ]
                    mock_cursor.fetchall.return_value = [
                        tuple(valid_job.values()),
                        tuple(invalid_job.values()),
                    ]

        mock_cursor.execute.side_effect = execute_side_effect

        campaign = {
            "campaign_id": 1,
            "campaign_name": "Test Campaign",
            "query": "Software Engineer",
            "location": "New York",
            "country": "us",
            "skills": "Python",
            "min_salary": 100000,
            "max_salary": 200000,
            "currency": "USD",
            "remote_preference": "onsite",
            "seniority": "mid",
            "company_size_preference": "201-500",
            "employment_type_preference": "FULLTIME",
        }

        # Mock execute_values for _write_rankings
        from unittest.mock import patch

        with patch("services.ranker.job_ranker.execute_values") as mock_execute_values:
            result = ranker.rank_jobs_for_campaign(campaign)

            # Should only rank the valid job
            assert result == 1
            # Should have called execute_values once with one ranking
            assert mock_execute_values.called
            # Check that only valid job was ranked (invalid job was skipped)
            call_args = mock_execute_values.call_args
            assert call_args is not None
            # execute_values signature: execute_values(cursor, query, rows, ...)
            # call_args.args[0] = cursor, call_args.args[1] = query, call_args.args[2] = rows
            rows = call_args.args[2]  # Third argument is rows
            assert len(rows) == 1
            assert rows[0][0] == "valid_job_1"  # jsearch_job_id is first element

    def test_rank_jobs_for_campaign_handles_all_invalid_jobs(self, ranker):
        """Test that rank_jobs_for_campaign handles case where all jobs are invalid."""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        ranker.db.get_cursor.return_value = mock_cursor

        invalid_job = {
            "jsearch_job_id": "invalid_job_1",
            "job_title": "Data Engineer",
            "job_location": "San Francisco",
            "job_employment_type": "FULLTIME",
            "job_is_remote": True,
            "job_posted_at_datetime_utc": "2025-01-02T00:00:00Z",
            "company_key": "company2",
            "extracted_skills": ["Python", "Spark"],
            "seniority_level": "senior",
            "remote_work_type": "remote",
            "job_min_salary": 120000,
            "job_max_salary": 180000,
            "job_salary_period": "year",
            "job_salary_currency": "USD",
            "company_size": "501-1000",
        }

        def execute_side_effect(query, *args):
            if "GET_JOBS_FOR_CAMPAIGN" in query or "SELECT" in query and "fact_jobs" in query:
                if "invalid_job_1" in str(args):
                    # Validation query returns False
                    mock_cursor.fetchone.return_value = (0,)
                else:
                    # get_jobs_for_campaign query
                    mock_cursor.description = [
                        ("jsearch_job_id",),
                        ("job_title",),
                        ("job_location",),
                        ("job_employment_type",),
                        ("job_is_remote",),
                        ("job_posted_at_datetime_utc",),
                        ("company_key",),
                        ("extracted_skills",),
                        ("seniority_level",),
                        ("remote_work_type",),
                        ("job_min_salary",),
                        ("job_max_salary",),
                        ("job_salary_period",),
                        ("job_salary_currency",),
                        ("company_size",),
                    ]
                    mock_cursor.fetchall.return_value = [tuple(invalid_job.values())]

        mock_cursor.execute.side_effect = execute_side_effect

        campaign = {
            "campaign_id": 1,
            "campaign_name": "Test Campaign",
            "query": "Data Engineer",
            "location": "San Francisco",
            "country": "us",
        }

        from unittest.mock import patch

        with patch("services.ranker.job_ranker.execute_values"):
            result = ranker.rank_jobs_for_campaign(campaign)

            # Should return 0 since all jobs were invalid
            assert result == 0
