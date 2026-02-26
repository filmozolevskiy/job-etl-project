#!/bin/bash
# Check database schema and list tables for a given environment.
#
# Usage:
#   source .env.staging-1 && ./scripts/check_db_schema.sh

set -euo pipefail

DB_HOST="${POSTGRES_HOST:?Error: POSTGRES_HOST not set}"
DB_PORT="${POSTGRES_PORT:?Error: POSTGRES_PORT not set}"
DB_USER="${POSTGRES_USER:?Error: POSTGRES_USER not set}"
DB_PASSWORD="${POSTGRES_PASSWORD:?Error: POSTGRES_PASSWORD not set}"
DB_NAME="${POSTGRES_DB:?Error: POSTGRES_DB not set}"

echo "=== Checking database: $DB_NAME ==="
echo "Host: $DB_HOST:$DB_PORT"
echo ""

# Function to run query and check success
run_query() {
    local label=$1
    local query=$2
    echo "--- $label ---"
    if PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "$query"; then
        echo "✓ $label retrieved."
    else
        echo "✗ Failed to retrieve $label."
        return 1
    fi
    echo ""
}

run_query "Schemas" "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema') ORDER BY schema_name;"
run_query "Tables in raw schema" "SELECT table_name FROM information_schema.tables WHERE table_schema='raw' ORDER BY table_name;"
run_query "Tables in staging schema" "SELECT table_name FROM information_schema.tables WHERE table_schema='staging' ORDER BY table_name;"
run_query "Tables in marts schema" "SELECT table_name FROM information_schema.tables WHERE table_schema='marts' ORDER BY table_name;"
run_query "Tables in public schema" "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"

echo "--- etl_run_metrics table structure (if exists) ---"
if PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\d public.etl_run_metrics" 2>&1; then
    echo "✓ etl_run_metrics structure retrieved."
else
    echo "Table public.etl_run_metrics does not exist (this may be expected)."
fi

echo ""
echo "✓ Database check complete."
