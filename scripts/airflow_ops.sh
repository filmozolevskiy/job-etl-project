#!/bin/bash
# Airflow operations script
# Usage: ./airflow_ops.sh <command> [args]

AIRFLOW_URL="http://localhost:8081"
AIRFLOW_USER="admin"
AIRFLOW_PASS="staging1admin"

case "$1" in
  unpause)
    DAG_ID="${2:-jobs_etl_daily}"
    echo "Unpausing DAG: $DAG_ID"
    curl -s -X PATCH -u "$AIRFLOW_USER:$AIRFLOW_PASS" \
      -H "Content-Type: application/json" \
      -d '{"is_paused": false}' \
      "$AIRFLOW_URL/api/v1/dags/$DAG_ID"
    ;;
  trigger)
    DAG_ID="${2:-jobs_etl_daily}"
    echo "Triggering DAG: $DAG_ID"
    curl -s -X POST -u "$AIRFLOW_USER:$AIRFLOW_PASS" \
      -H "Content-Type: application/json" \
      -d '{}' \
      "$AIRFLOW_URL/api/v1/dags/$DAG_ID/dagRuns"
    ;;
  status)
    DAG_ID="${2:-jobs_etl_daily}"
    echo "Getting latest run status for: $DAG_ID"
    curl -s -u "$AIRFLOW_USER:$AIRFLOW_PASS" \
      "$AIRFLOW_URL/api/v1/dags/$DAG_ID/dagRuns?limit=1&order_by=-execution_date"
    ;;
  list)
    echo "Listing all DAGs:"
    curl -s -u "$AIRFLOW_USER:$AIRFLOW_PASS" \
      "$AIRFLOW_URL/api/v1/dags"
    ;;
  *)
    echo "Usage: $0 {unpause|trigger|status|list} [dag_id]"
    exit 1
    ;;
esac
