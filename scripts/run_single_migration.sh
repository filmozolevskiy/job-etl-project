#!/bin/bash
# Run a single migration script on all staging databases
#
# Usage:
#   ./run_single_migration.sh <migration_file> [slots...]
#
# Example:
#   ./run_single_migration.sh 13_create_chatgpt_enrichments_table.sql 2 3 4 5 6 7 8 9 10

set -e

MIGRATION_FILE=${1:?Usage: $0 <migration_file> [slot numbers...]}
shift

if [ -z "$POSTGRES_HOST" ] || [ -z "$POSTGRES_PASSWORD" ]; then
    echo "Error: Set POSTGRES_HOST and POSTGRES_PASSWORD"
    exit 1
fi

POSTGRES_USER=${POSTGRES_USER:-doadmin}
POSTGRES_PORT=${POSTGRES_PORT:-25060}

# Default to all slots if none specified
if [ $# -eq 0 ]; then
    SLOTS=(1 2 3 4 5 6 7 8 9 10)
else
    SLOTS=("$@")
fi

INIT_DIR="/tmp/docker_init"
SQL_PATH="$INIT_DIR/$MIGRATION_FILE"

if [ ! -f "$SQL_PATH" ]; then
    echo "Error: Migration file not found: $SQL_PATH"
    exit 1
fi

export PGPASSWORD="$POSTGRES_PASSWORD"

echo "Running migration: $MIGRATION_FILE"
echo "On slots: ${SLOTS[*]}"
echo ""

for SLOT in "${SLOTS[@]}"; do
    DB_NAME="job_search_staging_$SLOT"
    echo -n "Slot $SLOT ($DB_NAME): "
    
    if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$DB_NAME" -f "$SQL_PATH" > /dev/null 2>&1; then
        echo "OK"
    else
        ERROR=$(psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$DB_NAME" -f "$SQL_PATH" 2>&1 || true)
        if echo "$ERROR" | grep -qi "already exists"; then
            echo "SKIPPED (already exists)"
        else
            echo "FAILED: $ERROR"
        fi
    fi
done

echo ""
echo "Done!"
