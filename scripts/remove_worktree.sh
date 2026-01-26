#!/bin/bash
# Remove a Git worktree for a Linear issue
# Usage: ./scripts/remove_worktree.sh <issue-id> <description>
# Example: ./scripts/remove_worktree.sh ABC-123 add-user-authentication

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

# Check if worktree exists
if [ ! -d "$WORKTREE_PATH" ]; then
    echo "Error: Worktree does not exist at $WORKTREE_PATH"
    exit 1
fi

# Check if we're currently in the worktree
CURRENT_DIR=$(pwd)
if [[ "$CURRENT_DIR" == *"$WORKTREE_PATH"* ]]; then
    echo "Error: Cannot remove worktree while inside it. Please change to a different directory first."
    exit 1
fi

# Remove worktree
echo "Removing worktree for issue $ISSUE_ID..."
git worktree remove "$WORKTREE_PATH"

echo ""
echo "✅ Worktree removed successfully!"
echo "   Path: $WORKTREE_PATH"
echo "   Branch: $BRANCH_NAME (still exists remotely, delete separately if needed)"
