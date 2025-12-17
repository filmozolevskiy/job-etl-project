"""
Airflow Task Functions

Python functions to be called by Airflow PythonOperator tasks.
These functions wrap the service classes and handle environment setup.
"""

import os
import sys
import logging
from typing import Dict, Any

# Add services directory to path so we can import extractors
sys.path.insert(0, '/opt/airflow/services')

from extractor import JobExtractor, CompanyExtractor, JSearchClient, GlassdoorClient
from shared import PostgreSQLDatabase
from ranker import JobRanker
from notifier.email_notifier import EmailNotifier
from notifier.notification_coordinator import NotificationCoordinator

logger = logging.getLogger(__name__)


def build_db_connection_string() -> str:
    """
    Build PostgreSQL connection string from environment variables.
    
    Reads from POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, 
    POSTGRES_PASSWORD, POSTGRES_DB environment variables.
    
    Returns:
        PostgreSQL connection string
    """
    host = os.getenv('POSTGRES_HOST', 'postgres')
    port = os.getenv('POSTGRES_PORT', '5432')
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', 'postgres')
    db = os.getenv('POSTGRES_DB', 'job_search_db')
    
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def extract_job_postings_task(**context) -> Dict[str, Any]:
    """
    Airflow task function to extract job postings.
    
    Reads active profiles from marts.profile_preferences, calls JSearch API
    for each profile, and writes raw JSON to raw.jsearch_job_postings.
    
    Args:
        **context: Airflow context (unused but required for Airflow callable)
        
    Returns:
        Dictionary with extraction results
    """
    logger.info("Starting job postings extraction task")
    
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
        
        # Extract jobs for all active profiles
        results = extractor.extract_all_jobs()
        
        # Log summary
        total_jobs = sum(results.values())
        logger.info(f"Job extraction complete. Total jobs extracted: {total_jobs}")
        logger.info(f"Results per profile: {results}")
        
        # Return results for Airflow XCom (optional)
        return {
            'status': 'success',
            'total_jobs': total_jobs,
            'results_by_profile': results
        }
        
    except Exception as e:
        logger.error(f"Job extraction task failed: {e}", exc_info=True)
        raise


def rank_jobs_task(**context) -> Dict[str, Any]:
    """
    Airflow task function to rank jobs.
    
    Reads jobs from marts.fact_jobs and profiles from marts.profile_preferences,
    scores each job/profile pair, and writes rankings to marts.dim_ranking.
    
    Args:
        **context: Airflow context (unused but required for Airflow callable)
        
    Returns:
        Dictionary with ranking results
    """
    logger.info("Starting job ranking task")
    
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
        
        # Return results for Airflow XCom (optional)
        return {
            'status': 'success',
            'total_ranked': total_ranked,
            'results_by_profile': results
        }
        
    except Exception as e:
        logger.error(f"Job ranking task failed: {e}", exc_info=True)
        raise


def send_notifications_task(**context) -> Dict[str, Any]:
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
        
        # Initialize notification coordinator with email notifier
        coordinator = NotificationCoordinator(
            notifier=email_notifier,
            db_connection_string=db_conn_str
        )
        
        # Send notifications for all active profiles
        results = coordinator.send_all_notifications()
        
        # Log summary
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        logger.info(f"Notification sending complete. Success: {success_count}/{total_count}")
        
        # Return results for Airflow XCom (optional)
        return {
            'status': 'success',
            'success_count': success_count,
            'total_count': total_count,
            'results_by_profile': results
        }
        
    except Exception as e:
        logger.error(f"Notification sending task failed: {e}", exc_info=True)
        # Don't fail the entire DAG if notifications fail - just log the error
        # This allows the pipeline to continue even if email service is down
        return {
            'status': 'error',
            'error': str(e),
            'results_by_profile': {}
        }


def extract_companies_task(**context) -> Dict[str, Any]:
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
        glassdoor_api_key = os.getenv('GLASSDOOR_API_KEY')
        if not glassdoor_api_key:
            raise ValueError("GLASSDOOR_API_KEY environment variable is required")
        
        # Initialize dependencies and extractor
        database = PostgreSQLDatabase(connection_string=db_conn_str)
        glassdoor_client = GlassdoorClient(api_key=glassdoor_api_key)
        extractor = CompanyExtractor(database=database, glassdoor_client=glassdoor_client)
        
        # Extract companies (no limit - process all that need enrichment)
        results = extractor.extract_all_companies()
        
        # Count results by status
        success_count = sum(1 for v in results.values() if v == 'success')
        not_found_count = sum(1 for v in results.values() if v == 'not_found')
        error_count = sum(1 for v in results.values() if v == 'error')
        
        logger.info(
            f"Company extraction complete. "
            f"Success: {success_count}, Not Found: {not_found_count}, Errors: {error_count}"
        )
        
        # Return results for Airflow XCom (optional)
        return {
            'status': 'success',
            'success_count': success_count,
            'not_found_count': not_found_count,
            'error_count': error_count,
            'total_processed': len(results)
        }
        
    except Exception as e:
        logger.error(f"Company extraction task failed: {e}", exc_info=True)
        raise

