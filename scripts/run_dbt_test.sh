#!/bin/bash
# Run dbt with verbose logging

sg docker -c 'docker exec staging_1_airflow_scheduler bash -c "export DBT_LOG_FORMAT=text && cd /opt/airflow/dbt && dbt run --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt 2>&1"'
