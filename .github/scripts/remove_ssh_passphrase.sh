#!/bin/bash
# Script to remove passphrase from SSH key
# Usage: ./remove_ssh_passphrase.sh [key_file]

set -euo pipefail

KEY_FILE="${1:-$HOME/.ssh/id_rsa}"

if [ ! -f "$KEY_FILE" ]; then
    echo "Error: SSH key file not found: $KEY_FILE"
    exit 1
fi

echo "=== Removing passphrase from SSH key ==="
echo "Key file: $KEY_FILE"
echo ""
echo "This will prompt you for the current passphrase."
echo "Then press Enter twice (leave new passphrase empty)."
echo ""

# Create backup
BACKUP_FILE="${KEY_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$KEY_FILE" "$BACKUP_FILE"
echo "Backup created: $BACKUP_FILE"
echo ""

# Remove passphrase
ssh-keygen -p -f "$KEY_FILE"

echo ""
echo "=== Passphrase removed successfully ==="
echo ""
echo "Next steps:"
echo "1. Get the private key: cat $KEY_FILE"
echo "2. Update GitHub secret SSH_PRIVATE_KEY with the key content"
echo "3. Ensure the public key is on the droplet:"
echo "   ssh-copy-id -i ${KEY_FILE}.pub deploy@134.122.35.239"
echo ""
echo "Or if the public key is already on the droplet, you're done!"
