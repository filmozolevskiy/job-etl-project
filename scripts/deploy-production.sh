#!/bin/bash
# Deploy production (staging slot 10) from remote main.
#
# Production uses staging-10 infrastructure. No staging banner is shown.
#
# Usage:
#   ./scripts/deploy-production.sh
#
# Prerequisites:
#   - SSH access to staging droplet
#   - Slot 10 set up (~/staging-10, .env.staging-10)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

echo "=== Deploying production (staging-10) from remote main ==="
git fetch origin
git checkout main
git pull origin main

"${SCRIPT_DIR}/deploy-staging.sh" 10 main
