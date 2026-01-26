# Local Agents Setup Guide

This guide explains how to use local Cursor agents with Linear tasks, Git worktrees, and staging slots.

## Overview

- **Local Agents**: Agents run on your local machine (not cloud)
- **Worktrees**: Each Linear issue gets its own Git worktree for isolation
- **MCP Integration**: Use Linear and GitHub MCP tools for task management
- **Staging Slots**: Each issue gets its own staging slot during QA (if relevant)

## Quick Start

### 1. Assign a Task to an Agent

**Agents automatically pick up tasks based on Linear issue status. No manual assignment needed.**

**To start work on an issue:**
- Set Linear issue status to `Todo` (or leave it as `Todo`)
- Development Agent will automatically query for `Todo` issues and pick it up

### 2. Agent Workflow

The agent will:
1. Read issue via Linear MCP
2. Create worktree: `.worktrees/linear-{issue-id}-{description}/`
3. Implement changes in the worktree
4. Create PR via GitHub MCP
5. Update Linear status via Linear MCP

### 3. Worktree Management

**Create worktree** (agent does this automatically):
```bash
./scripts/create_worktree.sh ABC-123 feature-name
```

**List worktrees**:
```bash
./scripts/list_worktrees.sh
```

**Remove worktree** (agent does this after PR merge):
```bash
./scripts/remove_worktree.sh ABC-123 feature-name
```

## Agent Phases

Agents are automatically triggered by Linear issue status:

### Development Agent
- **Trigger**: Issue status is `Todo` or `Fixes needed`
- Creates worktree
- Implements changes
- Creates PR
- Updates status to `Code review` (triggers Review Agent)

### Code Review Agent
- **Trigger**: Issue status is `Code review`
- Reviews PR via GitHub MCP
- Approves or requests changes
- Updates status to `QA` (if approved) or `Fixes needed` (if changes needed)

### QA Agent
- **Trigger**: Issue status is `QA`
- Claims staging slot (4-10)
- Deploys to staging
- Verifies changes
- Updates status to `Ready to Deploy` (if passed) or `Fixes needed` (if failed)

### Deployment Agent
- **Trigger**: Issue status is `Ready to Deploy`
- Merges PR via GitHub MCP
- Monitors CI
- Removes worktree
- Releases staging slot
- Updates status to `Done`

### CI Fix Agent
- **Trigger**: Issue has CI failure comment or PR has failed CI
- Fixes CI failures
- Pushes fixes
- Monitors CI until passing

## Worktree Structure

```
.worktrees/
├── linear-ABC-123-feature-1/
│   ├── .git (symlink to main repo)
│   └── [all project files]
├── linear-ABC-124-feature-2/
│   └── [all project files]
└── ...
```

## Staging Slots

- **Slots 1-10**: All slots available for QA agents
- **Registry**: `project_documentation/staging-slots.md`
- **Claim**: Update registry when starting QA
- **Release**: Update registry after PR merge

## MCP Tools Used

### Linear MCP
- `list_issues` - List Linear issues
- `get_issue` - Get issue details
- `update_issue` - Update issue status/assignee
- `create_comment` - Add comments to issues

### GitHub MCP
- `create_pull_request` - Create PRs
- `pull_request_read` - Read PR details
- `pull_request_review` - Review PRs
- `merge_pull_request` - Merge PRs
- `delete_branch` - Delete branches

## Best Practices

1. **One worktree per issue**: Never share worktrees between issues
2. **Clean up after merge**: Always remove worktree after PR merge
3. **Update Linear status**: Use Linear MCP to update status at each phase
4. **Use helper scripts**: Use `create_worktree.sh` and `remove_worktree.sh` for consistency
5. **Check worktree list**: Use `list_worktrees.sh` to see active worktrees

## Troubleshooting

### Worktree already exists
- Check if issue is already being worked on
- Remove old worktree if needed: `./scripts/remove_worktree.sh <issue-id> <description>`

### Cannot remove worktree
- Make sure you're not inside the worktree directory
- Change to project root first

### Branch conflicts
- Check if branch already exists: `git branch -a | grep linear-{issue-id}`
- Delete remote branch if needed: Use GitHub MCP

## Reference Documents

- **Full workflow**: `project_documentation/agent-workflow.md`
- **Project rules**: `.cursor/rules/cursorrules.mdc`
- **Staging slots**: `project_documentation/staging-slots.md`
