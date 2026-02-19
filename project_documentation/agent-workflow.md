# Cursor Chat Agent Workflow

This document defines how to use **Cursor chat** to work on Linear tasks through the development lifecycle using MCP (Model Context Protocol) for task management.

## Contents

- [IMPORTANT: Chat-Based Workflow](#important-chat-based-workflow)
- [Common Checklist (All Phases)](#common-checklist-all-phases)
- [Quick Start Checklists](#quick-start-checklists)
  - [Development Phase](#development-phase)
  - [Code Review Phase](#code-review-phase)
  - [QA Phase](#qa-phase)
  - [Deploy Phase](#deploy-phase)
  - [CI Fix Phase](#ci-fix-phase)
- [Status Transitions](#status-transitions)
- [Worktree Management](#worktree-management)
- [Staging Slot Management](#staging-slot-management)
- [Core Principles](#core-principles)

---

## IMPORTANT: Chat-Based Workflow

**This project uses Cursor chat to request work on Linear tasks.** Each Linear task is worked on in a **separate Git worktree** for complete isolation.

### How to Use

1. **Open Cursor chat** and request work on a Linear issue
2. **Agent checks issue status** via Linear MCP to determine the appropriate phase
3. **Agent follows the workflow** for that phase
4. **Agent updates Linear status** as work progresses

### Key Requirements

- **Worktrees**: Each Linear issue gets its own worktree in `.worktrees/linear-{issue-id}-{description}/`
- **MCP Integration**: Agent uses Linear MCP tools to read and update tasks
- **Isolation**: One worktree = One branch = One staging slot per issue
- **Branch naming**: Use `linear-{issue-id}-{short-description}` NOT `cursor/...`
- **Comments**: Use our structured templates, NOT Cursor's default format
- **Status updates**: Agent MUST update Linear status at each phase via MCP

---

## Common Checklist (All Phases)

**When working on a Linear task via Cursor chat, the agent MUST:**

- [ ] Read Linear issue via Linear MCP to get current status and details
- [ ] Determine the appropriate phase based on issue status
- [ ] Use Linear MCP to update issue status as work progresses
- [ ] Use Linear MCP to add completion comments using structured templates
- [ ] Use GitHub MCP for all PR operations (create, read, review, merge)
- [ ] Use DigitalOcean MCP for environment control and deployment (droplets, databases, actions)
- [ ] Follow branch naming: `linear-{issue-id}-{short-description}`
- [ ] Leave completion comment using appropriate template
- [ ] Update Linear status at phase completion

---

## Quick Start Checklists

### Development Phase

**When requested**: "Work on Linear issue ABC-123" or "Develop Linear issue ABC-123"

**Agent checks**: Issue status should be `Todo` or `Fixes needed`

- [ ] Read Linear issue via Linear MCP to get issue details
- [ ] Verify issue status is `Todo` or `Fixes needed` (if not, inform user)
- [ ] Update Linear status to `In Progress` via Linear MCP
- [ ] Create worktree: `linear-{issue-id}-{short-description}` (MUST use `linear-` prefix) ou use the existing in case of fixes
- [ ] Change to worktree directory
- [ ] Implement changes following cursor rules
- [ ] Run tests and linting (from worktree directory)
- [ ] Push branch
- [ ] Create PR via GitHub MCP (NOT just pushing)
- [ ] Update Linear status to `Code review` via Linear MCP
- [ ] Leave completion comment using template below

**Completion Comment Template:**
```markdown
**Development Complete**
- Branch: `linear-{issue-id}-{description}`
- PR: {link to PR}
- Changes: {summary of what was done}
- Tests: {test results}
- Status updated to: Code review
```

### Code Review Phase

**When requested**: "Review Linear issue ABC-123" or "Review the PR for ABC-123"

**Agent checks**: Issue status should be `Code review`

- [ ] Query Linear for issues with status `Code review` via Linear MCP
- [ ] Get issue details to find PR link from comments
- [ ] Read PR using GitHub MCP tools
- [ ] Review against Code Review Checklist (see [Code Review Agent Checklist](#code-review-agent-checklist) for full checklist)
- [ ] Add inline comments via GitHub MCP if issues found
- [ ] If approved:
  - [ ] Update Linear status to `QA` via Linear MCP
  - [ ] Approve PR via GitHub MCP
- [ ] If changes needed:
  - [ ] Update Linear status to `Fixes needed` via Linear MCP
  - [ ] Request changes on PR via GitHub MCP
- [ ] Leave completion comment using template below

**Completion Comment Template:**
```markdown
**Code Review Complete**
- Status: APPROVED / CHANGES_REQUESTED
- Issues: [list if any]
- Status updated to: QA (if approved) or Fixes needed (if changes needed)
```

### QA Phase

**When requested**: "Do QA for Linear issue ABC-123" or "Test Linear issue ABC-123"

**Agent checks**: Issue status should be `QA`

- [ ] Query Linear for issues with status `QA` via Linear MCP
- [ ] Get issue details to find branch name and PR link
- [ ] Assess change type to determine verification needed
- [ ] Claim staging slot (slots 1-9) via Staging API or `marts.staging_slots` (Staging Dashboard or API; slot 10 is available for staging)
- [ ] Deploy to staging from worktree (if exists) or branch
  - [ ] Use DigitalOcean MCP to check droplet status and database cluster health if needed
  - [ ] Use deployment scripts (`deploy-staging.sh`) or DigitalOcean MCP for environment management
- [ ] Perform relevant verification based on change type:
  - [ ] Frontend changes → UI verification with screenshots
  - [ ] Backend API changes → API endpoint testing
  - [ ] Database/dbt changes → Data verification
  - [ ] Service logic changes → Functional testing
- [ ] If passed: Update Linear status to `Ready to Deploy` via Linear MCP
- [ ] If failed: Update Linear status to `Fixes needed` via Linear MCP, release staging slot
- [ ] Leave completion comment using template below

**Completion Comment Template:**
```markdown
**QA Verification Complete**

**Staging Environment**
- Slot: staging-N (STILL ALLOCATED - will be released after merge)
- Branch: linear-{issue-id}-{description}
- URL: https://staging-N.justapply.net

**Change Type**: [Frontend / Backend API / Database / Service Logic]

**Verification Performed**:
- [x] [Describe what was verified]
- [x] [Describe what was verified]

**Evidence**:
[For UI changes: Screenshots attached]
[For API changes: Request/response samples]
[For DB changes: Query results]

**Result**: PASSED / FAILED
**Status updated to**: Ready to Deploy (if passed) or Fixes needed (if failed)
```

### Deploy Phase

**When requested**: "Deploy Linear issue ABC-123" or "Merge Linear issue ABC-123"

**Agent checks**: Issue status should be `Ready to Deploy`

**CRITICAL**: This agent is responsible for cleanup: releasing staging slot, removing worktree, and deleting branch after merge.

- [ ] Query Linear for issues with status `Ready to Deploy` via Linear MCP
- [ ] Get issue details to find PR, branch, and staging slot info
- [ ] Verify PR is approved and CI passing
- [ ] Read QA comment to get staging slot number
- [ ] Merge PR via GitHub MCP
- [ ] Monitor CI after merge (poll until terminal state)
- [ ] For production deployment (slot 10): Use `./scripts/deploy-production.sh` or DigitalOcean MCP to manage deployment
- [ ] Use DigitalOcean MCP to verify droplet and database cluster status if needed
- [ ] If CI passes:
  - [ ] Release staging slot (via Staging API or `marts.staging_slots`; see `.cursor/rules/release-staging-when-done.mdc`)
  - [ ] Remove worktree: `git worktree remove .worktrees/linear-{issue-id}-{description}` (from project root)
  - [ ] Delete remote branch via GitHub MCP
  - [ ] Update Linear status to `Done` via Linear MCP
- [ ] If CI fails:
  - [ ] Add comment to Linear issue: "CI failed after merge. Need to investigate."
  - [ ] Update status to appropriate status (may need manual intervention)
- [ ] Leave completion comment using template below

**Completion Comment Template:**
```markdown
**Deployment Complete**
- PR merged: {link}
- CI status: PASSED
- Staging slot: staging-N (RELEASED)
- Branch: {name} (DELETED)
- Status: Done
```

### CI Fix Phase

**When requested**: "Fix CI for Linear issue ABC-123" or "Fix the CI failures"

**Agent checks**: Issue has CI failure comment or PR has failed CI status

- [ ] Query Linear for issues with recent comments mentioning "CI failed" or check PRs with failed CI
- [ ] Get Linear issue via MCP to find branch and worktree location
- [ ] Extract errors using `.github/scripts/report_ci_errors.py`
- [ ] Analyze failures (lint errors, test failures, dbt failures)
- [ ] Work in the worktree (or checkout branch if worktree was removed)
- [ ] Push fixes to the branch
- [ ] Monitor CI again until passing
- [ ] Once passing, add comment to Linear issue: "CI fixes applied and passing. Ready for deployment."
- [ ] If issue is in `Ready to Deploy`: Status remains, Deploy Agent will retry
- [ ] If issue is in `Code review`: Status remains, Review Agent can re-review

---

## Status Transitions

```
Todo → In Progress → Code review → QA → Ready to Deploy → Done
                  ↑                   ↓
                  └── Fixes needed ←──┘
```

| From Status | To Status | Triggered By |
|-------------|-----------|--------------|
| `Todo` | `In Progress` | Development agent starts work |
| `In Progress` | `Code review` | Development agent completes, creates PR |
| `Code review` | `QA` | Code review agent approves |
| `Code review` | `Fixes needed` | Code review agent requests changes |
| `QA` | `Ready to Deploy` | QA agent verifies successfully |
| `QA` | `Fixes needed` | QA agent finds issues |
| `Ready to Deploy` | `Done` | Deploy agent merges successfully |
| `Fixes needed` | `In Progress` | Development agent addresses feedback |

---

## Worktree Management

**Worktree Location**: `.worktrees/linear-{issue-id}-{description}/`

**Creating a Worktree** (use helper script):
```bash
# From project root
./scripts/create_worktree.sh <issue-id> <description>
# Example: ./scripts/create_worktree.sh ABC-123 user-authentication

# Or manually:
git worktree add .worktrees/linear-{issue-id}-{description} -b linear-{issue-id}-{description}
cd .worktrees/linear-{issue-id}-{description}
```

**Removing a Worktree** (after PR merge, use helper script):
```bash
# From project root
./scripts/remove_worktree.sh <issue-id> <description>
# Example: ./scripts/remove_worktree.sh ABC-123 user-authentication

# Or manually:
git worktree remove .worktrees/linear-{issue-id}-{description}
# If worktree directory was deleted manually:
git worktree prune
```

**Listing Worktrees**:
```bash
# Use helper script
./scripts/list_worktrees.sh

# Or manually:
git worktree list
```

**Working in a Worktree**:
- All git operations (commit, push, etc.) happen in the worktree directory
- Each worktree has its own `.git` reference pointing to the main repository
- Changes are isolated to that worktree until pushed
- Worktrees are stored in `.worktrees/` (already in `.gitignore`)

---

## Staging Slot Management

### Available Slots

| Slots | Purpose |
|-------|---------|
| 1-9 | Available for QA agents |
| 10 | Temporarily reserved for production |

### Slot Registry Location

- **Database**: `marts.staging_slots` (e.g. production DB for justapply.net).
- **Staging Dashboard**: https://justapply.net/staging (view and manage slots).
- **Static reference**: `project_documentation/staging-slots.md` (ports, subdomains; usage is in DB).

### Claiming a Slot

1. Check availability via Staging API (`GET /api/staging/slots`) or Staging Dashboard.
2. Claim first available slot (1-9; slot 10 is available for staging) via API (`PUT /api/staging/slots`) or by updating `marts.staging_slots`.
3. Deploy and test: `./scripts/deploy-staging.sh <slot-id> [branch]`.

### Releasing a Slot

**Only release when**:
- PR is merged to main (success case)
- QA fails and issue goes back to development

**Do NOT release when**:
- QA passes but PR not yet merged
- CI fails after merge (may need for debugging)

Release via Staging API (`POST /api/staging/slots/<id>/release`) or DB: `UPDATE marts.staging_slots SET status = 'Available', owner = NULL, ... WHERE slot_id = N`. See `.cursor/rules/release-staging-when-done.mdc`.

---

## Core Principles

### Isolation Guarantees

1. **One Task = One Worktree = One Branch = One Staging Slot**
   - Each Linear task gets its own dedicated Git worktree
   - Each worktree has its own branch: `linear-{issue-id}-{short-description}`
   - Each task gets its own staging slot during QA phase (if relevant)
   - No sharing of worktrees, branches, or staging slots between tasks

2. **Resource Lifecycle**
   - **Worktree**: Created when development starts, removed after PR is merged
   - **Branch**: Created in worktree, deleted after PR is merged
   - **Staging Slot**: Claimed when QA starts, released when PR is merged to main

3. **Clean Handoffs**
   - Each agent phase completes fully before handing off
   - Status changes (via Linear MCP) signal handoff between agents
   - Comments document what was done and what's next
