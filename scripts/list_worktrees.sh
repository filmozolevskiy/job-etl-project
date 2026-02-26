#!/bin/bash
# List all Git worktrees and their status.
#
# Usage: ./scripts/list_worktrees.sh

set -euo pipefail

echo "Git Worktrees:"
echo "=============="
echo ""

# List worktrees
git worktree list

echo ""
echo "Worktree Details:"
echo "================="

# Check if .worktrees directory exists
if [ ! -d ".worktrees" ]; then
    echo "No worktrees directory found."
    exit 0
fi

# List each worktree with branch info
# Use find to avoid issues with empty globs
WORKTREES=$(find .worktrees -maxdepth 1 -mindepth 1 -type d)

if [ -z "$WORKTREES" ]; then
    echo "No worktrees found in .worktrees/"
    exit 0
fi

for worktree in $WORKTREES; do
    worktree_name=$(basename "$worktree")
    echo ""
    echo "Worktree: $worktree_name"
    
    # Get branch name from worktree
    if [ -f "$worktree/.git" ]; then
        git_dir=$(cat "$worktree/.git" | sed 's/^gitdir: //')
        if [ -f "$git_dir/HEAD" ]; then
            branch=$(cat "$git_dir/HEAD" | sed 's/^ref: refs\/heads\///')
            echo "  Branch: $branch"
        fi
    fi
    
    # Check if branch exists remotely
    if git show-ref --verify --quiet refs/remotes/origin/"$worktree_name"; then
        echo "  Remote: exists"
    else
        echo "  Remote: not pushed"
    fi
done

echo ""
echo "To remove a worktree: ./scripts/remove_worktree.sh <issue-id> <description>"
