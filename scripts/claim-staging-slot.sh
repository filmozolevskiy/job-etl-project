#!/bin/bash
# Claim a staging slot on the production Staging Dashboard (updates marts.staging_slots via API).
#
# Requires: STAGING_ADMIN_JWT (admin JWT from https://justapply.net login).
# Usage:   ./scripts/claim-staging-slot.sh <slot_id> [branch]
# Example: STAGING_ADMIN_JWT="eyJ..." ./scripts/claim-staging-slot.sh 2 main

set -euo pipefail

SLOT=${1:-}
BRANCH=${2:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")}
BASE_URL="${BASE_URL:-https://justapply.net}"
JWT="${STAGING_ADMIN_JWT:-}"

if [[ -z "$SLOT" ]] || [[ ! "$SLOT" =~ ^[1-9]$|^10$ ]]; then
  echo "Usage: $0 <slot_id> [branch]"
  echo "Slot must be 1-10. Set STAGING_ADMIN_JWT for API claim."
  exit 1
fi

if [[ -z "$JWT" ]]; then
  echo "STAGING_ADMIN_JWT not set. Claim slot $SLOT manually at $BASE_URL/staging"
  exit 0
fi

OWNER="${USER:-deploy}"
PURPOSE="Deployed via deploy-staging.sh"
# Optional: set ISSUE_ID if branch looks like linear-JOB-60-...
ISSUE_ID=""
if [[ "$BRANCH" =~ JOB-[0-9]+ ]]; then
  ISSUE_ID=$(echo "$BRANCH" | grep -oE "JOB-[0-9]+" | head -1)
fi

JSON=$(cat <<EOF
{
  "status": "In Use",
  "owner": "$OWNER",
  "branch": "$BRANCH",
  "issue_id": "$ISSUE_ID",
  "purpose": "$PURPOSE"
}
EOF
)

echo "Claiming slot $SLOT (branch=$BRANCH, owner=$OWNER)..."
HTTP=$(curl -s -w "%{http_code}" -o /tmp/claim-staging-out.json \
  -X PUT \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "$JSON" \
  "$BASE_URL/api/staging/slots/$SLOT")

if [[ "$HTTP" -ge 200 && "$HTTP" -lt 300 ]]; then
  echo "Slot $SLOT claimed successfully."
  cat /tmp/claim-staging-out.json | head -c 500
  echo ""
else
  echo "Claim failed (HTTP $HTTP):"
  cat /tmp/claim-staging-out.json
  exit 1
fi
