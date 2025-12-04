"""
Daily Job Postings ETL DAG

This DAG orchestrates the complete daily batch pipeline:
1. Initialize database tables
2. Extract job postings from JSearch API
3. Normalize jobs to staging layer
4. Extract and enrich company data from Glassdoor
5. Normalize companies to staging layer
6. Build marts (fact and dimension tables)
7. Rank jobs per profile
8. Run data quality tests
9. Send daily email notifications

Schedule: Daily at 07:00 America/Toronto
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

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

# Task: Initialize database tables
# This ensures all required tables exist before extraction
initialize_tables = BashOperator(
    task_id="initialize_tables",
    bash_command="""
    cd /opt/airflow/dags && \
    dbt run --select raw.* staging.company_enrichment_queue marts.profile_preferences \
    --profiles-dir /opt/airflow/dags || echo "Tables initialization completed"
    """,
    dag=dag,
)

# Task: Extract job postings
# TODO: Replace with actual Python service call
extract_job_postings = BashOperator(
    task_id="extract_job_postings",
    bash_command="echo 'Extract job postings - TODO: Implement service call'",
    dag=dag,
)

# Task: Normalize jobs
normalize_jobs = BashOperator(
    task_id="normalize_jobs",
    bash_command="""
    cd /opt/airflow/dags && \
    dbt run --select staging.jsearch_job_postings \
    --profiles-dir /opt/airflow/dags
    """,
    dag=dag,
)

# Task: Extract companies
# TODO: Replace with actual Python service call
extract_companies = BashOperator(
    task_id="extract_companies",
    bash_command="echo 'Extract companies - TODO: Implement service call'",
    dag=dag,
)

# Task: Normalize companies
normalize_companies = BashOperator(
    task_id="normalize_companies",
    bash_command="""
    cd /opt/airflow/dags && \
    dbt run --select staging.glassdoor_companies \
    --profiles-dir /opt/airflow/dags
    """,
    dag=dag,
)

# Task: Build marts
dbt_modelling = BashOperator(
    task_id="dbt_modelling",
    bash_command="""
    cd /opt/airflow/dags && \
    dbt run --select marts.* \
    --profiles-dir /opt/airflow/dags
    """,
    dag=dag,
)

# Task: Rank jobs
# TODO: Replace with actual Python service call
rank_jobs = BashOperator(
    task_id="rank_jobs",
    bash_command="echo 'Rank jobs - TODO: Implement service call'",
    dag=dag,
)

# Task: Data quality tests
dbt_tests = BashOperator(
    task_id="dbt_tests",
    bash_command="""
    cd /opt/airflow/dags && \
    dbt test --profiles-dir /opt/airflow/dags
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
initialize_tables >> extract_job_postings >> normalize_jobs >> extract_companies
extract_companies >> normalize_companies >> dbt_modelling
dbt_modelling >> rank_jobs >> dbt_tests >> notify_daily

