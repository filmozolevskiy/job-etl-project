#!/bin/bash
# Verify staging slot is reachable via public URL (run after deploy-staging.sh).
# Usage: ./scripts/verify_staging_health.sh <slot> [slot ...]
# Example: ./scripts/verify_staging_health.sh 1
# Exit: 0 if all slots return 200 on /api/health, 1 otherwise.

set -euo pipefail

SLOTS=("$@")

if [ ${#SLOTS[@]} -eq 0 ]; then
  echo "Usage: $0 <slot> [slot ...]"
  echo "Example: $0 1"
  exit 1
fi

FAIL=0
for slot in "${SLOTS[@]}"; do
  if [[ ! "$slot" =~ ^[1-9]$|^10$ ]]; then
    echo "Invalid slot: $slot (must be 1-10)"
    FAIL=1
    continue
  fi
  url="https://staging-${slot}.justapply.net/api/health"
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$url" || echo "000")
  if [ "$code" = "200" ]; then
    echo "Slot $slot: OK (200)"
  else
    echo "Slot $slot: FAIL (HTTP $code) $url"
    FAIL=1
  fi
done

exit $FAIL
