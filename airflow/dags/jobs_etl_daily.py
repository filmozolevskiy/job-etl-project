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
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from task_functions import extract_job_postings_task, extract_companies_task, rank_jobs_task

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
normalize_jobs = BashOperator(
    task_id="normalize_jobs",
    bash_command="""
    cd /opt/airflow/dbt && \
    dbt run --select staging.jsearch_job_postings \
    --profiles-dir /opt/airflow/dbt
    """,
    dag=dag,
)

# Task: Extract companies
extract_companies = PythonOperator(
    task_id="extract_companies",
    python_callable=extract_companies_task,
    dag=dag,
)

# Task: Normalize companies
normalize_companies = BashOperator(
    task_id="normalize_companies",
    bash_command="""
    cd /opt/airflow/dbt && \
    dbt run --select staging.glassdoor_companies \
    --profiles-dir /opt/airflow/dbt
    """,
    dag=dag,
)

# Task: Enricher Service (NLP enrichment)
# TODO: Replace with actual Python service call
enricher = BashOperator(
    task_id="enricher",
    bash_command="echo 'Enricher service - TODO: Implement service call'",
    dag=dag,
)

# Task: Build marts
dbt_modelling = BashOperator(
    task_id="dbt_modelling",
    bash_command="""
    cd /opt/airflow/dbt && \
    dbt run --select marts.* \
    --profiles-dir /opt/airflow/dbt
    """,
    dag=dag,
)

# Task: Rank jobs
rank_jobs = PythonOperator(
    task_id="rank_jobs",
    python_callable=rank_jobs_task,
    dag=dag,
)

# Task: Data quality tests
dbt_tests = BashOperator(
    task_id="dbt_tests",
    bash_command="""
    cd /opt/airflow/dbt && \
    dbt test --profiles-dir /opt/airflow/dbt
    """,
    dag=dag,
)

# Task: Send daily notifications
# TODO: Replace with actual Python service call
notify_daily = BashOperator(
    task_id="notify_daily",
    bash_command="echo 'Send notifications - TODO: Implement service call'",
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

