#!/bin/bash
# Initialize a single staging database with all migrations
#
# Usage:
#   ./init_db_direct.sh <slot_number>
#
# Requires:
#   POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD environment variables

set -e

SLOT=${1:?Usage: $0 <slot_number>}
DB_NAME="job_search_staging_$SLOT"
INIT_DIR="/tmp/docker_init"

if [ -z "$POSTGRES_HOST" ] || [ -z "$POSTGRES_PASSWORD" ]; then
    echo "Error: Set POSTGRES_HOST and POSTGRES_PASSWORD"
    exit 1
fi

POSTGRES_USER=${POSTGRES_USER:-doadmin}
POSTGRES_PORT=${POSTGRES_PORT:-25060}

export PGPASSWORD="$POSTGRES_PASSWORD"
PSQL_CMD="psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $DB_NAME"

echo "============================================"
echo "Initializing database: $DB_NAME"
echo "Host: $POSTGRES_HOST:$POSTGRES_PORT"
echo "============================================"
echo ""

# Get all SQL files sorted by numeric prefix
SQL_FILES=$(ls -1 "$INIT_DIR"/*.sql 2>/dev/null | sort -t_ -k1 -n)

if [ -z "$SQL_FILES" ]; then
    echo "Error: No SQL files found in $INIT_DIR"
    exit 1
fi

TOTAL=$(echo "$SQL_FILES" | wc -l)
CURRENT=0
FAILED=0

for SQL_FILE in $SQL_FILES; do
    CURRENT=$((CURRENT + 1))
    FILENAME=$(basename "$SQL_FILE")
    echo -n "[$CURRENT/$TOTAL] Running $FILENAME... "
    
    if $PSQL_CMD -f "$SQL_FILE" > /dev/null 2>&1; then
        echo "OK"
    else
        # Try again to see the error
        ERROR=$($PSQL_CMD -f "$SQL_FILE" 2>&1 || true)
        if echo "$ERROR" | grep -qi "already exists"; then
            echo "SKIPPED (already exists)"
        else
            echo "FAILED"
            echo "  Error: $ERROR"
            FAILED=$((FAILED + 1))
        fi
    fi
done

echo ""
echo "============================================"
echo "Verifying schema..."
echo "============================================"

# Check schemas
echo -n "Schemas: "
$PSQL_CMD -t -c "SELECT string_agg(schema_name, ', ') FROM information_schema.schemata WHERE schema_name IN ('raw', 'staging', 'marts')"

# Count tables
echo -n "Tables: "
$PSQL_CMD -t -c "SELECT COUNT(*) || ' total' FROM information_schema.tables WHERE table_schema IN ('raw', 'staging', 'marts')"

# Check key tables
echo "Key tables check:"
for TABLE in "raw.jsearch_job_postings" "staging.jsearch_job_postings" "staging.chatgpt_enrichments" "marts.dim_companies" "marts.users"; do
    SCHEMA=$(echo $TABLE | cut -d. -f1)
    NAME=$(echo $TABLE | cut -d. -f2)
    EXISTS=$($PSQL_CMD -t -c "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='$SCHEMA' AND table_name='$NAME')")
    if [ "$(echo $EXISTS | tr -d ' ')" = "t" ]; then
        echo "  ✓ $TABLE"
    else
        echo "  ✗ $TABLE MISSING"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
if [ $FAILED -gt 0 ]; then
    echo "Completed with $FAILED issues"
    exit 1
else
    echo "Database initialized successfully!"
fi
