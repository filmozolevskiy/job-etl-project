"""
Airflow Task Functions

Python functions to be called by Airflow PythonOperator tasks.
These functions wrap the service classes and handle environment setup.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)

# Add services directory to path so we can import extractors
sys.path.insert(0, "/opt/airflow/services")

# Import after path modification
from enricher import JobEnricher
from extractor import CompanyExtractor, GlassdoorClient, JobExtractor, JSearchClient
from notifier import EmailNotifier, NotificationCoordinator
from profile_management import ProfileService
from ranker import JobRanker
from shared import MetricsRecorder, PostgreSQLDatabase


def build_db_connection_string() -> str:
    """
    Build PostgreSQL connection string from environment variables.

    Reads from POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER,
    POSTGRES_PASSWORD, POSTGRES_DB environment variables.

    Returns:
        PostgreSQL connection string
    """
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "job_search_db")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def get_profile_service() -> ProfileService:
    """
    Get ProfileService instance with database connection.

    Returns:
        ProfileService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return ProfileService(database=database)


def get_metrics_recorder() -> MetricsRecorder:
    """
    Get MetricsRecorder instance with database connection.

    Returns:
        MetricsRecorder instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return MetricsRecorder(database=database)


def extract_job_postings_task(**context) -> dict[str, Any]:
    """
    Airflow task function to extract job postings.

    Reads active profiles from marts.profile_preferences, calls JSearch API
    for each profile, and writes raw JSON to raw.jsearch_job_postings.

    Args:
        **context: Airflow context (contains dag_run, task_instance, etc.)

    Returns:
        Dictionary with extraction results
    """
    import time

    logger.info("Starting job postings extraction task")
    start_time = time.time()
    dag_run_id = context.get("dag_run").run_id if context.get("dag_run") else "unknown"
    metrics_recorder = get_metrics_recorder()

    try:
        # Build connection string
        db_conn_str = build_db_connection_string()

        # Get API key from environment
        jsearch_api_key = os.getenv("JSEARCH_API_KEY")
        if not jsearch_api_key:
            raise ValueError("JSEARCH_API_KEY environment variable is required")

        # Get num_pages from environment (default: 5 pages = ~50 jobs)
        num_pages_env = os.getenv("JSEARCH_NUM_PAGES")
        num_pages = int(num_pages_env) if num_pages_env else 5
        logger.info(
            f"Extracting {num_pages} page(s) per profile (approximately {num_pages * 10} jobs)"
        )

        # Build dependencies
        database = PostgreSQLDatabase(connection_string=db_conn_str)
        jsearch_client = JSearchClient(api_key=jsearch_api_key)

        # Initialize extractor
        extractor = JobExtractor(
            database=database,
            jsearch_client=jsearch_client,
            num_pages=num_pages,
        )

        # Check if profile_id is specified in DAG run configuration
        dag_run = context.get("dag_run")
        profile_id_from_conf = None
        if dag_run and dag_run.conf:
            profile_id_from_conf = dag_run.conf.get("profile_id")
            # Convert to int if it's a string (JSON deserialization)
            if profile_id_from_conf and isinstance(profile_id_from_conf, str):
                try:
                    profile_id_from_conf = int(profile_id_from_conf)
                except ValueError:
                    logger.warning(f"Invalid profile_id in DAG configuration: {profile_id_from_conf}, treating as None")
                    profile_id_from_conf = None

        if profile_id_from_conf:
            # Extract jobs for a specific profile only
            logger.info(f"Extracting jobs for specific profile_id: {profile_id_from_conf}")
            profile_service = get_profile_service()
            profile = profile_service.get_profile_by_id(profile_id_from_conf)

            if not profile:
                raise ValueError(f"Profile {profile_id_from_conf} not found")

            if not profile.get("is_active"):
                logger.warning(f"Profile {profile_id_from_conf} is not active, skipping extraction")
                results = {profile_id_from_conf: 0}
            else:
                # Extract for single profile
                count = extractor.extract_jobs_for_profile(profile)
                results = {profile_id_from_conf: count}
                logger.info(f"Extracted {count} jobs for profile {profile_id_from_conf}")
        else:
            # Extract jobs for all active profiles (default behavior)
            logger.info("No profile_id specified in DAG configuration, extracting for all active profiles")
            results = extractor.extract_all_jobs()

        # Log summary
        total_jobs = sum(results.values())
        logger.info(f"Job extraction complete. Total jobs extracted: {total_jobs}")
        logger.info(f"Results per profile: {results}")

        # Update profile tracking fields for each profile using ProfileService
        # profile_service already initialized if profile_id_from_conf was set, otherwise initialize here
        if not profile_id_from_conf:
            profile_service = get_profile_service()
        for profile_id, job_count in results.items():
            try:
                profile_service.update_tracking_fields(
                    profile_id=profile_id,
                    status="success",
                    job_count=job_count,
                    increment_run_count=True,
                )
            except Exception as e:
                logger.error(
                    f"Failed to update tracking fields for profile {profile_id}: {e}",
                    exc_info=True,
                )
                # Don't raise - tracking field updates shouldn't fail the DAG

        # Record metrics
        duration = time.time() - start_time
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="extract_job_postings",
            task_status="success",
            rows_processed_raw=total_jobs,
            api_calls_made=total_jobs,  # Approximate - one API call per job
            processing_duration_seconds=duration,
            metadata={"results_by_profile": results},
        )

        # Return results for Airflow XCom (optional)
        return {"status": "success", "total_jobs": total_jobs, "results_by_profile": results}

    except Exception as e:
        logger.error(f"Job extraction task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="extract_job_postings",
            task_status="failed",
            api_errors=1,
            processing_duration_seconds=duration,
            error_message=str(e),
        )

        # Update tracking fields for all profiles with error status
        try:
            profile_service = get_profile_service()
            # Get all active profiles to mark them as failed
            profiles = profile_service.get_all_profiles()
            active_profile_ids = [p["profile_id"] for p in profiles if p.get("is_active")]
            for profile_id in active_profile_ids:
                try:
                    profile_service.update_tracking_fields(
                        profile_id=profile_id,
                        status="error",
                        job_count=0,
                        increment_run_count=True,
                    )
                except Exception as update_error:
                    logger.error(
                        f"Failed to update tracking fields for profile {profile_id}: {update_error}"
                    )
        except Exception as update_error:
            logger.error(f"Failed to update tracking fields after error: {update_error}")
        raise


def rank_jobs_task(**context) -> dict[str, Any]:
    """
    Airflow task function to rank jobs.

    Reads jobs from marts.fact_jobs and profiles from marts.profile_preferences,
    scores each job/profile pair, and writes rankings to marts.dim_ranking.

    Args:
        **context: Airflow context (contains dag_run, task_instance, etc.)

    Returns:
        Dictionary with ranking results
    """
    import time

    logger.info("Starting job ranking task")
    start_time = time.time()
    dag_run_id = context.get("dag_run").run_id if context.get("dag_run") else "unknown"
    metrics_recorder = get_metrics_recorder()

    try:
        # Build connection string
        db_conn_str = build_db_connection_string()

        # Build dependencies
        database = PostgreSQLDatabase(connection_string=db_conn_str)

        # Initialize ranker with injected dependencies
        ranker = JobRanker(database=database)

        # Rank jobs for all active profiles
        results = ranker.rank_all_jobs()

        # Log summary
        total_ranked = sum(results.values())
        logger.info(f"Job ranking complete. Total jobs ranked: {total_ranked}")
        logger.info(f"Results per profile: {results}")

        # Log summary of scoring factors used
        logger.info(
            "Ranking uses the following scoring factors: "
            "location_match (15 pts), salary_match (15 pts), company_size_match (10 pts), "
            "skills_match (15 pts), keyword_match (15 pts), employment_type_match (5 pts), "
            "seniority_match (10 pts), remote_type_match (10 pts), recency (5 pts). "
            "Detailed breakdown stored in rank_explain JSON field."
        )

        # Record metrics
        duration = time.time() - start_time
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="rank_jobs",
            task_status="success",
            rows_processed_marts=total_ranked,
            processing_duration_seconds=duration,
            metadata={"results_by_profile": results},
        )

        # Return results for Airflow XCom (optional)
        return {"status": "success", "total_ranked": total_ranked, "results_by_profile": results}

    except Exception as e:
        logger.error(f"Job ranking task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="rank_jobs",
            task_status="failed",
            processing_duration_seconds=duration,
            error_message=str(e),
        )
        raise


def send_notifications_task(**context) -> dict[str, Any]:
    """
    Airflow task function to send job notifications.

    Reads top ranked jobs from marts.dim_ranking and sends notifications
    (email, SMS, etc.) to active profiles.

    Args:
        **context: Airflow context (unused but required for Airflow callable)

    Returns:
        Dictionary with notification results
    """
    logger.info("Starting notification sending task")

    try:
        # Build connection string
        db_conn_str = build_db_connection_string()

        # Initialize email notifier
        email_notifier = EmailNotifier()

        # Initialize database dependency
        database = PostgreSQLDatabase(connection_string=db_conn_str)

        # Initialize notification coordinator with injected dependencies
        coordinator = NotificationCoordinator(
            notifier=email_notifier,
            database=database,
        )

        # Send notifications for all active profiles
        results = coordinator.send_all_notifications()

        # Log summary
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        logger.info(f"Notification sending complete. Success: {success_count}/{total_count}")

        # Update profile tracking fields to mark DAG run as complete
        # Note: We only update status and timestamp here, not job_count or run_count
        # (those were already set in the extraction task)
        profile_service = get_profile_service()
        for profile_id, notification_success in results.items():
            status = "success" if notification_success else "error"
            try:
                profile_service.update_tracking_fields(
                    profile_id=profile_id,
                    status=status,
                    job_count=0,  # Not used when increment_run_count=False
                    increment_run_count=False,
                )
            except Exception as e:
                logger.error(
                    f"Failed to update tracking fields for profile {profile_id}: {e}",
                    exc_info=True,
                )
                # Don't raise - tracking field updates shouldn't fail the DAG

        # Return results for Airflow XCom (optional)
        return {
            "status": "success",
            "success_count": success_count,
            "total_count": total_count,
            "results_by_profile": results,
        }

    except Exception as e:
        logger.error(f"Notification sending task failed: {e}", exc_info=True)
        # Don't fail the entire DAG if notifications fail - just log the error
        # This allows the pipeline to continue even if email service is down
        return {"status": "error", "error": str(e), "results_by_profile": {}}


def extract_companies_task(**context) -> dict[str, Any]:
    """
    Airflow task function to extract company data.

    Scans staging.jsearch_job_postings for employer names, identifies companies
    not yet enriched, and calls Glassdoor API to fetch company data.

    Args:
        **context: Airflow context (unused but required for Airflow callable)

    Returns:
        Dictionary with extraction results
    """
    logger.info("Starting company extraction task")

    try:
        # Build connection string
        db_conn_str = build_db_connection_string()

        # Get API key from environment
        glassdoor_api_key = os.getenv("GLASSDOOR_API_KEY")
        if not glassdoor_api_key:
            raise ValueError("GLASSDOOR_API_KEY environment variable is required")

        # Initialize dependencies and extractor
        database = PostgreSQLDatabase(connection_string=db_conn_str)
        glassdoor_client = GlassdoorClient(api_key=glassdoor_api_key)
        extractor = CompanyExtractor(database=database, glassdoor_client=glassdoor_client)

        # Extract companies (no limit - process all that need enrichment)
        results = extractor.extract_all_companies()

        # Count results by status
        success_count = sum(1 for v in results.values() if v == "success")
        not_found_count = sum(1 for v in results.values() if v == "not_found")
        error_count = sum(1 for v in results.values() if v == "error")

        logger.info(
            f"Company extraction complete. "
            f"Success: {success_count}, Not Found: {not_found_count}, Errors: {error_count}"
        )

        # Return results for Airflow XCom (optional)
        return {
            "status": "success",
            "success_count": success_count,
            "not_found_count": not_found_count,
            "error_count": error_count,
            "total_processed": len(results),
        }

    except Exception as e:
        logger.error(f"Company extraction task failed: {e}", exc_info=True)
        raise


def enrich_jobs_task(**context) -> dict[str, Any]:
    """
    Airflow task function to enrich job postings with skills and seniority.

    Reads jobs from staging.jsearch_job_postings that need enrichment,
    extracts skills using spaCy NLP and seniority from job titles,
    and updates the staging table.

    Args:
        **context: Airflow context (unused but required for Airflow callable)

    Returns:
        Dictionary with enrichment results
    """
    logger.info("Starting job enrichment task")

    try:
        # Build connection string
        db_conn_str = build_db_connection_string()

        # Get batch size from environment (default: 100)
        batch_size_env = os.getenv("ENRICHER_BATCH_SIZE")
        batch_size = int(batch_size_env) if batch_size_env else 100
        logger.info(f"Enrichment batch size: {batch_size}")

        # Build dependencies
        database = PostgreSQLDatabase(connection_string=db_conn_str)

        # Initialize enricher
        enricher = JobEnricher(database=database, batch_size=batch_size)

        # Enrich all pending jobs
        stats = enricher.enrich_all_pending_jobs()

        # Log summary
        logger.info(
            f"Job enrichment complete. "
            f"Processed: {stats['processed']}, "
            f"Enriched: {stats['enriched']}, "
            f"Errors: {stats['errors']}"
        )

        # Return results for Airflow XCom (optional)
        return {
            "status": "success",
            "processed": stats["processed"],
            "enriched": stats["enriched"],
            "errors": stats["errors"],
        }

    except Exception as e:
        logger.error(f"Job enrichment task failed: {e}", exc_info=True)
        raise
