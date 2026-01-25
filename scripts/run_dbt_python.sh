#!/bin/bash
# Run dbt via Python subprocess to capture all output

sg docker -c 'docker exec staging_1_airflow_scheduler python3 -c "
import subprocess
import os

os.chdir(\"/opt/airflow/dbt\")

result = subprocess.run(
    [\"dbt\", \"run\", \"--select\", \"staging.jsearch_job_postings\", \"--profiles-dir\", \"/opt/airflow/dbt\"],
    capture_output=True,
    text=True
)

print(\"=== STDOUT ===\")
print(result.stdout)
print(\"=== STDERR ===\")
print(result.stderr)
print(f\"=== RETURN CODE: {result.returncode} ===\")
"'
