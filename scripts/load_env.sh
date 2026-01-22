#!/bin/bash
# Helper script to load environment-specific .env file
# Usage: source scripts/load_env.sh [environment]
# Defaults to 'development' if no environment is specified

ENVIRONMENT=${1:-${ENVIRONMENT:-development}}

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV_FILE="$PROJECT_ROOT/.env.$ENVIRONMENT"

if [ ! -f "$ENV_FILE" ]; then
    echo "Warning: .env.$ENVIRONMENT not found, falling back to .env"
    ENV_FILE="$PROJECT_ROOT/.env"
fi

if [ -f "$ENV_FILE" ]; then
    echo "Loading environment variables from $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
    export ENVIRONMENT
else
    echo "Error: No .env file found at $ENV_FILE"
    exit 1
fi
