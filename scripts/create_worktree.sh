#!/bin/bash
# Create a Git worktree for a Linear issue
# Usage: ./scripts/create_worktree.sh <issue-id> <description>
# Example: ./scripts/create_worktree.sh ABC-123 add-user-authentication

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <issue-id> <description>"
    echo "Example: $0 ABC-123 add-user-authentication"
    exit 1
fi

ISSUE_ID="$1"
DESCRIPTION="$2"
BRANCH_NAME="linear-${ISSUE_ID}-${DESCRIPTION}"
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
