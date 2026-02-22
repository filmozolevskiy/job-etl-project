#!/bin/bash
# Claim a staging slot on the production Staging Dashboard (updates marts.staging_slots via API).
# All metadata is submitted: branch, issue_id, owner, purpose (PR/Linear link), and claimed time.
#
# Requires: STAGING_ADMIN_JWT (admin JWT from https://justapply.net login).
#
# Usage:   ./scripts/claim-staging-slot.sh <slot_id> [branch]
#
# Required for full metadata (recommended): set PURPOSE to include PR and/or Linear link.
# Optional env:
#   ISSUE_ID    Linear issue (e.g. JOB-60); auto-parsed from branch if not set.
#   PURPOSE     e.g. "QA: JOB-60 — https://github.com/org/repo/pull/42" or "QA: https://linear.app/…/issue/JOB-60"
#   PR_URL      If set, appended to PURPOSE when PURPOSE is not set or is default.
#   OWNER       Default: $USER or deploy.
#
# Example (full metadata):
#   STAGING_ADMIN_JWT="eyJ..." PURPOSE="QA: JOB-60 — https://github.com/filmozolevskiy/job-etl-project/pull/42" ./scripts/claim-staging-slot.sh 2 linear-JOB-60-fix-login
# Example (minimal):
#   STAGING_ADMIN_JWT="eyJ..." ./scripts/claim-staging-slot.sh 2

set -euo pipefail

SLOT=${1:-}
BRANCH=${2:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")}
BASE_URL="${BASE_URL:-https://justapply.net}"
JWT="${STAGING_ADMIN_JWT:-}"

if [[ -z "$SLOT" ]] || [[ ! "$SLOT" =~ ^[1-9]$|^10$ ]]; then
  echo "Usage: $0 <slot_id> [branch]"
  echo "Slot must be 1-10. Set STAGING_ADMIN_JWT for API claim."
  echo "For full metadata set PURPOSE (e.g. 'QA: JOB-60 — <PR link>') and optionally ISSUE_ID."
  exit 1
fi

if [[ -z "$JWT" ]]; then
  echo "STAGING_ADMIN_JWT not set. Claim slot $SLOT manually at $BASE_URL/staging"
  exit 0
fi

OWNER="${OWNER:-${USER:-deploy}}"
# Issue ID: from env, or parsed from branch (e.g. linear-JOB-60-...)
ISSUE_ID="${ISSUE_ID:-}"
if [[ -z "$ISSUE_ID" ]] && [[ "$BRANCH" =~ JOB-[0-9]+ ]]; then
  ISSUE_ID=$(echo "$BRANCH" | grep -oE "JOB-[0-9]+" | head -1)
fi

# Purpose must include PR and/or Linear link when slot is in use (per .cursorrules).
if [[ -n "${PURPOSE:-}" ]]; then
  PURPOSE="$PURPOSE"
elif [[ -n "${PR_URL:-}" ]]; then
  PURPOSE="QA: ${ISSUE_ID:-branch $BRANCH} — $PR_URL"
else
  PURPOSE="${PURPOSE:-Claimed via claim-staging-slot.sh (set PURPOSE or PR_URL for full metadata)}"
fi

# Claimed/deployed_at: when this slot was claimed (ISO format)
DEPLOYED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Escape JSON string fields (simple: escape backslash and double-quote)
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

echo "Claiming slot $SLOT (branch=$BRANCH, owner=$OWNER, purpose=$PURPOSE, claimed_at=$DEPLOYED_AT)..."
HTTP=$(curl -s -w "%{http_code}" -o /tmp/claim-staging-out.json \
  -X PUT \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "$JSON" \
  "$BASE_URL/api/staging/slots/$SLOT")

if [[ "$HTTP" -ge 200 && "$HTTP" -lt 300 ]]; then
  echo "Slot $SLOT claimed successfully (claimed_at=$DEPLOYED_AT)."
  cat /tmp/claim-staging-out.json | head -c 500
  echo ""
else
  echo "Claim failed (HTTP $HTTP):"
  cat /tmp/claim-staging-out.json
  exit 1
fi
