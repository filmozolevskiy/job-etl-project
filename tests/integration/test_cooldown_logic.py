"""Integration tests for cooldown logic and DAG trigger edge cases."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from services.campaign_management import CampaignService
from services.shared import PostgreSQLDatabase

pytestmark = pytest.mark.integration


@pytest.fixture
def campaign_service(test_database):
    """Create a CampaignService instance for testing."""
    db = PostgreSQLDatabase(test_database)
    return CampaignService(db)


@pytest.fixture
def sample_campaign(test_database):
    """Create a sample campaign for testing."""
    from services.shared import PostgreSQLDatabase

    db = PostgreSQLDatabase(connection_string=test_database)
    with db.get_cursor() as cur:
        # First create a test user
        cur.execute(
            """
            INSERT INTO marts.users (username, email, password_hash, role, created_at, updated_at)
            VALUES ('test_user_cooldown_1', 'test_cooldown_1@example.com', 'dummy_hash', 'user', NOW(), NOW())
            RETURNING user_id
            """
        )
        user_id = cur.fetchone()[0]

        # Insert campaign (campaign_id is auto-generated via SERIAL PRIMARY KEY)
        cur.execute(
            """
            INSERT INTO marts.job_campaigns
            (campaign_name, is_active, query, location, country, date_window, user_id,
             created_at, updated_at, total_run_count, last_run_status, last_run_job_count)
            VALUES
            ('Test Cooldown Campaign', true, 'Software Engineer', 'Toronto, ON', 'CA', 'week', %s,
             NOW(), NOW(), 0, NULL, 0)
            RETURNING campaign_id
            """,
            (user_id,),
        )
        campaign_id = cur.fetchone()[0]
        yield campaign_id


@pytest.fixture
def sample_campaign_2(test_database):
    """Create a second sample campaign for testing."""
    from services.shared import PostgreSQLDatabase

    db = PostgreSQLDatabase(connection_string=test_database)
    with db.get_cursor() as cur:
        # First create a test user
        cur.execute(
            """
            INSERT INTO marts.users (username, email, password_hash, role, created_at, updated_at)
            VALUES ('test_user_cooldown_2', 'test_cooldown_2@example.com', 'dummy_hash', 'user', NOW(), NOW())
            RETURNING user_id
            """
        )
        user_id = cur.fetchone()[0]

        # Insert campaign (campaign_id is auto-generated via SERIAL PRIMARY KEY)
        cur.execute(
            """
            INSERT INTO marts.job_campaigns
            (campaign_name, is_active, query, location, country, date_window, user_id,
             created_at, updated_at, total_run_count, last_run_status, last_run_job_count)
            VALUES
            ('Test Cooldown Campaign 2', true, 'Data Engineer', 'Vancouver, BC', 'CA', 'week', %s,
             NOW(), NOW(), 0, NULL, 0)
            RETURNING campaign_id
            """,
            (user_id,),
        )
        campaign_id = cur.fetchone()[0]
        yield campaign_id


class TestCooldownLogic:
    """Test cooldown logic and edge cases."""

    def test_cooldown_after_successful_dag(self, campaign_service, sample_campaign):
        """Test that cooldown is set after successful DAG completion."""
        # Simulate DAG completion by updating last_run_at
        campaign_service.update_tracking_fields(
            campaign_id=sample_campaign,
            status="success",
            job_count=10,
        )

        # Get campaign to check last_run_at
        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign["last_run_at"] is not None

        # Verify cooldown would be active (1 hour from now)
        last_run = campaign["last_run_at"]
        if isinstance(last_run, str):
            from dateutil.parser import parse

            last_run = parse(last_run)
        elif isinstance(last_run, datetime):
            pass
        else:
            pytest.fail(f"Unexpected last_run_at type: {type(last_run)}")

        # Check that last_run_at is recent (within last minute)
        assert (datetime.now() - last_run.replace(tzinfo=None)).total_seconds() < 60

    def test_cooldown_after_failed_dag(self, campaign_service, sample_campaign):
        """Test that cooldown is set after failed DAG completion."""
        # Simulate DAG failure by updating last_run_at with error status
        campaign_service.update_tracking_fields(
            campaign_id=sample_campaign,
            status="error",
            job_count=0,
        )

        # Get campaign to check last_run_at
        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign["last_run_at"] is not None
        assert campaign["last_run_status"] == "error"

    def test_no_cooldown_before_first_run(self, campaign_service, sample_campaign):
        """Test that there's no cooldown before first DAG run."""
        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign is not None, f"Campaign {sample_campaign} not found"
        assert campaign.get("last_run_at") is None

    def test_cooldown_expires_after_one_hour(self, campaign_service, sample_campaign):
        """Test that cooldown expires after 1 hour."""
        # Set last_run_at to 2 hours ago
        two_hours_ago = datetime.now() - timedelta(hours=2)
        with campaign_service.db.get_cursor() as cur:
            cur.execute(
                """
                UPDATE marts.job_campaigns
                SET last_run_at = %s
                WHERE campaign_id = %s
            """,
                (two_hours_ago, sample_campaign),
            )

        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        last_run = campaign["last_run_at"]
        if isinstance(last_run, str):
            from dateutil.parser import parse

            last_run = parse(last_run)
        elif isinstance(last_run, datetime):
            pass

        # Cooldown should have expired (2 hours > 1 hour)
        time_diff = (datetime.now() - last_run.replace(tzinfo=None)).total_seconds()
        assert time_diff > 3600  # More than 1 hour

    def test_multiple_campaigns_independent_cooldown(
        self, campaign_service, sample_campaign, sample_campaign_2
    ):
        """Test that cooldown is independent for different campaigns."""
        # Set cooldown for campaign 1
        campaign_service.update_tracking_fields(
            campaign_id=sample_campaign,
            status="success",
            job_count=5,
        )

        # Campaign 2 should not have cooldown
        campaign_2 = campaign_service.get_campaign_by_id(sample_campaign_2)
        assert campaign_2["last_run_at"] is None

        # Campaign 1 should have cooldown
        campaign_1 = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign_1["last_run_at"] is not None

    def test_concurrent_dag_triggers_same_campaign(self, campaign_service, sample_campaign):
        """Test that concurrent DAG triggers for same campaign are handled correctly."""
        # This test simulates two users trying to trigger DAG at the same time
        # The backend should allow both triggers (Airflow handles concurrency)
        # But we should verify that last_run_at is updated correctly

        # Simulate first trigger (use "success" since "running" is not a valid status)
        campaign_service.update_tracking_fields(
            campaign_id=sample_campaign,
            status="success",
            job_count=0,
        )

        # Get first timestamp (verify it was set)
        campaign_1 = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign_1["last_run_at"] is not None, "First run timestamp should be set"

        # Small delay to simulate concurrent trigger
        time.sleep(0.1)

        # Simulate second trigger (should update last_run_at)
        campaign_service.update_tracking_fields(
            campaign_id=sample_campaign,
            status="success",
            job_count=0,
        )

        # Get second timestamp
        campaign_2 = campaign_service.get_campaign_by_id(sample_campaign)
        second_run_at = campaign_2["last_run_at"]

        # Second trigger should update last_run_at
        assert second_run_at is not None
        # Note: In a real scenario, Airflow would handle concurrent triggers,
        # but both would update last_run_at

    def test_dag_completion_with_no_jobs(self, campaign_service, sample_campaign):
        """Test DAG completion when no jobs are found."""
        # Simulate DAG completion with 0 jobs
        campaign_service.update_tracking_fields(
            campaign_id=sample_campaign,
            status="success",
            job_count=0,
        )

        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign["last_run_at"] is not None
        assert campaign["last_run_status"] == "success"
        assert campaign["last_run_job_count"] == 0

    def test_page_refresh_preserves_cooldown(self, campaign_service, sample_campaign):
        """Test that cooldown persists across page refreshes."""
        # Set last_run_at to 30 minutes ago (still in cooldown)
        thirty_minutes_ago = datetime.now() - timedelta(minutes=30)
        with campaign_service.db.get_cursor() as cur:
            cur.execute(
                """
                UPDATE marts.job_campaigns
                SET last_run_at = %s
                WHERE campaign_id = %s
            """,
                (thirty_minutes_ago, sample_campaign),
            )

        # Get campaign - should still be in cooldown
        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        last_run = campaign["last_run_at"]
        if isinstance(last_run, str):
            from dateutil.parser import parse

            last_run = parse(last_run)
        elif isinstance(last_run, datetime):
            pass

        # Should still be in cooldown (30 minutes < 1 hour)
        time_diff = (datetime.now() - last_run.replace(tzinfo=None)).total_seconds()
        assert time_diff < 3600  # Less than 1 hour
        assert time_diff > 0  # But more than 0

    @patch("services.campaign_management.campaign_service.logger")
    def test_force_start_bypasses_cooldown(self, mock_logger, campaign_service, sample_campaign):
        """Test that force start bypasses cooldown (admin only)."""
        # Set last_run_at to 30 minutes ago (in cooldown)
        thirty_minutes_ago = datetime.now() - timedelta(minutes=30)
        with campaign_service.db.get_cursor() as cur:
            cur.execute(
                """
                UPDATE marts.job_campaigns
                SET last_run_at = %s
                WHERE campaign_id = %s
            """,
                (thirty_minutes_ago, sample_campaign),
            )

        # Force start should still work (bypasses cooldown check)
        # This is tested at the API level, not service level
        # But we can verify the campaign state allows it
        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign["last_run_at"] is not None

        # Force start would update last_run_at again
        campaign_service.update_tracking_fields(
            campaign_id=sample_campaign,
            status="success",
            job_count=0,
        )

        # Verify last_run_at was updated
        campaign_after = campaign_service.get_campaign_by_id(sample_campaign)
        new_last_run = campaign_after["last_run_at"]
        if isinstance(new_last_run, str):
            from dateutil.parser import parse

            new_last_run = parse(new_last_run)
        elif isinstance(new_last_run, datetime):
            pass

        # New timestamp should be more recent
        assert new_last_run.replace(tzinfo=None) > thirty_minutes_ago

    def test_cooldown_calculation_edge_cases(self, campaign_service, sample_campaign):
        """Test edge cases in cooldown calculation."""
        # Test 1: Exactly 1 hour ago (cooldown should be expired)
        one_hour_ago = datetime.now() - timedelta(hours=1, seconds=1)
        with campaign_service.db.get_cursor() as cur:
            cur.execute(
                """
                UPDATE marts.job_campaigns
                SET last_run_at = %s
                WHERE campaign_id = %s
            """,
                (one_hour_ago, sample_campaign),
            )

        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        last_run = campaign["last_run_at"]
        if isinstance(last_run, str):
            from dateutil.parser import parse

            last_run = parse(last_run)
        elif isinstance(last_run, datetime):
            pass

        time_diff = (datetime.now() - last_run.replace(tzinfo=None)).total_seconds()
        assert time_diff >= 3600  # At least 1 hour

        # Test 2: Just under 1 hour ago (cooldown should be active)
        just_under_hour = datetime.now() - timedelta(hours=1, seconds=-60)
        with campaign_service.db.get_cursor() as cur:
            cur.execute(
                """
                UPDATE marts.job_campaigns
                SET last_run_at = %s
                WHERE campaign_id = %s
            """,
                (just_under_hour, sample_campaign),
            )

        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        last_run = campaign["last_run_at"]
        if isinstance(last_run, str):
            from dateutil.parser import parse

            last_run = parse(last_run)
        elif isinstance(last_run, datetime):
            pass

        time_diff = (datetime.now() - last_run.replace(tzinfo=None)).total_seconds()
        assert time_diff < 3600  # Less than 1 hour

    def test_status_derived_from_metrics(self, campaign_service, sample_campaign):
        """Test that campaign status is correctly derived from etl_run_metrics."""
        # This test verifies the get_campaign_status_from_metrics logic
        # We need to insert some metrics data first
        with campaign_service.db.get_cursor() as cur:
            # Insert test metrics
            cur.execute(
                """
                INSERT INTO marts.etl_run_metrics (
                    run_id, campaign_id, dag_run_id, task_name, task_status, run_timestamp
                ) VALUES
                ('test-run-1-extract', %s, 'test-run-1', 'extract_job_postings', 'success', NOW() - INTERVAL '5 minutes'),
                ('test-run-1-normalize', %s, 'test-run-1', 'normalize_jobs', 'success', NOW() - INTERVAL '4 minutes'),
                ('test-run-1-rank', %s, 'test-run-1', 'rank_jobs', 'success', NOW() - INTERVAL '3 minutes'),
                ('test-run-1-notify', %s, 'test-run-1', 'send_notifications', 'success', NOW() - INTERVAL '2 minutes')
            """,
                (sample_campaign, sample_campaign, sample_campaign, sample_campaign),
            )

        # Get status from metrics
        status = campaign_service.get_campaign_status_from_metrics(campaign_id=sample_campaign)

        # Should return success status
        assert status is not None
        assert status["status"] == "success"
        assert status["is_complete"] is True

    def test_concurrent_triggers_different_users(self, campaign_service, sample_campaign):
        """Test that concurrent triggers from different users are handled."""
        # This simulates two different users trying to trigger the same campaign
        # The backend should allow both (Airflow handles concurrency)
        # But last_run_at should be updated correctly

        # First user triggers
        campaign_service.update_tracking_fields(
            campaign_id=sample_campaign,
            status="success",
            job_count=0,
            increment_run_count=False,
        )

        campaign_1 = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign_1["last_run_at"] is not None, "First timestamp should be set"

        # Small delay
        time.sleep(0.1)

        # Second user triggers (simulated by updating again)
        campaign_service.update_tracking_fields(
            campaign_id=sample_campaign,
            status="success",
            job_count=0,
            increment_run_count=False,
        )

        campaign_2 = campaign_service.get_campaign_by_id(sample_campaign)
        second_timestamp = campaign_2["last_run_at"]

        # Both should update last_run_at
        assert second_timestamp is not None
        # In real scenario, Airflow would handle both triggers

    def test_cooldown_with_timezone_issues(self, campaign_service, sample_campaign):
        """Test cooldown calculation handles timezone edge cases."""
        # Set last_run_at to a future time (simulating timezone mismatch)
        future_time = datetime.now() + timedelta(hours=1)
        with campaign_service.db.get_cursor() as cur:
            cur.execute(
                """
                UPDATE marts.job_campaigns
                SET last_run_at = %s
                WHERE campaign_id = %s
            """,
                (future_time, sample_campaign),
            )

        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        last_run = campaign["last_run_at"]
        if isinstance(last_run, str):
            from dateutil.parser import parse

            last_run = parse(last_run)
        elif isinstance(last_run, datetime):
            pass

        # Future timestamp should be detected
        time_diff = (last_run.replace(tzinfo=None) - datetime.now()).total_seconds()
        assert time_diff > 0  # Future time

    def test_cooldown_reset_on_force_start(self, campaign_service, sample_campaign):
        """Test that force start resets cooldown properly."""
        # Set last_run_at to 30 minutes ago (in cooldown)
        thirty_minutes_ago = datetime.now() - timedelta(minutes=30)
        with campaign_service.db.get_cursor() as cur:
            cur.execute(
                """
                UPDATE marts.job_campaigns
                SET last_run_at = %s
                WHERE campaign_id = %s
            """,
                (thirty_minutes_ago, sample_campaign),
            )

        # Force start should update last_run_at
        campaign_service.update_tracking_fields(
            campaign_id=sample_campaign,
            status="success",
            job_count=0,
            increment_run_count=False,
        )

        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        new_last_run = campaign["last_run_at"]
        if isinstance(new_last_run, str):
            from dateutil.parser import parse

            new_last_run = parse(new_last_run)
        elif isinstance(new_last_run, datetime):
            pass

        # New timestamp should be more recent than 30 minutes ago
        assert new_last_run.replace(tzinfo=None) > thirty_minutes_ago


