#!/bin/bash
# Check setup and container status of all staging slots (1-10).
#
# Usage:
#   ./scripts/check_staging_slots.sh

set -euo pipefail

echo "Staging Slot Status:"
echo "===================="
echo ""

for i in {1..10}; do
    echo -n "Slot $i: "
    
    SLOT_DIR=~/staging-$i
    ENV_FILE=$SLOT_DIR/.env.staging-$i
    PROJECT_DIR=$SLOT_DIR/job-search-project
    
    if [ ! -d "$SLOT_DIR" ]; then
        echo "NOT SET UP (no directory)"
    elif [ ! -f "$ENV_FILE" ]; then
        echo "PARTIAL (directory exists, no .env file)"
    elif [ ! -d "$PROJECT_DIR" ]; then
        echo "PARTIAL (no git checkout)"
    else
        # Check if containers are running
        # Use docker compose ps -q to check for running containers
        if cd "$PROJECT_DIR" 2>/dev/null; then
            RUNNING_COUNT=$(docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-$i" ps --format json | grep -c '"State":"running"' || echo "0")
            if [ "$RUNNING_COUNT" -gt 0 ]; then
                echo "RUNNING ($RUNNING_COUNT containers)"
            else
                echo "CONFIGURED (not running)"
            fi
        else
            echo "ERROR (cannot access project directory)"
        fi
    fi
done

echo ""
echo "Done."
