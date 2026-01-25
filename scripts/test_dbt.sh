#!/bin/bash
# Test dbt connectivity

echo "=== Testing dbt connectivity ==="
sg docker -c 'docker exec staging_1_airflow_scheduler bash -c "cd /opt/airflow/dbt; dbt debug 2>&1"'
