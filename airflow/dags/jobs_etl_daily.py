"""
Daily Job Postings ETL DAG

This DAG orchestrates the complete daily batch pipeline:
1. Extract job postings from JSearch API
2. Normalize jobs to staging layer
3. Extract and enrich company data from Glassdoor
4. Normalize companies to staging layer
5. Build marts (fact and dimension tables)
6. Rank jobs per profile
7. Run data quality tests
8. Send daily email notifications

Schedule: Daily at 07:00 America/Toronto
"""

from datetime import datetime, timedelta

from airflow.operators.python import PythonOperator
from task_functions import (
    dbt_modelling_task,
    dbt_tests_task,
    enrich_jobs_task,
    extract_companies_task,
    extract_job_postings_task,
    normalize_companies_task,
    normalize_jobs_task,
    rank_jobs_task,
    send_notifications_task,
)

from airflow import DAG

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

# Task: Enricher Service (NLP enrichment)
enricher = PythonOperator(
    task_id="enricher",
    python_callable=enrich_jobs_task,
    dag=dag,
)

# Task: Build marts
dbt_modelling = PythonOperator(
    task_id="dbt_modelling",
    python_callable=dbt_modelling_task,
    dag=dag,
)

# Task: Rank jobs
rank_jobs = PythonOperator(
    task_id="rank_jobs",
    python_callable=rank_jobs_task,
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

# Step 3-4: Extract and normalize companies (parallel with enricher)
normalize_jobs >> [extract_companies, enricher]
extract_companies >> normalize_companies

# Step 5-6: Enricher completes, then build marts (needs both normalize_companies and enricher)
[normalize_companies, enricher] >> dbt_modelling

# Step 7-10: Rank, test, and notify
dbt_modelling >> rank_jobs >> dbt_tests >> notify_daily
