#!/bin/bash
# Fix dbt directory permissions by running as root

echo "=== Creating directories as root ==="
sg docker -c 'docker exec -u root staging_1_airflow_scheduler mkdir -p /opt/airflow/dbt/logs /opt/airflow/dbt/target'

echo "=== Changing ownership ==="
sg docker -c 'docker exec -u root staging_1_airflow_scheduler chown -R airflow:airflow /opt/airflow/dbt/logs /opt/airflow/dbt/target'

echo "=== Setting permissions ==="
sg docker -c 'docker exec -u root staging_1_airflow_scheduler chmod 755 /opt/airflow/dbt/logs /opt/airflow/dbt/target'

echo "=== Verifying ==="
sg docker -c 'docker exec staging_1_airflow_scheduler ls -la /opt/airflow/dbt/'

echo ""
echo "=== Testing dbt debug ==="
sg docker -c 'docker exec staging_1_airflow_scheduler python3 /tmp/debug_dbt_import.py'
