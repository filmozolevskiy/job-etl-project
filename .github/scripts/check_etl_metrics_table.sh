#!/bin/bash
# Check if etl_run_metrics table exists

SLOT="${1:-10}"
source ~/staging-${SLOT}/.env.staging-${SLOT}

echo "=== Checking marts.etl_run_metrics table for staging-${SLOT} ==="
TABLE_EXISTS=$(PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'marts' AND table_name = 'etl_run_metrics';" | xargs)

if [ "$TABLE_EXISTS" = "1" ]; then
  echo "✅ Table exists"
  PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "\d marts.etl_run_metrics" | head -30
else
  echo "❌ Table does not exist"
fi

echo ""
echo "=== Checking all marts tables ==="
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'marts' ORDER BY table_name;"
