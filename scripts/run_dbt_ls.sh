#!/bin/bash
# Run dbt ls to list models

sg docker -c 'docker exec staging_1_airflow_scheduler python3 -c "
import subprocess
import os

os.chdir(\"/opt/airflow/dbt\")

result = subprocess.run(
    [\"dbt\", \"ls\", \"--profiles-dir\", \"/opt/airflow/dbt\"],
    capture_output=True,
    text=True,
    env={**os.environ, \"DBT_LOG_FORMAT\": \"text\", \"DBT_PRINTER_WIDTH\": \"80\"}
)

print(\"=== STDOUT ===\")
print(result.stdout)
print(\"=== STDERR ===\")
print(result.stderr)
print(f\"=== RETURN CODE: {result.returncode} ===\")
"'
