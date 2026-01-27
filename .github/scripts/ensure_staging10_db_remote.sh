#!/bin/bash
set -euo pipefail
source ~/staging-10/.env.staging-10
DB_NAME=job_search_staging_10
export PGPASSWORD="${POSTGRES_PASSWORD}"
export PGSSLMODE="${POSTGRES_SSL_MODE:-require}"
psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d defaultdb -c "CREATE DATABASE ${DB_NAME};" 2>&1 || true
psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d defaultdb -c "\l" 2>/dev/null | grep -E "job_search_staging_10|Name" || true
