#!/bin/bash
# Assign admin role to a user by email
# Usage: ./assign_admin_role.sh <email>

set -euo pipefail

EMAIL="${1:?Usage: $0 <email>}"

# Load environment
source ~/staging-10/.env.staging-10

# Check if user exists
USER_CHECK=$(PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -t -c "SELECT COUNT(*) FROM marts.users WHERE email = '${EMAIL}';" | xargs)

if [ "$USER_CHECK" -eq 0 ]; then
  echo "ERROR: User with email '${EMAIL}' not found"
  exit 1
fi

# Update role to admin
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "
  UPDATE marts.users 
  SET role = 'admin', updated_at = CURRENT_TIMESTAMP 
  WHERE email = '${EMAIL}';
"

# Verify the update
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "
  SELECT user_id, username, email, role, updated_at 
  FROM marts.users 
  WHERE email = '${EMAIL}';
"

echo ""
echo "✅ Admin role assigned successfully to ${EMAIL}"
