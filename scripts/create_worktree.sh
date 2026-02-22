#!/bin/bash
# Create a Git worktree for a Linear issue.
# Name convention: .worktrees/linear-<issue-id>-<description> (branch and path match).
# Description is normalized: lowercase, spaces/slashes to hyphens, no leading/trailing hyphens.
#
# Usage: ./scripts/create_worktree.sh <issue-id> <description>
# Example: ./scripts/create_worktree.sh JOB-123 add-user-authentication
# Example: ./scripts/create_worktree.sh JOB-60 "Fix login flow"

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <issue-id> <description>"
    echo "  issue-id:   Linear issue ID (e.g. JOB-123)"
    echo "  description: Short slug for branch/path (e.g. add-user-auth or 'Fix login flow')"
    echo "Example: $0 JOB-123 add-user-authentication"
    exit 1
fi

ISSUE_ID="$1"
DESCRIPTION="$2"
# Normalize: lowercase, replace spaces/slashes with hyphens, collapse multiple hyphens, trim
NORM_DESC=$(echo "$DESCRIPTION" | tr '[:upper:]' '[:lower:]' | tr ' /_' '-' | sed 's/-\+/-/g' | sed 's/^-//;s/-$//')
BRANCH_NAME="linear-${ISSUE_ID}-${NORM_DESC}"
WORKTREE_PATH=".worktrees/${BRANCH_NAME}"

# Check if worktree already exists
if [ -d "$WORKTREE_PATH" ]; then
    echo "Error: Worktree already exists at $WORKTREE_PATH"
    exit 1
fi

# Check if branch already exists
if git show-ref --verify --quiet refs/heads/"$BRANCH_NAME"; then
    echo "Error: Branch $BRANCH_NAME already exists"
    exit 1
fi

# Create worktree
echo "Creating worktree for issue $ISSUE_ID..."
git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME"

echo ""
echo "✅ Worktree created successfully!"
echo "   Path: $WORKTREE_PATH"
echo "   Branch: $BRANCH_NAME"
echo ""
echo "To work in this worktree:"
echo "   cd $WORKTREE_PATH"
