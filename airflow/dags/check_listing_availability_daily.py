"""
Daily listing availability check DAG

Runs once per day at 07:00 to call JSearch job-details for staging jobs
and update listing_available / listing_checked_at. Separate from jobs_etl_daily
so the main ETL is not blocked by this check. JOB-57.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from task_functions import check_job_listing_availability_task

default_args = {
    "owner": "data_engineer",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "start_date": datetime(2025, 1, 1),
}

dag = DAG(
    "check_listing_availability_daily",
    default_args=default_args,
    description="Daily JSearch job-details check; updates listing_available on staging jobs",
    schedule="0 7 * * *",  # 07:00 daily (uses Airflow default timezone, e.g. America/Toronto)
    catchup=False,
    tags=["listing", "availability", "daily"],
)

check_listing_availability = PythonOperator(
    task_id="check_listing_availability",
    python_callable=check_job_listing_availability_task,
    dag=dag,
)
