#!/bin/bash
# Run this script ON the staging droplet to fix nginx so staging-N.justapply.net is accessible.
#
# On droplet: cd /home/deploy/staging-1/job-search-project && sudo bash scripts/fix-staging-nginx.sh
# From your machine: ssh deploy@<staging-ip> 'cd /home/deploy/staging-1/job-search-project && sudo bash scripts/fix-staging-nginx.sh'

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [ ! -f "${PROJECT_DIR}/infra/nginx/staging-multi.conf" ]; then
  echo "Not found: ${PROJECT_DIR}/infra/nginx/staging-multi.conf"
  exit 1
fi

echo "=== Enabling staging nginx config ==="
sudo cp -f "${PROJECT_DIR}/infra/nginx/staging-multi.conf" /etc/nginx/sites-available/staging-multi
sudo ln -sf /etc/nginx/sites-available/staging-multi /etc/nginx/sites-enabled/staging-multi
sudo nginx -t
sudo systemctl reload nginx
echo "Nginx reloaded."

echo "=== Checking staging-1 ports (slot 1) ==="
curl -s -o /dev/null -w "Backend 5001: %{http_code}\n" http://127.0.0.1:5001/api/health || echo "Backend 5001: failed"
curl -s -o /dev/null -w "Frontend 5174: %{http_code}\n" http://127.0.0.1:5174/ || echo "Frontend 5174: failed"
echo "Done. Try https://staging-1.justapply.net in the browser."
