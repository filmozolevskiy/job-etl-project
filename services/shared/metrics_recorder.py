"""
ETL Run Metrics Recorder

Utility for recording pipeline run metrics to marts.etl_run_metrics table.
Used by Airflow tasks to track processing statistics, API usage, errors, etc.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from .database import Database

logger = logging.getLogger(__name__)


class MetricsRecorder:
    """
    Service for recording ETL run metrics.

    Records per-run statistics including:
    - Rows processed per layer
    - API calls and errors
    - Processing duration
    - Data quality test results
    - Error messages
    """

    def __init__(self, database: Database):
        """
        Initialize the metrics recorder.

        Args:
            database: Database connection interface (implements Database protocol)
        """
        if not database:
            raise ValueError("Database is required")
        self.db = database

    def record_task_metrics(
        self,
        dag_run_id: str,
        task_name: str,
        task_status: str,
        profile_id: int | None = None,
        user_id: int | None = None,
        rows_processed_raw: int = 0,
        rows_processed_staging: int = 0,
        rows_processed_marts: int = 0,
        api_calls_made: int = 0,
        api_errors: int = 0,
        processing_duration_seconds: float | None = None,
        data_quality_tests_passed: int = 0,
        data_quality_tests_failed: int = 0,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Record metrics for a single task execution.

        Args:
            dag_run_id: Airflow DAG run ID
            task_name: Name of the task (e.g., 'extract_job_postings')
            task_status: Status of the task ('success', 'failed', 'skipped')
            profile_id: Profile ID if task is profile-specific (optional)
            user_id: User ID of the profile owner (optional, will be looked up from profile_id if not provided)
            rows_processed_raw: Number of rows processed in raw layer
            rows_processed_staging: Number of rows processed in staging layer
            rows_processed_marts: Number of rows processed in marts layer
            api_calls_made: Number of API calls made
            api_errors: Number of API errors encountered
            processing_duration_seconds: Processing duration in seconds
            data_quality_tests_passed: Number of data quality tests that passed
            data_quality_tests_failed: Number of data quality tests that failed
            error_message: Error message if task failed
            metadata: Additional metadata as dictionary (will be stored as JSONB)

        Returns:
            Generated run_id (UUID string)
        """
        run_id = str(uuid.uuid4())
        run_timestamp = datetime.now()

        # Convert metadata dict to JSON string
        metadata_json = json.dumps(metadata) if metadata else None

        # If user_id is not provided but profile_id is, look it up from the database
        resolved_user_id = user_id
        if not resolved_user_id and profile_id:
            try:
                with self.db.get_cursor() as cur:
                    cur.execute(
                        "SELECT user_id FROM marts.profile_preferences WHERE profile_id = %s",
                        (profile_id,),
                    )
                    result = cur.fetchone()
                    if result:
                        resolved_user_id = result[0]
            except Exception as e:
                logger.warning(
                    f"Failed to lookup user_id for profile_id {profile_id}: {e}. "
                    "Recording metrics without user_id."
                )

        insert_query = """
            INSERT INTO marts.etl_run_metrics (
                run_id,
                dag_run_id,
                run_timestamp,
                profile_id,
                user_id,
                task_name,
                task_status,
                rows_processed_raw,
                rows_processed_staging,
                rows_processed_marts,
                api_calls_made,
                api_errors,
                processing_duration_seconds,
                data_quality_tests_passed,
                data_quality_tests_failed,
                error_message,
                metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        try:
            with self.db.get_cursor() as cur:
                cur.execute(
                    insert_query,
                    (
                        run_id,
                        dag_run_id,
                        run_timestamp,
                        profile_id,
                        resolved_user_id,
                        task_name,
                        task_status,
                        rows_processed_raw,
                        rows_processed_staging,
                        rows_processed_marts,
                        api_calls_made,
                        api_errors,
                        processing_duration_seconds,
                        data_quality_tests_passed,
                        data_quality_tests_failed,
                        error_message,
                        metadata_json,
                    ),
                )

            logger.debug(
                f"Recorded metrics for task {task_name} (run_id: {run_id}, status: {task_status})"
            )
            return run_id

        except Exception as e:
            logger.error(f"Failed to record metrics for task {task_name}: {e}", exc_info=True)
            # Don't raise - metrics recording failure shouldn't break the pipeline
            return run_id
