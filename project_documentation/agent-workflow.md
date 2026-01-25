# Cursor Agent Workflow

This document defines how Cursor agents work with Linear tasks through the development lifecycle.

---

## IMPORTANT: Override Cursor Defaults

**Background Agents**: This project has CUSTOM workflow rules. You MUST override Cursor's default conventions:

- **Branch naming**: Use `linear-{issue-id}-...` NOT `cursor/...`
- **Comments**: Use our structured templates, NOT Cursor's default format
- **Status updates**: You MUST update Linear status at each phase

---

## QUICK START CHECKLIST

**For Development Agent (`@agent:develop`):**

- [ ] Update Linear status to `In Progress`
- [ ] Create branch: `linear-{issue-id}-{short-description}` (MUST use `linear-` prefix)
- [ ] Implement changes
- [ ] Run tests and linting
- [ ] Push branch
- [ ] Create PR via GitHub MCP (NOT just pushing)
- [ ] Update Linear status to `Code review`
- [ ] Leave completion comment using template below
- [ ] Tag `@agent:review` for next phase

**Completion Comment Template (REQUIRED):**
```markdown
**Development Complete**
- Branch: `linear-{issue-id}-{description}`
- PR: {link to PR}
- Changes: {summary of what was done}
- Tests: {test results}
- Next: @agent:review
```

**CRITICAL RULES:**
1. Branch MUST start with `linear-` prefix (NOT `cursor/`, `feature/`, etc.)
2. MUST create PR via GitHub MCP tools
3. MUST update Linear status at start AND end
4. MUST use completion comment template
5. MUST tag next agent (`@agent:review`)

---

## Core Principles

### Isolation Guarantees

1. **One Task = One Branch = One Staging Slot**
   - Each Linear task gets its own dedicated Git branch
   - Each task gets its own staging slot during QA phase
   - No sharing of branches or staging slots between tasks

2. **Resource Lifecycle**
   - **Branch**: Created when development starts, deleted after PR is merged
   - **Staging Slot**: Claimed when QA starts, released when PR is merged to main

3. **Clean Handoffs**
   - Each agent phase completes fully before handing off
   - Status changes signal handoff between agents
   - Comments document what was done and what's next

---

## Agent Tags

Use these tags in Linear comments to invoke specific agents:

| Tag | Purpose | Expected Status |
|-----|---------|-----------------|
| `@agent:develop` | Start development work | `Todo` |
| `@agent:review` | Perform code review | `Code review` |
| `@agent:qa` | Perform QA verification | `QA` |
| `@agent:deploy` | Merge and deploy | `Ready to Deploy` |
| `@agent:fix-ci` | Fix CI failures | Any (after CI failure) |

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

## Agent Workflows

### 1. Development Agent (`@agent:develop`)

**Trigger**: Comment with `@agent:develop` on issue in `Todo` status

**Steps**:
1. Update status to `In Progress`
2. Create branch: `linear-{issue-id}-{short-description}`
3. Implement changes following cursor rules
4. Run unit tests and linting
5. Push branch, create PR via GitHub MCP
6. Update status to `Code review`
7. Leave completion comment

**Branch Naming**: `linear-{issue-id}-{short-description}`
- Example: `linear-abc123-add-user-auth`
- Issue ID MUST be included for traceability

**Completion Comment**:
```markdown
**Development Complete**
- Branch: `linear-abc123-feature-name`
- PR: https://github.com/owner/repo/pull/123
- Changes: [summary of what was implemented]
- Tests: [test results - passed/failed]
- Next: @agent:review
```

### 2. Code Review Agent (`@agent:review`)

**Trigger**: Comment with `@agent:review` on issue in `Code review` status

**Steps**:
1. Read PR using GitHub MCP
2. Review against Code Review Checklist (see cursorrules.mdc)
3. Add inline comments if issues found
4. If approved: Update status to `QA`, approve PR
5. If changes needed: Update status to `Fixes needed`, request changes on PR

**Completion Comment**:
```markdown
**Code Review Complete**
- Status: APPROVED / CHANGES_REQUESTED
- Issues: [list if any]
- Next: @agent:qa (if approved) or @agent:develop (if changes needed)
```

### 3. QA Agent (`@agent:qa`)

**Trigger**: Comment with `@agent:qa` on issue in `QA` status

**Steps**:
1. **Assess change type** to determine verification needed
2. **Claim staging slot** (slots 4-10, update `staging-slots.md`)
3. **Deploy to staging**
4. **Perform relevant verification** based on change type
5. **Report results** (keep slot allocated if passed)

**Change Type Assessment**:

| Change Type | Verification Method | Evidence |
|-------------|---------------------|----------|
| Frontend (UI, React, styles) | Manual UI verification | Screenshots attached to Linear |
| Backend API (endpoints) | API endpoint testing | Request/response in comment |
| Database/dbt (schema, queries) | Data verification | Query results in comment |
| Service logic (business rules) | Functional testing | Test results in comment |

**Staging Slot Claiming**:
1. Read `project_documentation/staging-slots.md`
2. Find first available slot in range 4-10
3. Update registry with: Status=`In Use`, Owner, Branch, Issue ID
4. Record slot number in Linear comment

