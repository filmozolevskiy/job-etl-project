#!/bin/bash
# Test dbt connection and configuration

cd /home/deploy/staging-10/job-search-project

echo "=== Checking dbt profiles file ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c 'cd /opt/airflow/dbt && ls -la profiles.staging.yml 2>&1 && echo "" && cat profiles.staging.yml 2>&1'

echo ""
echo "=== Testing dbt debug with explicit output ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c 'cd /opt/airflow/dbt && dbt debug --profiles-dir . --profile job_search_platform --target staging --log-level debug 2>&1 || echo "Exit code: $?"'

echo ""
echo "=== Testing environment variables ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c 'env | grep POSTGRES | sort'

echo ""
echo "=== Testing Python subprocess directly ==="
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler python3 << 'PYEOF'
import subprocess
import os
import sys

os.chdir('/opt/airflow/dbt')
cmd = ['dbt', 'debug', '--profiles-dir', '.', '--profile', 'job_search_platform', '--target', 'staging']
print(f"Running: {' '.join(cmd)}")
print(f"Working directory: {os.getcwd()}")
print(f"POSTGRES_HOST: {os.getenv('POSTGRES_HOST', 'NOT SET')}")
print(f"POSTGRES_DB: {os.getenv('POSTGRES_DB', 'NOT SET')}")

result = subprocess.run(cmd, capture_output=True, text=True)
print(f"\nReturn code: {result.returncode}")
print(f"Stdout length: {len(result.stdout)}")
print(f"Stderr length: {len(result.stderr)}")
if result.stdout:
    print(f"\nStdout:\n{result.stdout}")
if result.stderr:
    print(f"\nStderr:\n{result.stderr}")
sys.exit(result.returncode)
PYEOF
