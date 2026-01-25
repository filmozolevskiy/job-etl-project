#!/bin/bash
# Run dbt debug inside the Airflow scheduler container

sg docker -c 'docker exec staging_1_airflow_scheduler bash -c "cd /opt/airflow/dbt && dbt debug 2>&1 | tee /tmp/dbt_debug_output.txt"'

echo ""
echo "=== Exit code: $? ==="
