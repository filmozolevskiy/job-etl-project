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

from extractor.job_extractor import JobExtractor
from extractor.company_extractor import CompanyExtractor

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
        jsearch_api_key = os.getenv('JSEARCH_API_KEY')
        if not jsearch_api_key:
            raise ValueError("JSEARCH_API_KEY environment variable is required")
        
        # Get num_pages from environment (default: 5 pages = ~50 jobs)
        num_pages = os.getenv('JSEARCH_NUM_PAGES')
        num_pages = int(num_pages) if num_pages else 5
        logger.info(f"Extracting {num_pages} page(s) per profile (approximately {num_pages * 10} jobs)")
        
        # Initialize extractor
        extractor = JobExtractor(
            db_connection_string=db_conn_str,
            jsearch_api_key=jsearch_api_key,
            num_pages=num_pages
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
        
        # Initialize extractor
        extractor = CompanyExtractor(
            db_connection_string=db_conn_str,
            glassdoor_api_key=glassdoor_api_key
        )
        
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

