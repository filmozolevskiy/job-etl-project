#!/bin/bash
# Pause a DAG
DAG_ID="${1:-jobs_etl_daily}"
echo "Pausing DAG: $DAG_ID"
curl -s -X PATCH -u admin:staging1admin \
  -H "Content-Type: application/json" \
  -d '{"is_paused": true}' \
  "http://localhost:8081/api/v1/dags/$DAG_ID"
