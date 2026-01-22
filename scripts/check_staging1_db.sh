#!/bin/bash
# Check staging-1 database schema
# Source the env file and run checks

set -e

# Source the environment file
set -a
source ~/staging-1/.env.staging-1
set +a

echo "=== Checking database: $POSTGRES_DB ==="
echo ""

echo "=== Schemas ==="
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema') ORDER BY schema_name;"

echo ""
echo "=== Tables in raw schema ==="
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT table_name FROM information_schema.tables WHERE table_schema='raw' ORDER BY table_name;" 2>&1 || echo "(schema may not exist)"

echo ""
echo "=== Tables in staging schema ==="
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT table_name FROM information_schema.tables WHERE table_schema='staging' ORDER BY table_name;" 2>&1 || echo "(schema may not exist)"

echo ""
echo "=== Tables in marts schema ==="
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT table_name FROM information_schema.tables WHERE table_schema='marts' ORDER BY table_name;" 2>&1 || echo "(schema may not exist)"

echo ""
echo "=== Tables in public schema ==="
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"

echo ""
echo "=== etl_run_metrics table structure (if exists) ==="
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "\d public.etl_run_metrics" 2>&1 || echo "Table does not exist"
