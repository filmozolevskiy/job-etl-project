"""
Airflow Task Functions

Python functions to be called by Airflow PythonOperator tasks.
These functions wrap the service classes and handle environment setup.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from environment-specific .env file
# Defaults to .env.development if ENVIRONMENT is not set
# In Docker, repo root is at /opt/airflow
if Path("/opt/airflow").exists():
    repo_root = Path("/opt/airflow")
else:
    # Fallback for local development
    repo_root = Path(__file__).resolve().parents[2]

environment = os.getenv("ENVIRONMENT", "development")
env_file = repo_root / f".env.{environment}"
if env_file.exists():
    load_dotenv(env_file, override=True)
else:
    # Fallback to .env if environment-specific file doesn't exist
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)

# Add services directory to path so we can import extractors
sys.path.insert(0, "/opt/airflow/services")

# Import after path modification
from campaign_management import CampaignService
from enricher import ChatGPTEnricher, JobEnricher
from extractor import CompanyExtractor, GlassdoorClient, JobExtractor, JSearchClient
from notifier import EmailNotifier, NotificationCoordinator
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


def get_campaign_service() -> CampaignService:
    """
    Get CampaignService instance with database connection.

    Returns:
        CampaignService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return CampaignService(database=database)


def get_metrics_recorder() -> MetricsRecorder:
    """
    Get MetricsRecorder instance with database connection.

    Returns:
        MetricsRecorder instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return MetricsRecorder(database=database)


def get_campaign_id_from_context(context: dict[str, Any]) -> int | None:
    """
    Extract campaign_id from DAG run configuration.

    Args:
        context: Airflow context dictionary

    Returns:
        Campaign ID if present in DAG run config, None otherwise
    """
    try:
        dag_run = context.get("dag_run")
        if dag_run and dag_run.conf:
            campaign_id_from_conf = dag_run.conf.get("campaign_id")
            # Convert to int if it's a string (JSON deserialization)
            if campaign_id_from_conf and isinstance(campaign_id_from_conf, str):
                try:
                    return int(campaign_id_from_conf)
                except ValueError:
                    logger.warning(
                        f"Invalid campaign_id in DAG configuration: {campaign_id_from_conf}, treating as None"
                    )
                    return None
            elif campaign_id_from_conf:
                return campaign_id_from_conf
    except Exception:
        pass  # If we can't get campaign_id, return None
    return None


def extract_job_postings_task(**context) -> dict[str, Any]:
    """
    Airflow task function to extract job postings.

    Reads active campaigns from marts.job_campaigns, calls JSearch API
    for each campaign, and writes raw JSON to raw.jsearch_job_postings.

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
            f"Extracting {num_pages} page(s) per campaign (approximately {num_pages * 10} jobs)"
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

        # Check if campaign_id is specified in DAG run configuration
        campaign_id_from_conf = get_campaign_id_from_context(context)

        if campaign_id_from_conf:
            # Extract jobs for a specific campaign only
            logger.info(f"Extracting jobs for specific campaign_id: {campaign_id_from_conf}")
            campaign_service = get_campaign_service()
            campaign = campaign_service.get_campaign_by_id(campaign_id_from_conf)

            if not campaign:
                raise ValueError(f"Campaign {campaign_id_from_conf} not found")

            if not campaign.get("is_active"):
                logger.warning(
                    f"Campaign {campaign_id_from_conf} is not active, skipping extraction"
                )
                results = {campaign_id_from_conf: 0}
            else:
                # Extract for single campaign
                count = extractor.extract_jobs_for_campaign(campaign)
                results = {campaign_id_from_conf: count}
                logger.info(f"Extracted {count} jobs for campaign {campaign_id_from_conf}")
        else:
            # Extract jobs for all active campaigns (default behavior)
            logger.info(
                "No campaign_id specified in DAG configuration, extracting for all active campaigns"
            )
            results = extractor.extract_all_jobs()

        # Log summary
        total_jobs = sum(results.values())
        logger.info(f"Job extraction complete. Total jobs extracted: {total_jobs}")
        logger.info(f"Results per campaign: {results}")

        # Update campaign tracking fields for each campaign using CampaignService
        # campaign_service already initialized if campaign_id_from_conf was set, otherwise initialize here
        if not campaign_id_from_conf:
            campaign_service = get_campaign_service()
        for campaign_id, job_count in results.items():
            try:
                campaign_service.update_tracking_fields(
                    campaign_id=campaign_id,
                    status="success",
                    job_count=job_count,
                    increment_run_count=True,
                )
            except Exception as e:
                logger.error(
                    f"Failed to update tracking fields for campaign {campaign_id}: {e}",
                    exc_info=True,
                )
                # Don't raise - tracking field updates shouldn't fail the DAG

        # Record metrics
        duration = time.time() - start_time
        # If processing a single campaign, record with campaign_id; otherwise record without it
        # (for multi-campaign runs, we can't assign a single campaign_id)
        campaign_id_for_metrics = campaign_id_from_conf if campaign_id_from_conf else None
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="extract_job_postings",
            task_status="success",
            campaign_id=campaign_id_for_metrics,
            rows_processed_raw=total_jobs,
            api_calls_made=total_jobs,  # Approximate - one API call per job
            processing_duration_seconds=duration,
            metadata={"results_by_campaign": results},
        )

        # Return results for Airflow XCom (optional)
        return {"status": "success", "total_jobs": total_jobs, "results_by_campaign": results}

    except Exception as e:
        logger.error(f"Job extraction task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_for_metrics = get_campaign_id_from_context(context)

        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="extract_job_postings",
            task_status="failed",
            campaign_id=campaign_id_for_metrics,
            api_errors=1,
            processing_duration_seconds=duration,
            error_message=str(e),
        )

        # Update tracking fields for all campaigns with error status
        try:
            campaign_service = get_campaign_service()
            # Get all active campaigns to mark them as failed
            campaigns = campaign_service.get_all_campaigns()
            active_campaign_ids = [c["campaign_id"] for c in campaigns if c.get("is_active")]
            for campaign_id in active_campaign_ids:
                try:
                    campaign_service.update_tracking_fields(
                        campaign_id=campaign_id,
                        status="error",
                        job_count=0,
                        increment_run_count=True,
                    )
                except Exception as update_error:
                    logger.error(
                        f"Failed to update tracking fields for campaign {campaign_id}: {update_error}"
                    )
        except Exception as update_error:
            logger.error(f"Failed to update tracking fields after error: {update_error}")
        raise


