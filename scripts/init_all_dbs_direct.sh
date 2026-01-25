#!/bin/bash
# Initialize ALL staging databases (1-10) with complete schema
#
# Usage:
#   ./init_all_dbs_direct.sh
#   ./init_all_dbs_direct.sh 2 3 4  # specific slots only
#
# Requires:
#   POSTGRES_HOST, POSTGRES_PASSWORD environment variables

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check required environment variables
if [ -z "$POSTGRES_HOST" ] || [ -z "$POSTGRES_PASSWORD" ]; then
    echo "Error: POSTGRES_HOST and POSTGRES_PASSWORD must be set"
    exit 1
fi

# Default to all slots if none specified
if [ $# -eq 0 ]; then
    SLOTS=(1 2 3 4 5 6 7 8 9 10)
else
    SLOTS=("$@")
fi

echo "=========================================="
echo "Initializing ${#SLOTS[@]} Staging Databases"
echo "=========================================="
echo "Host: $POSTGRES_HOST"
echo "Slots: ${SLOTS[*]}"
echo ""

SUCCEEDED=()
FAILED=()

for SLOT in "${SLOTS[@]}"; do
    echo ""
    echo "=========================================="
    echo "Slot $SLOT"
    echo "=========================================="
    
    if /tmp/init_db_direct.sh "$SLOT"; then
        SUCCEEDED+=("$SLOT")
    else
        FAILED+=("$SLOT")
    fi
done

echo ""
echo ""
echo "=========================================="
echo "FINAL SUMMARY"
echo "=========================================="
echo "Succeeded: ${SUCCEEDED[*]:-none}"
echo "Failed: ${FAILED[*]:-none}"
echo ""

if [ ${#FAILED[@]} -gt 0 ]; then
    echo "Some databases failed initialization!"
    exit 1
else
    echo "All databases initialized successfully!"
fi
