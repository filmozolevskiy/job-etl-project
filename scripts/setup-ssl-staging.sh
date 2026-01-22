#!/bin/bash
# SSL setup script for staging environments
#
# This script configures Let's Encrypt SSL certificates for staging subdomains.
# It supports both wildcard certificates (recommended) and individual domain certs.
#
# Usage:
#   sudo ./scripts/setup-ssl-staging.sh [--wildcard]
#
# Options:
#   --wildcard    Request a wildcard certificate for *.jobsearch.example.com
#                 Requires DNS challenge (manual or automated via DNS provider API)
#
# Prerequisites:
#   - Nginx installed
#   - Domain DNS configured pointing to staging droplet
#   - certbot installed

set -euo pipefail

# Configuration - UPDATE THESE VALUES
DOMAIN="jobsearch.example.com"
EMAIL="admin@example.com"  # For Let's Encrypt notifications

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Parse arguments
WILDCARD=false
if [[ "${1:-}" == "--wildcard" ]]; then
    WILDCARD=true
fi

echo -e "${GREEN}=== SSL Setup for Staging ===${NC}"
echo "Domain: ${DOMAIN}"
echo "Wildcard: ${WILDCARD}"
echo ""

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo -e "${YELLOW}Installing certbot...${NC}"
    apt update
    apt install -y certbot python3-certbot-nginx
fi

# Check if nginx is installed
if ! command -v nginx &> /dev/null; then
    echo -e "${RED}Error: Nginx is not installed${NC}"
    exit 1
fi

if [ "$WILDCARD" = true ]; then
    echo -e "${YELLOW}=== Requesting Wildcard Certificate ===${NC}"
    echo ""
    echo "This will use DNS challenge. You'll need to add a TXT record to your DNS."
    echo "For automated renewals, consider using a DNS provider plugin."
    echo ""
    
    certbot certonly \
        --manual \
        --preferred-challenges dns \
        -d "${DOMAIN}" \
        -d "*.${DOMAIN}" \
        --email "${EMAIL}" \
        --agree-tos \
        --no-eff-email
else
    echo -e "${YELLOW}=== Requesting Individual Certificates ===${NC}"
    
    # Request certificates for all staging subdomains
    DOMAINS=""
    for i in {1..10}; do
        DOMAINS="${DOMAINS} -d staging-${i}.${DOMAIN}"
    done
    
    # Create webroot directory
    mkdir -p /var/www/certbot
    
    certbot certonly \
        --nginx \
        ${DOMAINS} \
        --email "${EMAIL}" \
        --agree-tos \
        --no-eff-email
fi

echo -e "${GREEN}=== Certificate obtained successfully ===${NC}"
echo ""

# Set up auto-renewal
echo -e "${YELLOW}=== Setting up auto-renewal ===${NC}"

# Create renewal hook to reload nginx
cat > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh << 'EOF'
#!/bin/bash
systemctl reload nginx
EOF
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

# Test renewal
echo "Testing certificate renewal..."
certbot renew --dry-run

echo ""
echo -e "${GREEN}=== SSL Setup Complete ===${NC}"
echo ""
echo "Certificates installed at:"
if [ "$WILDCARD" = true ]; then
    echo "  /etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
    echo "  /etc/letsencrypt/live/${DOMAIN}/privkey.pem"
else
    for i in {1..10}; do
        echo "  /etc/letsencrypt/live/staging-${i}.${DOMAIN}/"
    done
fi
echo ""
echo "Auto-renewal is configured. Certificates will renew automatically."
echo ""
echo "Next steps:"
echo "1. Update infra/nginx/staging-multi.conf with correct certificate paths"
echo "2. Copy nginx config: sudo cp infra/nginx/staging-multi.conf /etc/nginx/sites-available/"
echo "3. Enable the site: sudo ln -s /etc/nginx/sites-available/staging-multi /etc/nginx/sites-enabled/"
echo "4. Test nginx config: sudo nginx -t"
echo "5. Reload nginx: sudo systemctl reload nginx"