def rank_jobs_task(**context) -> dict[str, Any]:
    """
    Airflow task function to rank jobs.

    Reads jobs from marts.fact_jobs and campaigns from marts.job_campaigns,
    scores each job/campaign pair, and writes rankings to marts.dim_ranking.

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

        # Extract campaign_id from DAG run config if available
        campaign_id_from_conf = get_campaign_id_from_context(context)

        # Rank jobs - for specific campaign if provided, otherwise for all campaigns
        if campaign_id_from_conf:
            # Rank jobs for a specific campaign only
            logger.info(f"Ranking jobs for specific campaign_id: {campaign_id_from_conf}")
            campaign_service = get_campaign_service()
            campaign = campaign_service.get_campaign_by_id(campaign_id_from_conf)

            if not campaign:
                raise ValueError(f"Campaign {campaign_id_from_conf} not found")

            if not campaign.get("is_active"):
                logger.warning(f"Campaign {campaign_id_from_conf} is not active, skipping ranking")
                results = {campaign_id_from_conf: 0}
            else:
                # Rank for single campaign
                count = ranker.rank_jobs_for_campaign(campaign)
                results = {campaign_id_from_conf: count}
                logger.info(f"Ranked {count} jobs for campaign {campaign_id_from_conf}")
        else:
            # Rank jobs for all active campaigns (default behavior)
            logger.info(
                "No campaign_id specified in DAG configuration, ranking for all active campaigns"
            )
            results = ranker.rank_all_jobs()

        # Log summary
        total_ranked = sum(results.values())
        logger.info(f"Job ranking complete. Total jobs ranked: {total_ranked}")
        logger.info(f"Results per campaign: {results}")

        # Log summary of scoring factors used
        logger.info(
            "Ranking uses the following scoring factors: "
            "location_match (15 pts), salary_match (15 pts), company_size_match (10 pts), "
            "skills_match (15 pts), keyword_match (15 pts), employment_type_match (5 pts), "
            "seniority_match (10 pts), remote_type_match (10 pts), recency (5 pts). "
            "Detailed breakdown stored in rank_explain JSON field."
        )

        # Record metrics
        # Extract campaign_id from DAG run config if available (even though we process all campaigns)
        campaign_id_from_conf = get_campaign_id_from_context(context)
        duration = time.time() - start_time
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="rank_jobs",
            task_status="success",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            rows_processed_marts=total_ranked,
            processing_duration_seconds=duration,
            metadata={"results_by_campaign": results},
        )

        # Return results for Airflow XCom (optional)
        return {"status": "success", "total_ranked": total_ranked, "results_by_campaign": results}

    except Exception as e:
        logger.error(f"Job ranking task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="rank_jobs",
            task_status="failed",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
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
    import time

    logger.info("Starting notification sending task")
    start_time = time.time()
    dag_run_id = context.get("dag_run").run_id if context.get("dag_run") else "unknown"
    metrics_recorder = get_metrics_recorder()

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

        # Extract campaign_id from DAG run config if available
        campaign_id_from_conf = get_campaign_id_from_context(context)

        # Send notifications - for specific campaign if provided, otherwise for all campaigns
        if campaign_id_from_conf:
            # Send notifications for a specific campaign only
            logger.info(f"Sending notifications for specific campaign_id: {campaign_id_from_conf}")
            campaign_service = get_campaign_service()
            campaign = campaign_service.get_campaign_by_id(campaign_id_from_conf)

            if not campaign:
                raise ValueError(f"Campaign {campaign_id_from_conf} not found")

            if not campaign.get("is_active"):
                logger.warning(
                    f"Campaign {campaign_id_from_conf} is not active, skipping notifications"
                )
                results = {campaign_id_from_conf: False}
            else:
                # Send for single campaign
                success = coordinator.send_notifications_for_campaign(campaign)
                results = {campaign_id_from_conf: success}
                logger.info(
                    f"Notification {'sent' if success else 'failed'} for campaign {campaign_id_from_conf}"
                )
        else:
            # Send notifications for all active campaigns (default behavior)
            logger.info(
                "No campaign_id specified in DAG configuration, sending notifications for all active campaigns"
            )
            results = coordinator.send_all_notifications()

        # Log summary
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        error_count = total_count - success_count
        logger.info(f"Notification sending complete. Success: {success_count}/{total_count}")

        # Update campaign tracking fields to mark DAG run as complete
        # Note: We only update status and timestamp here, not job_count or run_count
        # (those were already set in the extraction task)
        campaign_service = get_campaign_service()
        for campaign_id, notification_success in results.items():
            status = "success" if notification_success else "error"
            try:
                campaign_service.update_tracking_fields(
                    campaign_id=campaign_id,
                    status=status,
                    job_count=0,  # Not used when increment_run_count=False
                    increment_run_count=False,
                )
            except Exception as e:
                logger.error(
                    f"Failed to update tracking fields for campaign {campaign_id}: {e}",
                    exc_info=True,
                )
                # Don't raise - tracking field updates shouldn't fail the DAG

        # Record metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        duration = time.time() - start_time
        task_status = (
            "success" if error_count == 0 else "success"
        )  # Still success even with some errors
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="send_notifications",
            task_status=task_status,
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            metadata={
                "success_count": success_count,
                "total_count": total_count,
                "error_count": error_count,
                "results_by_campaign": results,
            },
        )

        # Return results for Airflow XCom (optional)
        return {
            "status": "success",
            "success_count": success_count,
            "total_count": total_count,
            "results_by_campaign": results,
        }

    except Exception as e:
        logger.error(f"Notification sending task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="send_notifications",
            task_status="failed",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            error_message=str(e),
        )
        # Don't fail the entire DAG if notifications fail - just log the error
        # This allows the pipeline to continue even if email service is down
        return {"status": "error", "error": str(e), "results_by_campaign": {}}


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
    import time

    logger.info("Starting company extraction task")
    start_time = time.time()
    dag_run_id = context.get("dag_run").run_id if context.get("dag_run") else "unknown"
    metrics_recorder = get_metrics_recorder()

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
        total_processed = len(results)

        logger.info(
            f"Company extraction complete. "
            f"Success: {success_count}, Not Found: {not_found_count}, Errors: {error_count}"
        )

        # Record metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        duration = time.time() - start_time
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="extract_companies",
            task_status="success",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            rows_processed_staging=total_processed,
            api_calls_made=total_processed,  # Approximate - one API call per company
            api_errors=error_count,
            processing_duration_seconds=duration,
            metadata={
                "success_count": success_count,
                "not_found_count": not_found_count,
                "error_count": error_count,
                "total_processed": total_processed,
            },
        )

        # Return results for Airflow XCom (optional)
        return {
            "status": "success",
            "success_count": success_count,
            "not_found_count": not_found_count,
            "error_count": error_count,
            "total_processed": total_processed,
        }

    except Exception as e:
        logger.error(f"Company extraction task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="extract_companies",
            task_status="failed",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            error_message=str(e),
        )
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
    import time

    logger.info("Starting job enrichment task")
    start_time = time.time()
    dag_run_id = context.get("dag_run").run_id if context.get("dag_run") else "unknown"
    metrics_recorder = get_metrics_recorder()

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

        # Extract campaign_id from DAG run config if available
        campaign_id_from_conf = get_campaign_id_from_context(context)

        # Enrich all pending jobs (filtered by campaign_id if provided)
        stats = enricher.enrich_all_pending_jobs(campaign_id=campaign_id_from_conf)

        # Log summary
        logger.info(
            f"Job enrichment complete. "
            f"Processed: {stats['processed']}, "
            f"Enriched: {stats['enriched']}, "
            f"Errors: {stats['errors']}"
        )

        # Record metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        duration = time.time() - start_time
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="enrich_jobs",
            task_status="success",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            rows_processed_staging=stats["processed"],
            processing_duration_seconds=duration,
            metadata={
                "processed": stats["processed"],
                "enriched": stats["enriched"],
                "errors": stats["errors"],
                "batch_size": batch_size,
            },
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
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="enrich_jobs",
            task_status="failed",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            error_message=str(e),
        )
        raise


def chatgpt_enrich_jobs_task(**context) -> dict[str, Any]:
    """
    Airflow task function to enrich job postings using ChatGPT.

    Reads jobs from staging.jsearch_job_postings that haven't been enriched by ChatGPT yet,
    calls OpenAI API to extract job summary, skills, and normalized location,
    and updates the staging table.

    Args:
        **context: Airflow context (unused but required for Airflow callable)

    Returns:
        Dictionary with enrichment results
    """
    import time

    logger.info("Starting ChatGPT job enrichment task")
    start_time = time.time()
    dag_run_id = context.get("dag_run").run_id if context.get("dag_run") else "unknown"
    metrics_recorder = get_metrics_recorder()

    try:
        # Build connection string
        db_conn_str = build_db_connection_string()

        # Get OpenAI API key from environment
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key or openai_api_key.lower() in ("test", "none", ""):
            logger.warning(
                "OPENAI_API_KEY not set or is invalid. Skipping ChatGPT enrichment. "
                "Set OPENAI_API_KEY environment variable to enable ChatGPT enrichment."
            )
            return {
                "status": "skipped",
                "reason": "OPENAI_API_KEY not configured or invalid",
                "processed": 0,
                "enriched": 0,
                "errors": 0,
            }

        # Get batch size from environment (default: 10 for ChatGPT to manage API costs)
        batch_size_env = os.getenv("CHATGPT_ENRICHMENT_BATCH_SIZE")
        batch_size = int(batch_size_env) if batch_size_env else 10
        logger.info(f"ChatGPT enrichment batch size: {batch_size}")

        # Get model from environment (default: gpt-5-nano per plan)
        model = os.getenv("CHATGPT_MODEL", "gpt-5-nano")
        logger.info(f"Using OpenAI model: {model}")

        # Build dependencies
        database = PostgreSQLDatabase(connection_string=db_conn_str)

        # Initialize ChatGPT enricher (may raise ValueError if API key is invalid)
        try:
            chatgpt_enricher = ChatGPTEnricher(
                database=database, api_key=openai_api_key, model=model, batch_size=batch_size
            )
        except ValueError as e:
            logger.warning(
                f"Failed to initialize ChatGPT enricher: {e}. Skipping ChatGPT enrichment."
            )
            return {
                "status": "skipped",
                "reason": str(e),
                "processed": 0,
                "enriched": 0,
                "errors": 0,
            }

        # Extract campaign_id from DAG run config if available
        campaign_id_from_conf = get_campaign_id_from_context(context)

        # Enrich all pending jobs (filtered by campaign_id if provided)
        stats = chatgpt_enricher.enrich_all_pending_jobs(campaign_id=campaign_id_from_conf)

        # Log summary
        logger.info(
            f"ChatGPT job enrichment complete. "
            f"Processed: {stats['processed']}, "
            f"Enriched: {stats['enriched']}, "
            f"Errors: {stats['errors']}"
        )

        # Record metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        duration = time.time() - start_time
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="chatgpt_enrich_jobs",
            task_status="success",
            campaign_id=campaign_id_from_conf,
            rows_processed_staging=stats["processed"],
            processing_duration_seconds=duration,
            metadata={
                "processed": stats["processed"],
                "enriched": stats["enriched"],
                "errors": stats["errors"],
                "batch_size": batch_size,
                "model": model,
            },
        )

        # Return results for Airflow XCom (optional)
        return {
            "status": "success",
            "processed": stats["processed"],
            "enriched": stats["enriched"],
            "errors": stats["errors"],
        }

    except Exception as e:
        logger.error(f"ChatGPT job enrichment task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="chatgpt_enrich_jobs",
            task_status="failed",
            campaign_id=campaign_id_from_conf,
            processing_duration_seconds=duration,
            error_message=str(e),
        )
        # Don't fail the entire DAG if ChatGPT enrichment fails - it's optional
        logger.warning(
            "ChatGPT enrichment failed but continuing DAG execution. "
            "This is a non-critical enrichment step."
        )
        return {
            "status": "error",
            "error": str(e),
            "processed": 0,
            "enriched": 0,
            "errors": 1,
        }


def normalize_jobs_task(**context) -> dict[str, Any]:
    """
    Airflow task function wrapper for normalize_jobs (dbt run).

    Executes dbt run for staging.jsearch_job_postings and records metrics.

    Args:
        **context: Airflow context (contains dag_run, task_instance, etc.)

    Returns:
        Dictionary with task results
    """
    import subprocess
    import time

    logger.info("Starting normalize_jobs task (dbt run)")
    start_time = time.time()
    dag_run_id = context.get("dag_run").run_id if context.get("dag_run") else "unknown"
    metrics_recorder = get_metrics_recorder()

    try:
        # Extract campaign_id from DAG run config if available
        campaign_id_from_conf = get_campaign_id_from_context(context)

        # Build dbt command
        dbt_cmd = [
            "dbt",
            "run",
            "--select",
            "staging.jsearch_job_postings",
            "--profiles-dir",
            "/opt/airflow/dbt",
        ]

        # Add campaign_id as variable if provided
        if campaign_id_from_conf:
            vars_json = json.dumps({"campaign_id": campaign_id_from_conf})
            dbt_cmd.extend(["--vars", vars_json])
            logger.info(f"Running dbt with campaign_id={campaign_id_from_conf}")

        # Execute dbt run command
        result = subprocess.run(
            dbt_cmd,
            cwd="/opt/airflow/dbt",
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse output to get row counts (if available)
        # dbt output typically shows "Completed successfully" and may include row counts
        output = result.stdout
        logger.info(f"dbt run output: {output}")

        # Record metrics (campaign_id_from_conf already extracted above)
        duration = time.time() - start_time
        try:
            metrics_recorder.record_task_metrics(
                dag_run_id=dag_run_id,
                task_name="normalize_jobs",
                task_status="success",
                campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
                rows_processed_staging=0,  # dbt doesn't provide row counts easily
                processing_duration_seconds=duration,
                metadata={"dbt_output": output[:1000]},  # Store first 1000 chars of output
            )
        except Exception as metrics_error:
            # Don't fail the task if metrics recording fails
            logger.warning(f"Failed to record metrics for normalize_jobs: {metrics_error}", exc_info=True)

        return {"status": "success", "output": output}

    except subprocess.CalledProcessError as e:
        logger.error(f"normalize_jobs task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="normalize_jobs",
            task_status="failed",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            error_message=f"dbt run failed: {e.stderr if e.stderr else str(e)}",
        )
        raise

    except Exception as e:
        logger.error(f"normalize_jobs task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="normalize_jobs",
            task_status="failed",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            error_message=str(e),
        )
        raise


def normalize_companies_task(**context) -> dict[str, Any]:
    """
    Airflow task function wrapper for normalize_companies (dbt run).

    Executes dbt run for staging.glassdoor_companies and records metrics.

    Args:
        **context: Airflow context (contains dag_run, task_instance, etc.)

    Returns:
        Dictionary with task results
    """
    import subprocess
    import time

    logger.info("Starting normalize_companies task (dbt run)")
    start_time = time.time()
    dag_run_id = context.get("dag_run").run_id if context.get("dag_run") else "unknown"
    metrics_recorder = get_metrics_recorder()

    try:
        # Extract campaign_id from DAG run config if available
        # Note: Companies are shared across campaigns, but we still record campaign_id in metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)

        # Build dbt command (companies don't need campaign_id filtering as they're shared)
        dbt_cmd = [
            "dbt",
            "run",
            "--select",
            "staging.glassdoor_companies",
            "--profiles-dir",
            "/opt/airflow/dbt",
        ]

        # Execute dbt run command
        result = subprocess.run(
            dbt_cmd,
            cwd="/opt/airflow/dbt",
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse output
        output = result.stdout
        logger.info(f"dbt run output: {output}")

        # Record metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        duration = time.time() - start_time
        try:
            metrics_recorder.record_task_metrics(
                dag_run_id=dag_run_id,
                task_name="normalize_companies",
                task_status="success",
                campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
                rows_processed_staging=0,  # dbt doesn't provide row counts easily
                processing_duration_seconds=duration,
                metadata={"dbt_output": output[:1000]},  # Store first 1000 chars of output
            )
        except Exception as metrics_error:
            # Don't fail the task if metrics recording fails
            logger.warning(f"Failed to record metrics for normalize_companies: {metrics_error}", exc_info=True)

        return {"status": "success", "output": output}

        return {"status": "success", "output": output}

    except subprocess.CalledProcessError as e:
        logger.error(f"normalize_companies task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="normalize_companies",
            task_status="failed",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            error_message=f"dbt run failed: {e.stderr if e.stderr else str(e)}",
        )
        raise

    except Exception as e:
        logger.error(f"normalize_companies task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="normalize_companies",
            task_status="failed",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            error_message=str(e),
        )
        raise


def dbt_modelling_task(**context) -> dict[str, Any]:
    """
    Airflow task function wrapper for dbt_modelling (dbt run).

    Executes dbt run for marts.* and records metrics.

    Args:
        **context: Airflow context (contains dag_run, task_instance, etc.)

    Returns:
        Dictionary with task results
    """
    import subprocess
    import time

    logger.info("Starting dbt_modelling task (dbt run)")
    start_time = time.time()
    dag_run_id = context.get("dag_run").run_id if context.get("dag_run") else "unknown"
    metrics_recorder = get_metrics_recorder()

    try:
        # Extract campaign_id from DAG run config if available
        campaign_id_from_conf = get_campaign_id_from_context(context)

        # Build dbt command
        dbt_cmd = [
            "dbt",
            "run",
            "--select",
            "marts.*",
            "--profiles-dir",
            "/opt/airflow/dbt",
        ]

        # Add campaign_id as variable if provided
        if campaign_id_from_conf:
            vars_json = json.dumps({"campaign_id": campaign_id_from_conf})
            dbt_cmd.extend(["--vars", vars_json])
            logger.info(f"Running dbt with campaign_id={campaign_id_from_conf}")

        # Execute dbt run command
        result = subprocess.run(
            dbt_cmd,
            cwd="/opt/airflow/dbt",
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse output
        output = result.stdout
        logger.info(f"dbt run output: {output}")

        # Record metrics (campaign_id_from_conf already extracted above)
        duration = time.time() - start_time
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="dbt_modelling",
            task_status="success",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            rows_processed_marts=0,  # dbt doesn't provide row counts easily
            processing_duration_seconds=duration,
            metadata={"dbt_output": output[:1000]},  # Store first 1000 chars of output
        )

        return {"status": "success", "output": output}

    except subprocess.CalledProcessError as e:
        logger.error(f"dbt_modelling task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="dbt_modelling",
            task_status="failed",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            error_message=f"dbt run failed: {e.stderr if e.stderr else str(e)}",
        )
        raise

    except Exception as e:
        logger.error(f"dbt_modelling task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="dbt_modelling",
            task_status="failed",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            error_message=str(e),
        )
        raise


def dbt_tests_task(**context) -> dict[str, Any]:
    """
    Airflow task function wrapper for dbt_tests (dbt test).

    Executes dbt test, parses results to count passed/failed tests, and records metrics.

    Args:
        **context: Airflow context (contains dag_run, task_instance, etc.)

    Returns:
        Dictionary with task results including test counts
    """
    import subprocess
    import time

    logger.info("Starting dbt_tests task (dbt test)")
    start_time = time.time()
    dag_run_id = context.get("dag_run").run_id if context.get("dag_run") else "unknown"
    metrics_recorder = get_metrics_recorder()

    try:
        # Extract campaign_id from DAG run config if available (for metrics recording only)
        campaign_id_from_conf = get_campaign_id_from_context(context)

        # Build dbt command
        # Note: We don't pass campaign_id to dbt tests because tests should validate
        # data quality across ALL campaigns, not just a subset. Filtering would break
        # referential integrity tests (e.g., relationships between dim_ranking and fact_jobs).
        dbt_cmd = ["dbt", "test", "--profiles-dir", "/opt/airflow/dbt"]
        logger.info(
            "Running dbt test on all data (tests validate data quality across all campaigns)"
        )

        # Execute dbt test command
        # Note: We don't use check=True so we can handle test failures gracefully
        # and still record metrics about which tests passed/failed
        result = subprocess.run(
            dbt_cmd,
            cwd="/opt/airflow/dbt",
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception on test failures
        )

        # Parse output to count passed and failed tests
        output = result.stdout + "\n" + (result.stderr or "")
        logger.info(f"dbt test output: {output}")

        # dbt test output typically contains lines like:
        # "PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5"
        # or individual test results like "PASS" or "FAIL"
        # or "Completed successfully" with test counts
        passed_count = 0
        failed_count = 0

        # Try to parse summary line (various formats)
        # Format 1: "PASS=5 WARN=0 ERROR=2 SKIP=0 TOTAL=7"
        summary_match = re.search(
            r"PASS\s*=\s*(\d+).*?(?:ERROR|FAIL)\s*=\s*(\d+)", output, re.IGNORECASE
        )
        if summary_match:
            passed_count = int(summary_match.group(1))
            failed_count = int(summary_match.group(2))
        else:
            # Format 2: "Completed successfully" with counts
            # Try to find patterns like "5 passed", "2 failed"
            passed_match = re.search(r"(\d+)\s+passed", output, re.IGNORECASE)
            failed_match = re.search(r"(\d+)\s+(?:failed|error)", output, re.IGNORECASE)
            if passed_match:
                passed_count = int(passed_match.group(1))
            if failed_match:
                failed_count = int(failed_match.group(1))

            # Fallback: count individual test result lines
            if passed_count == 0 and failed_count == 0:
                # Count lines containing "PASS" or "PASSED"
                passed_lines = re.findall(
                    r"^\s*PASS(?:ED)?\s*", output, re.MULTILINE | re.IGNORECASE
                )
                # Count lines containing "FAIL", "FAILED", or "ERROR"
                failed_lines = re.findall(
                    r"^\s*(?:FAIL(?:ED)?|ERROR)\s*", output, re.MULTILINE | re.IGNORECASE
                )
                passed_count = len(passed_lines)
                failed_count = len(failed_lines)

        logger.info(f"Data quality tests: {passed_count} passed, {failed_count} failed")

        # Record metrics with data quality test results
        campaign_id_from_conf = get_campaign_id_from_context(context)
        duration = time.time() - start_time
        task_status = "success" if failed_count == 0 else "failed"

        # Log warning if tests failed, but don't fail the task
        if failed_count > 0:
            logger.warning(
                f"Data quality tests failed: {failed_count} test(s) failed, {passed_count} passed. "
                f"This indicates a data quality issue that should be investigated. "
                f"See dbt output for details."
            )
        else:
            logger.info(f"All data quality tests passed: {passed_count} test(s) passed")

        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="dbt_tests",
            task_status=task_status,
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            data_quality_tests_passed=passed_count,
            data_quality_tests_failed=failed_count,
            metadata={
                "passed_count": passed_count,
                "failed_count": failed_count,
                "dbt_output": output[:1000],  # Store first 1000 chars of output
            },
        )

        # Return success even if tests failed - we record the failure in metrics
        # This allows the DAG to continue while still tracking data quality issues
        return {
            "status": "success",  # Always return success to allow DAG to continue
            "passed_count": passed_count,
            "failed_count": failed_count,
            "tests_passed": failed_count == 0,  # Indicate if tests actually passed
            "output": output,
        }

    except Exception as e:
        # This should not happen since we set check=False, but handle it just in case
        logger.error(f"dbt_tests task encountered unexpected error: {e}", exc_info=True)
        duration = time.time() - start_time

        # Try to parse test results from error output if available
        # This provides better metrics even for unexpected errors
        output = str(e)
        passed_count = 0
        failed_count = 0

        # Check if error has attributes that might contain output (e.g., CalledProcessError)
        if hasattr(e, "stdout") and e.stdout:
            output = e.stdout + "\n" + (getattr(e, "stderr", "") or "")
            # Try to parse test results from output
            summary_match = re.search(
                r"PASS\s*=\s*(\d+).*?(?:ERROR|FAIL)\s*=\s*(\d+)", output, re.IGNORECASE
            )
            if summary_match:
                passed_count = int(summary_match.group(1))
                failed_count = int(summary_match.group(2))
            else:
                # Try alternative parsing
                passed_match = re.search(r"(\d+)\s+passed", output, re.IGNORECASE)
                failed_match = re.search(r"(\d+)\s+(?:failed|error)", output, re.IGNORECASE)
                if passed_match:
                    passed_count = int(passed_match.group(1))
                if failed_match:
                    failed_count = int(failed_match.group(1))

        # Record failure metrics with test counts if available
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="dbt_tests",
            task_status="failed",
            campaign_id=campaign_id_from_conf,  # Record campaign_id if DAG was triggered for specific campaign
            processing_duration_seconds=duration,
            data_quality_tests_passed=passed_count,
            data_quality_tests_failed=failed_count,
            error_message=str(e),
            metadata={
                "error_type": type(e).__name__,
                "output": output[:1000] if len(output) > 1000 else output,
            },
        )
        raise


def dbt_modelling_chatgpt_task(**context) -> dict[str, Any]:
    """
    Airflow task function wrapper for dbt_modelling with ChatGPT data (dbt run).

    Executes dbt run for marts.* to include ChatGPT-enriched data and records metrics.
    This is part of the async ChatGPT enrichment path in the main DAG, running after
    chatgpt_enrich_jobs completes.

    Args:
        **context: Airflow context (contains dag_run, task_instance, etc.)

    Returns:
        Dictionary with task results
    """
    import subprocess
    import time

    logger.info("Starting dbt_modelling_chatgpt task (dbt run with ChatGPT data)")
    start_time = time.time()
    dag_run_id = context.get("dag_run").run_id if context.get("dag_run") else "unknown"
    metrics_recorder = get_metrics_recorder()

    try:
        # Extract campaign_id from DAG run config if available
        campaign_id_from_conf = get_campaign_id_from_context(context)

        # Build dbt command
        dbt_cmd = [
            "dbt",
            "run",
            "--select",
            "marts.*",
            "--profiles-dir",
            "/opt/airflow/dbt",
        ]

        # Add campaign_id as variable if provided
        if campaign_id_from_conf:
            vars_json = json.dumps({"campaign_id": campaign_id_from_conf})
            dbt_cmd.extend(["--vars", vars_json])
            logger.info(f"Running dbt with campaign_id={campaign_id_from_conf}")

        # Execute dbt run command
        result = subprocess.run(
            dbt_cmd,
            cwd="/opt/airflow/dbt",
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse output
        output = result.stdout
        logger.info(f"dbt run output: {output}")

        # Record metrics
        duration = time.time() - start_time
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="dbt_modelling_chatgpt",
            task_status="success",
            campaign_id=campaign_id_from_conf,
            rows_processed_marts=0,  # dbt doesn't provide row counts easily
            processing_duration_seconds=duration,
            metadata={"dbt_output": output[:1000], "source": "chatgpt_enrichment"},
        )

        return {"status": "success", "output": output}

    except subprocess.CalledProcessError as e:
        logger.error(f"dbt_modelling_chatgpt task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="dbt_modelling_chatgpt",
            task_status="failed",
            campaign_id=campaign_id_from_conf,
            processing_duration_seconds=duration,
            error_message=f"dbt run failed: {e.stderr if e.stderr else str(e)}",
        )
        raise

    except Exception as e:
        logger.error(f"dbt_modelling_chatgpt task failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="dbt_modelling_chatgpt",
            task_status="failed",
            campaign_id=campaign_id_from_conf,
            processing_duration_seconds=duration,
            error_message=str(e),
        )
        raise


def rank_jobs_chatgpt_task(**context) -> dict[str, Any]:
    """
    Airflow task function to rank jobs with ChatGPT-enriched data.

    Reads jobs from marts.fact_jobs (which includes ChatGPT-enriched fields via COALESCE)
    and campaigns from marts.job_campaigns, scores each job/campaign pair,
    and writes rankings to marts.dim_ranking.

    This is part of the async ChatGPT enrichment path in the main DAG, running after
    dbt_modelling_chatgpt completes.

    Args:
        **context: Airflow context (contains dag_run, task_instance, etc.)

    Returns:
        Dictionary with ranking results
    """
    import time

    logger.info("Starting job ranking task with ChatGPT-enriched data")
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

        # Extract campaign_id from DAG run config if available
        campaign_id_from_conf = get_campaign_id_from_context(context)

        # Rank jobs - for specific campaign if provided, otherwise for all campaigns
        if campaign_id_from_conf:
            # Rank jobs for a specific campaign only
            logger.info(f"Ranking jobs for specific campaign_id: {campaign_id_from_conf}")
            campaign_service = get_campaign_service()
            campaign = campaign_service.get_campaign_by_id(campaign_id_from_conf)

            if not campaign:
                raise ValueError(f"Campaign {campaign_id_from_conf} not found")

            if not campaign.get("is_active"):
                logger.warning(f"Campaign {campaign_id_from_conf} is not active, skipping ranking")
                results = {campaign_id_from_conf: 0}
            else:
                # Rank for single campaign
                count = ranker.rank_jobs_for_campaign(campaign)
                results = {campaign_id_from_conf: count}
                logger.info(f"Ranked {count} jobs for campaign {campaign_id_from_conf}")
        else:
            # Rank jobs for all active campaigns (default behavior)
            logger.info(
                "No campaign_id specified in DAG configuration, ranking for all active campaigns"
            )
            results = ranker.rank_all_jobs()

        # Log summary
        total_ranked = sum(results.values())
        logger.info(f"Job ranking complete (with ChatGPT data). Total jobs ranked: {total_ranked}")
        logger.info(f"Results per campaign: {results}")

        # Record metrics
        duration = time.time() - start_time
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="rank_jobs_chatgpt",
            task_status="success",
            campaign_id=campaign_id_from_conf,
            rows_processed_marts=total_ranked,
            processing_duration_seconds=duration,
            metadata={"results_by_campaign": results, "source": "chatgpt_enrichment"},
        )

        # Return results for Airflow XCom (optional)
        return {"status": "success", "total_ranked": total_ranked, "results_by_campaign": results}

    except Exception as e:
        logger.error(f"Job ranking task (ChatGPT) failed: {e}", exc_info=True)
        duration = time.time() - start_time

        # Record failure metrics
        campaign_id_from_conf = get_campaign_id_from_context(context)
        metrics_recorder.record_task_metrics(
            dag_run_id=dag_run_id,
            task_name="rank_jobs_chatgpt",
            task_status="failed",
            campaign_id=campaign_id_from_conf,
            processing_duration_seconds=duration,
            error_message=str(e),
        )
        raise
