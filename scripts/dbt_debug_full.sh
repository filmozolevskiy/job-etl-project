#!/bin/bash
# Test dbt connectivity with full output capture

sg docker -c 'docker exec staging_1_airflow_scheduler bash -c "cd /opt/airflow/dbt && dbt debug --no-use-colors > /tmp/dbt_debug.log 2>&1; cat /tmp/dbt_debug.log"'
