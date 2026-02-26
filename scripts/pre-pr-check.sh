#!/bin/bash
# Run lint (ruff) and tests (pytest) before creating a PR.
#
# Usage:
#   ./scripts/pre-pr-check.sh [pytest-args...]
#
# Example:
#   ./scripts/pre-pr-check.sh
#   ./scripts/pre-pr-check.sh -x -k "test_api"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Pre-PR check (ruff + pytest) ===${NC}"
echo ""

echo "1. Running ruff check..."
if ruff check . ; then
    echo -e "${GREEN}✓ ruff check passed.${NC}"
else
    echo -e "${RED}✗ ruff check failed. Fix lint errors before opening a PR.${NC}"
    exit 1
fi
echo ""

echo "2. Running ruff format check..."
if ruff format --check . ; then
    echo -e "${GREEN}✓ ruff format passed.${NC}"
else
    echo -e "${RED}✗ ruff format check failed. Run 'ruff format .' and commit.${NC}"
    exit 1
fi
echo ""

echo "3. Running pytest..."
if command -v pytest >/dev/null 2>&1; then
    PYTEST_CMD=(pytest)
else
    PYTEST_CMD=(python3 -m pytest)
fi

if "${PYTEST_CMD[@]}" "$@"; then
    echo -e "${GREEN}✓ pytest passed.${NC}"
else
    echo -e "${RED}✗ pytest failed. Fix tests before opening a PR.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=== ✓ All checks passed. Safe to push and open a PR. ===${NC}"