**Completion Comment**:
```markdown
**QA Verification Complete**

**Staging Environment**
- Slot: staging-N (STILL ALLOCATED - will be released after merge)
- Branch: linear-abc123-feature-name
- URL: https://staging-N.jobsearch.example.com

**Change Type**: [Frontend / Backend API / Database / Service Logic]

**Verification Performed**:
- [x] [Describe what was verified]
- [x] [Describe what was verified]

**Evidence**:
[For UI changes: Screenshots attached]
[For API changes: Request/response samples]
[For DB changes: Query results]

**Result**: PASSED / FAILED
**Next**: @agent:deploy (if passed)
```

### 4. Deploy Agent (`@agent:deploy`)

**Trigger**: Comment with `@agent:deploy` on issue in `Ready to Deploy` status

**CRITICAL**: This agent is responsible for releasing the staging slot after merge.

**Steps**:
1. Verify PR is approved and CI passing
2. Read QA comment to get staging slot number
3. Merge PR via GitHub MCP
4. Monitor CI after merge (poll until terminal state)
5. If CI passes:
   - Release staging slot (update `staging-slots.md`)
   - Delete remote branch
   - Update status to `Done`
6. If CI fails: Tag `@agent:fix-ci`

**Completion Comment**:
```markdown
**Deployment Complete**
- PR merged: https://github.com/owner/repo/pull/123
- CI status: PASSED
- Staging slot: staging-N (RELEASED)
- Branch: linear-abc123-feature-name (DELETED)
- Status: Done
```

### 5. CI Fix Agent (`@agent:fix-ci`)

**Trigger**: Comment with `@agent:fix-ci` or automatic after CI failure

**Steps**:
1. Extract errors using `.github/scripts/report_ci_errors.py`
2. Analyze failures (lint errors, test failures, dbt failures)
3. Push fixes to the branch
4. Monitor CI again until passing
5. Once passing, hand back to deploy agent

---

## Staging Slot Management

### Available Slots

| Slots | Purpose |
|-------|---------|
| 1-3 | Reserved for CI/CD and automated testing |
| 4-10 | Available for QA agents |

### Slot Registry Location

`project_documentation/staging-slots.md`

### Claiming a Slot

1. Read current registry
2. Find first available slot (4-10)
3. Update registry:
   ```markdown
   | N | In Use | QA-Agent | linear-abc123 | ABC-123 | 2026-01-24T10:00:00Z | QA for feature |
   ```
4. Deploy and test

### Releasing a Slot

**Only release when**:
- PR is merged to main (success case)
- QA fails and issue goes back to development

**Do NOT release when**:
- QA passes but PR not yet merged
- CI fails after merge (may need for debugging)

Update registry:
```markdown
| N | Available | - | - | - | - | - |
```

---

## Comment Templates

### Invoking Development Agent
```markdown
@agent:develop
Task: [Description of what to implement]
Notes: [Optional additional context]
```

### Invoking Review Agent
```markdown
@agent:review
PR: [link to PR]
Focus: [Optional areas to focus review on]
```

### Invoking QA Agent
```markdown
@agent:qa
PR: [link to PR]
Test focus: [Optional specific areas to verify]
```

### Invoking Deploy Agent
```markdown
@agent:deploy
PR: [link to PR]
Staging slot: [slot number from QA comment]
```

### Invoking CI Fix Agent
```markdown
@agent:fix-ci
Workflow run: [link to failed CI run]
Errors: [summary of failures]
```

---

## Screenshot Requirements (QA)

For frontend changes, screenshots are required as proof of verification.

**When to take screenshots**:
- After navigating to affected pages
- After performing user actions
- Before/after states for visual changes
- Error states if testing error handling

**Screenshot naming**:
- `{feature}-{state}.png`
- Example: `login-form-validation-error.png`

**Taking screenshots**:
- Use Playwright MCP to navigate and capture screenshots
- Save screenshots to `tests/browser/screenshots/` directory
- Name files descriptively to indicate what they verify

**Including in Linear comments**:
Since Linear MCP doesn't support direct file uploads, reference screenshots in comments:
```markdown
**Screenshots**:
- Login page: `tests/browser/screenshots/login-page.png`
- Dashboard after login: `tests/browser/screenshots/dashboard-loaded.png`
- Feature verification: `tests/browser/screenshots/feature-working.png`
```

**Alternative**: If screenshots need to be visible in Linear UI:
- Upload to external hosting (e.g., GitHub repository, image hosting service)
- Include direct image links in markdown comments

---

## Quick Reference

### Branch Naming
`linear-{issue-id}-{short-description}`

### Status Flow
`Todo` → `In Progress` → `Code review` → `QA` → `Ready to Deploy` → `Done`

### Agent Tags
- `@agent:develop` - Development
- `@agent:review` - Code review
- `@agent:qa` - QA verification
- `@agent:deploy` - Deployment
- `@agent:fix-ci` - CI fixes

### Staging Slots
- Slots 4-10 for QA
- Claim at QA start
- Release at PR merge
