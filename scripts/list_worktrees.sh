#!/bin/bash
# List all Git worktrees and their status
# Usage: ./scripts/list_worktrees.sh

set -e

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
for worktree in .worktrees/*/; do
    if [ -d "$worktree" ]; then
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
    fi
done

echo ""
echo "To remove a worktree: ./scripts/remove_worktree.sh <issue-id> <description>"