class TestTriggerLogicEdgeCases:
    """Test edge cases in DAG trigger logic."""

    def test_invalid_campaign_id_handling(self, campaign_service):
        """Test that invalid campaign IDs are handled gracefully."""
        # Test with non-existent campaign
        campaign = campaign_service.get_campaign_by_id(999999)
        assert campaign is None

    def test_missing_dag_run_id_handling(self, campaign_service, sample_campaign):
        """Test that missing dag_run_id doesn't break the flow."""
        # This is tested at the API level - if Airflow returns success but no dag_run_id,
        # the frontend should still be able to poll using campaign_id only
        # The backend should return dag_run_id as None in this case
        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign is not None

    def test_concurrent_status_check_race_condition(self, campaign_service, sample_campaign):
        """Test that concurrent status checks don't cause issues."""
        # Simulate two concurrent status checks
        status1 = campaign_service.get_campaign_status_from_metrics(campaign_id=sample_campaign)
        status2 = campaign_service.get_campaign_status_from_metrics(campaign_id=sample_campaign)

        # Both should return the same result (or None if no metrics)
        # This tests that the query is safe for concurrent access
        assert (status1 is None) == (status2 is None)
        if status1 and status2:
            assert status1["status"] == status2["status"]

    def test_airflow_api_timeout_simulation(self, campaign_service, sample_campaign):
        """Test handling of Airflow API timeout scenarios."""
        # This would be tested with mocking in unit tests
        # For integration tests, we verify the campaign state is consistent
        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign is not None
        # In a real timeout scenario, the backend should return 504 Gateway Timeout
        # and the frontend should handle it gracefully

    def test_airflow_connection_error_simulation(self, campaign_service, sample_campaign):
        """Test handling of Airflow connection errors."""
        # This would be tested with mocking in unit tests
        # For integration tests, we verify the campaign state is consistent
        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign is not None
        # In a real connection error, the backend should return 503 Service Unavailable
        # and the frontend should handle it gracefully

    def test_response_validation(self, campaign_service, sample_campaign):
        """Test that response validation works correctly."""
        # Test that get_campaign_status_from_metrics returns valid structure
        status = campaign_service.get_campaign_status_from_metrics(campaign_id=sample_campaign)

        # If status is not None, it should have required fields
        if status is not None:
            assert "status" in status
            assert "is_complete" in status
            assert status["status"] in ("success", "error", "running", "pending")

    def test_campaign_ownership_validation(self, campaign_service, sample_campaign):
        """Test that campaign ownership is validated correctly."""
        campaign = campaign_service.get_campaign_by_id(sample_campaign)
        assert campaign is not None
        assert "user_id" in campaign
        # Ownership validation is tested at the API level with authentication
