#!/bin/bash
# Configure Docker credential helper to avoid unencrypted credentials in ~/.docker/config.json.
# Run once on the production droplet as the deploy user.
# See: https://docs.docker.com/go/credential-store/
#
# Usage: ./scripts/configure-docker-credential-helper.sh
# Or via SSH: ssh deploy@<droplet> 'bash -s' < scripts/configure-docker-credential-helper.sh

set -euo pipefail

CONFIG="${HOME}/.docker/config.json"
HELPER=""

# Prefer secretservice (uses system keyring); fallback to pass
if command -v docker-credential-secretservice >/dev/null 2>&1; then
  HELPER="secretservice"
elif command -v docker-credential-pass >/dev/null 2>&1; then
  HELPER="pass"
fi

if [[ -z "$HELPER" ]]; then
  echo "No credential helper found. Install one:"
  echo "  Ubuntu: sudo apt-get install -y docker-credential-pass  # or docker-credential-secretservice"
  echo "  Or download from: https://github.com/docker/docker-credential-helpers/releases"
  exit 1
fi

echo "Using credential helper: $HELPER"

mkdir -p "$(dirname "$CONFIG")"
if [[ -f "$CONFIG" ]]; then
  # Merge credsStore into existing config (preserve auths if any)
  python3 -c "
import json, sys
p = '$CONFIG'
with open(p) as f:
  cfg = json.load(f)
cfg['credsStore'] = '$HELPER'
# Remove raw auth to force re-login via helper
cfg.pop('auths', None)
with open(p, 'w') as f:
  json.dump(cfg, f, indent=2)
"
else
  echo "{\"credsStore\": \"$HELPER\"}" > "$CONFIG"
fi

echo "Configured credsStore in $CONFIG"
echo "Run 'docker logout ghcr.io' then re-deploy; next docker login will use the helper."
