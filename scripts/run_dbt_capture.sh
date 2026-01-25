#!/bin/bash
# Run dbt and capture output to a file

# Run dbt inside container and save output to a file
sg docker -c 'docker exec staging_1_airflow_scheduler bash -c "cd /opt/airflow/dbt && DBT_LOG_FORMAT=text dbt run --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt >/tmp/dbt_run_output.txt 2>&1; echo EXITCODE=\$? >> /tmp/dbt_run_output.txt"'

# Copy the output file from container to host
sg docker -c 'docker cp staging_1_airflow_scheduler:/tmp/dbt_run_output.txt /tmp/dbt_run_output.txt'

# Display the output
cat /tmp/dbt_run_output.txt
