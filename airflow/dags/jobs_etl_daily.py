"""
Daily Job Postings ETL DAG

This DAG orchestrates the complete daily batch pipeline:
1. Extract job postings from JSearch API
2. Normalize jobs to staging layer
3. Extract and enrich company data from Glassdoor
4. Normalize companies to staging layer
5. Build marts (fact and dimension tables)
6. Rank jobs per campaign
7. Run data quality tests
8. Send daily email notifications

Schedule: Daily at 07:00 America/Toronto
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from task_functions import (
    chatgpt_enrich_jobs_task,
    check_job_listing_availability_task,
    dbt_modelling_chatgpt_task,
    dbt_modelling_task,
    dbt_tests_task,
    enrich_jobs_task,
    extract_companies_task,
    extract_job_postings_task,
    normalize_companies_task,
    normalize_jobs_task,
    rank_jobs_chatgpt_task,
    rank_jobs_task,
    send_notifications_task,
)

# Default arguments
default_args = {
    "owner": "data_engineer",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "start_date": datetime(2025, 1, 1),
}

# DAG definition
# Note: Timezone is set via AIRFLOW__CORE__DEFAULT_TIMEZONE in docker-compose
# Schedule: Daily at 07:00 America/Toronto
dag = DAG(
    "jobs_etl_daily",
    default_args=default_args,
    description="Daily job postings ETL pipeline",
    schedule="0 7 * * *",  # 07:00 daily (uses default timezone from config)
    catchup=False,
    tags=["etl", "jobs", "daily"],
)

# Task: Extract job postings
extract_job_postings = PythonOperator(
    task_id="extract_job_postings",
    python_callable=extract_job_postings_task,
    dag=dag,
)

# Task: Normalize jobs
normalize_jobs = PythonOperator(
    task_id="normalize_jobs",
    python_callable=normalize_jobs_task,
    dag=dag,
)

# Task: Check job listing availability (JSearch job-details; update listing_available)
check_job_listing_availability = PythonOperator(
    task_id="check_job_listing_availability",
    python_callable=check_job_listing_availability_task,
    dag=dag,
)

# Task: Extract companies
extract_companies = PythonOperator(
    task_id="extract_companies",
    python_callable=extract_companies_task,
    dag=dag,
)

# Task: Normalize companies
normalize_companies = PythonOperator(
    task_id="normalize_companies",
    python_callable=normalize_companies_task,
    dag=dag,
)

# Task: Rule-Based Enricher Service (NLP enrichment with spaCy and rules)
enricher_rule_based = PythonOperator(
    task_id="enricher_rule_based",
    python_callable=enrich_jobs_task,
    dag=dag,
)

# Task: ChatGPT Enrichment (runs in parallel with rule-based enricher, async/non-blocking)
chatgpt_enrich_jobs = PythonOperator(
    task_id="chatgpt_enrich_jobs",
    python_callable=chatgpt_enrich_jobs_task,
    dag=dag,
)

# Task: Build marts (waits for rule-based enricher, not ChatGPT)
dbt_modelling = PythonOperator(
    task_id="dbt_modelling",
    python_callable=dbt_modelling_task,
    dag=dag,
)

# Task: Rank jobs (with rule-based data)
rank_jobs = PythonOperator(
    task_id="rank_jobs",
    python_callable=rank_jobs_task,
    dag=dag,
)

# Task: Build marts with ChatGPT data (async path, runs independently)
dbt_modelling_chatgpt = PythonOperator(
    task_id="dbt_modelling_chatgpt",
    python_callable=dbt_modelling_chatgpt_task,
    dag=dag,
)

# Task: Rank jobs with ChatGPT data (async path, runs independently)
rank_jobs_chatgpt = PythonOperator(
    task_id="rank_jobs_chatgpt",
    python_callable=rank_jobs_chatgpt_task,
    dag=dag,
)

# Task: Data quality tests
dbt_tests = PythonOperator(
    task_id="dbt_tests",
    python_callable=dbt_tests_task,
    dag=dag,
)

# Task: Send daily notifications
notify_daily = PythonOperator(
    task_id="notify_daily",
    python_callable=send_notifications_task,
    dag=dag,
)

# Define task dependencies
# Step 1-2: Extract and normalize jobs
extract_job_postings >> normalize_jobs

# Step 2b: Check listing availability (job-details API) then continue
normalize_jobs >> check_job_listing_availability

# Step 3-4: Extract and normalize companies (parallel with enrichment)
check_job_listing_availability >> [extract_companies, enricher_rule_based, chatgpt_enrich_jobs]
extract_companies >> normalize_companies

# Step 5-6: Main path - rule-based enrichment → dbt modelling → ranking
# This path doesn't wait for ChatGPT enrichment (async/non-blocking)
# Jobs become available to users as soon as rank_jobs completes
[normalize_companies, enricher_rule_based] >> dbt_modelling >> rank_jobs

# Step 7-8: Tests and notifications run in parallel after rank_jobs
# These don't block job availability - users can see jobs once rank_jobs completes
rank_jobs >> [dbt_tests, notify_daily]

# Async path - ChatGPT enrichment → dbt modelling → ranking (runs independently)
# This path runs in parallel with the main path and doesn't block it
# ChatGPT enrichment updates jobs asynchronously after initial ranking
chatgpt_enrich_jobs >> dbt_modelling_chatgpt >> rank_jobs_chatgpt
