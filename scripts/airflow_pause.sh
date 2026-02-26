#!/bin/bash
# Pause or unpause Airflow DAGs.
#
# Usage:
#   ./scripts/airflow_pause.sh <slot_id> <dag_id> [pause|unpause]

set -euo pipefail

SLOT=${1:?Usage: $0 <slot_id> <dag_id> [pause|unpause]}
DAG_ID=${2:?Usage: $0 <slot_id> <dag_id> [pause|unpause]}
ACTION=${3:-pause}

PROJECT_DIR=~/staging-$SLOT/job-search-project

if [[ "$ACTION" != "pause" && "$ACTION" != "unpause" ]]; then
    echo "Error: Action must be 'pause' or 'unpause'"
    exit 1
fi

echo "--- ${ACTION^}ing DAG $DAG_ID on slot $SLOT ---"

if cd "$PROJECT_DIR" 2>/dev/null; then
    if docker compose -f docker-compose.yml -f docker-compose.staging.yml -p "staging-$SLOT" exec -T airflow-scheduler airflow dags "$ACTION" "$DAG_ID"; then
        echo "✓ DAG $DAG_ID ${ACTION}d successfully."
    else
        echo "✗ Failed to $ACTION DAG $DAG_ID."
        exit 1
    fi
else
    echo "✗ Error: Cannot access project directory $PROJECT_DIR"
    exit 1
fi
