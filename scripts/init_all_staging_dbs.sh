#!/bin/bash
# Initialize all staging databases (1-10) with complete schema
# 
# This script should be run from the staging droplet with proper environment
# variables set (POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_USER)
#
# Usage:
#   ./scripts/init_all_staging_dbs.sh
#
# Or for specific slots:
#   ./scripts/init_all_staging_dbs.sh 1 2 3

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check required environment variables
if [ -z "$POSTGRES_HOST" ] || [ -z "$POSTGRES_PASSWORD" ]; then
    echo "Error: POSTGRES_HOST and POSTGRES_PASSWORD must be set"
    echo "Example:"
    echo "  export POSTGRES_HOST=db-postgresql-tor1-37888-do-user-32258118-0.d.db.ondigitalocean.com"
    echo "  export POSTGRES_PASSWORD=your_password"
    exit 1
fi

# Default to all slots if none specified
if [ $# -eq 0 ]; then
    SLOTS=(1 2 3 4 5 6 7 8 9 10)
else
    SLOTS=("$@")
fi

echo "============================================"
echo "Initializing Staging Databases"
echo "============================================"
echo "Host: $POSTGRES_HOST"
echo "Slots: ${SLOTS[*]}"
echo ""

FAILED=()
SUCCEEDED=()

for SLOT in "${SLOTS[@]}"; do
    echo ""
    echo "--------------------------------------------"
    echo "Initializing slot $SLOT"
    echo "--------------------------------------------"
    
    export POSTGRES_DB="job_search_staging_$SLOT"
    
    if python3 "$PROJECT_ROOT/scripts/init_staging_db.py" "$SLOT"; then
        SUCCEEDED+=("$SLOT")
    else
        FAILED+=("$SLOT")
    fi
done

echo ""
echo "============================================"
echo "Summary"
echo "============================================"
echo "Succeeded: ${SUCCEEDED[*]:-none}"
echo "Failed: ${FAILED[*]:-none}"

if [ ${#FAILED[@]} -gt 0 ]; then
    exit 1
fi
