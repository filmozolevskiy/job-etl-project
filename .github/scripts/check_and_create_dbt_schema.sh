#!/bin/bash
# Check if dbt schema exists and create if missing

SLOT="${1:-10}"
source ~/staging-${SLOT}/.env.staging-${SLOT}

echo "=== Checking dbt schema for staging-${SLOT} ==="
SCHEMA_EXISTS=$(PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -t -c "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = 'dbt';" | xargs)

if [ "$SCHEMA_EXISTS" = "0" ]; then
  echo "dbt schema does not exist. Creating..."
  PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "CREATE SCHEMA IF NOT EXISTS dbt;"
  PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "GRANT ALL PRIVILEGES ON SCHEMA dbt TO ${POSTGRES_USER};"
  echo "✅ dbt schema created"
else
  echo "✅ dbt schema already exists"
fi

echo ""
echo "=== Verifying schemas ==="
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('dbt', 'raw', 'staging', 'marts') ORDER BY schema_name;"
