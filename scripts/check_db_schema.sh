#!/bin/bash
# Check database schema and list tables
# Usage: source .env.staging-1 && ./check_db_schema.sh

DB_HOST="${POSTGRES_HOST:?Error: POSTGRES_HOST not set}"
DB_PORT="${POSTGRES_PORT:?Error: POSTGRES_PORT not set}"
DB_USER="${POSTGRES_USER:?Error: POSTGRES_USER not set}"
DB_PASSWORD="${POSTGRES_PASSWORD:?Error: POSTGRES_PASSWORD not set}"
DB_NAME="${POSTGRES_DB:?Error: POSTGRES_DB not set}"

echo "=== Checking database: $DB_NAME ==="
echo ""

echo "=== Schemas ==="
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema') ORDER BY schema_name;"

echo ""
echo "=== Tables in raw schema ==="
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT table_name FROM information_schema.tables WHERE table_schema='raw' ORDER BY table_name;"

echo ""
echo "=== Tables in staging schema ==="
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT table_name FROM information_schema.tables WHERE table_schema='staging' ORDER BY table_name;"

echo ""
echo "=== Tables in marts schema ==="
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT table_name FROM information_schema.tables WHERE table_schema='marts' ORDER BY table_name;"

echo ""
echo "=== Tables in public schema ==="
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"

echo ""
echo "=== etl_run_metrics table structure (if exists) ==="
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\d public.etl_run_metrics" 2>&1 || echo "Table does not exist"
