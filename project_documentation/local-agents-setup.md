# Cursor Chat Agent Workflow Guide

This guide explains how to use Cursor chat to work on Linear tasks, using Git worktrees and staging slots.

## Overview

- **Cursor Chat**: Use regular Cursor chat/agent interface to request work on Linear tasks
- **Worktrees**: Each Linear issue gets its own Git worktree for isolation
- **MCP Integration**: Agent uses Linear and GitHub MCP tools for task management
- **Staging Slots**: Each issue gets its own staging slot during QA (if relevant)

## Quick Start

### 1. Request Work via Cursor Chat

**Simply ask the Cursor agent to work on a Linear task via chat.**

**Examples:**
- "Work on Linear issue ABC-123"
- "Review the PR for Linear issue ABC-123"
- "Do QA for Linear issue ABC-123"
- "Deploy Linear issue ABC-123"

**The agent will:**
1. Check the Linear issue status to determine what phase to perform
2. Follow the appropriate workflow (Development, Review, QA, Deploy, etc.)
3. Use MCP tools to interact with Linear and GitHub
4. Update status and leave comments as work progresses

### 2. How It Works

**When you request work via chat, the agent will:**

1. **Check Linear issue status** via Linear MCP to determine the appropriate phase
2. **Follow the workflow** for that phase (see [Agent Phases](#agent-phases) below)
3. **Use MCP tools** to interact with Linear, GitHub, and DigitalOcean
4. **Update Linear status** as work progresses
5. **Leave completion comments** using structured templates

**Example conversation:**
```
You: "Work on Linear issue ABC-123"

Agent: [Checks issue status via Linear MCP]
        [Status is "Todo" → Development phase]
        [Creates worktree, implements changes, creates PR]
        [Updates status to "Code review"]
        "Development complete for ABC-123. PR created. Status updated to Code review."
```

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

**The agent determines which phase to perform based on the Linear issue status:**

### Development Phase
- **When to request**: "Work on Linear issue ABC-123" or "Develop Linear issue ABC-123"
- **Agent checks**: Issue status should be `Todo` or `Fixes needed`
- **What agent does**:
  - Creates worktree
  - Implements changes
  - Creates PR
  - Updates status to `Code review`

### Code Review Phase
- **When to request**: "Review Linear issue ABC-123" or "Review the PR for ABC-123"
- **Agent checks**: Issue status should be `Code review`
- **What agent does**:
  - Reviews PR via GitHub MCP
  - Approves or requests changes
  - Updates status to `QA` (if approved) or `Fixes needed` (if changes needed)

### QA Phase
- **When to request**: "Do QA for Linear issue ABC-123" or "Test Linear issue ABC-123"
- **Agent checks**: Issue status should be `QA`
- **What agent does**:
  - Claims staging slot (1-9; slot 10 is reserved for production)
  - Deploys to staging
  - Verifies changes
  - Updates status to `Ready to Deploy` (if passed) or `Fixes needed` (if failed)

### Deployment Phase
- **When to request**: "Deploy Linear issue ABC-123" or "Merge Linear issue ABC-123"
- **Agent checks**: Issue status should be `Ready to Deploy`
- **What agent does**:
  - Merges PR via GitHub MCP
  - Monitors CI
  - Removes worktree
  - Releases staging slot
  - Updates status to `Done`

### CI Fix Phase
- **When to request**: "Fix CI for Linear issue ABC-123" or "Fix the CI failures"
- **Agent checks**: Issue has CI failure or PR has failed CI
- **What agent does**:
  - Analyzes CI failures
  - Fixes issues
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

- **Slots 1-9**: Available for QA agents
- **Slot 10**: Temporarily reserved for production
- **Registry**: `project_documentation/staging-slots.md`
- **Claim**: Update registry when starting QA (slots 1-9 only)
- **Release**: Update registry after PR merge


## Reference Documents

- **Full workflow**: `project_documentation/agent-workflow.md`
- **Project rules**: `.cursor/rules/cursorrules.mdc`
- **Staging slots**: `project_documentation/staging-slots.md`
