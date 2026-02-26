#!/bin/bash
# Provision all unconfigured staging slots (2-10).
#
# Usage:
#   ./scripts/provision_all_staging_slots.sh [branch]
#
# Example:
#   ./scripts/provision_all_staging_slots.sh          # Uses 'main' branch
#   ./scripts/provision_all_staging_slots.sh develop  # Uses 'develop' branch

set -euo pipefail

BRANCH=${1:-main}

echo "============================================"
echo "Provisioning all staging slots"
echo "============================================"
echo "Branch: $BRANCH"
echo ""

# Check slot 1 exists (required for credentials)
if [ ! -f ~/staging-1/.env.staging-1 ]; then
    echo "ERROR: Slot 1 must be set up first"
    echo "Slot 1 provides the database credentials and API keys for other slots"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROVISION_SCRIPT="${SCRIPT_DIR}/provision_staging_slot.sh"

SUCCEEDED=()
FAILED=()
SKIPPED=()

for SLOT in {2..10}; do
    echo ""
    echo "============================================"
    echo "Slot $SLOT"
    echo "============================================"
    
    PROJECT_DIR=~/staging-$SLOT/job-search-project
    
    if [ -d "$PROJECT_DIR" ]; then
        echo "SKIPPED: Already configured"
        SKIPPED+=("$SLOT")
        continue
    fi
    
    if "$PROVISION_SCRIPT" "$SLOT" "$BRANCH"; then
        SUCCEEDED+=("$SLOT")
    else
        echo "FAILED: Provisioning failed for slot $SLOT"
        FAILED+=("$SLOT")
    fi
done

echo ""
echo ""
echo "============================================"
echo "SUMMARY"
echo "============================================"
echo "Succeeded: ${SUCCEEDED[*]:-none}"
echo "Skipped:   ${SKIPPED[*]:-none}"
echo "Failed:    ${FAILED[*]:-none}"
echo ""

if [ ${#FAILED[@]} -gt 0 ]; then
    exit 1
fi
