#!/bin/bash
# Wrapper for dedicated production deploy. Delegates to deploy-production-dedicated.sh.
# Usage: ./scripts/deploy-production.sh [branch] | <commit-sha> | --diagnose
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy-production-dedicated.sh" "$@"
