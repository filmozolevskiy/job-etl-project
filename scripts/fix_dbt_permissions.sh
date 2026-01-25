#!/bin/bash
# Fix dbt directory permissions

sg docker -c 'docker exec staging_1_airflow_scheduler mkdir -p /opt/airflow/dbt/logs /opt/airflow/dbt/target'
sg docker -c 'docker exec staging_1_airflow_scheduler chmod 777 /opt/airflow/dbt/logs /opt/airflow/dbt/target'
sg docker -c 'docker exec staging_1_airflow_scheduler ls -la /opt/airflow/dbt/'

echo ""
echo "=== Testing dbt debug again ==="
sg docker -c 'docker exec staging_1_airflow_scheduler python3 /tmp/debug_dbt_import.py'
