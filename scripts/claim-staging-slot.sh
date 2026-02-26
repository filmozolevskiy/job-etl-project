#!/bin/bash
# Claim a staging slot on the production Staging Dashboard.
#
# Requires: STAGING_ADMIN_JWT (admin JWT from https://justapply.net login).
#
# Usage: ./scripts/claim-staging-slot.sh <slot_id> [branch]

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

OWNER="${OWNER:-${USER:-deploy}}"
ISSUE_ID="${ISSUE_ID:-}"
if [[ -z "$ISSUE_ID" ]] && [[ "$BRANCH" =~ JOB-[0-9]+ ]]; then
  ISSUE_ID=$(echo "$BRANCH" | grep -oE "JOB-[0-9]+" | head -1)
fi

if [[ -n "${PURPOSE:-}" ]]; then
  PURPOSE="$PURPOSE"
elif [[ -n "${PR_URL:-}" ]]; then
  PURPOSE="QA: ${ISSUE_ID:-branch $BRANCH} — $PR_URL"
else
  PURPOSE="${PURPOSE:-Claimed via claim-staging-slot.sh}"
fi

DEPLOYED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

escape_json() { echo "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/	/\\t/g'; }
BRANCH_E=$(escape_json "$BRANCH")
ISSUE_E=$(escape_json "$ISSUE_ID")
OWNER_E=$(escape_json "$OWNER")
PURPOSE_E=$(escape_json "$PURPOSE")

JSON=$(cat <<EOF
{
  "status": "In Use",
  "owner": "$OWNER_E",
  "branch": "$BRANCH_E",
  "issue_id": "$ISSUE_E",
  "deployed_at": "$DEPLOYED_AT",
  "purpose": "$PURPOSE_E"
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
  echo "✓ Slot $SLOT claimed successfully."
else
  echo "✗ Claim failed (HTTP $HTTP):"
  cat /tmp/claim-staging-out.json
  exit 1
fi
