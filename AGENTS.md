# Agent Instructions

This file provides instructions for Cursor Background Agents working on this repository.

## CRITICAL: Override Default Cursor Behavior

**DO NOT use Cursor's default conventions.** This project has custom workflow rules.

### Branch Naming (MANDATORY)

- **USE**: `linear-{issue-id}-{short-description}`
- **DO NOT USE**: `cursor/...` or any other prefix

**Examples:**
- Correct: `linear-JOB-36-fix-duplicates`
- Wrong: `cursor/JOB-36-fix-duplicates-abc123`
- Wrong: `filippmozolevskiy/job-36-...`

### Before Starting Work

1. Read `project_documentation/agent-workflow.md` for full workflow details
2. Read `.cursor/rules/cursorrules.mdc` for project rules

### Development Workflow

1. Update Linear issue status to `In Progress`
2. Create branch: `linear-{issue-id}-{short-description}`
3. Implement changes
4. Run tests: `pytest -q tests/unit`
5. Run linting: `ruff check .`
6. Push branch to remote
7. Create PR using GitHub MCP tools
8. Update Linear issue status to `Code review`
9. Leave completion comment using this template:

```markdown
**Development Complete**
- Branch: `linear-{issue-id}-{description}`
- PR: {link to PR}
- Changes: {summary of changes}
- Tests: {test results}
- Next: @agent:review
```

### Code Review Workflow

When reviewing code (status = `Code review`):

1. Read the PR using GitHub MCP
2. Review against the Code Review Checklist in cursorrules.mdc
3. If approved: Update status to `QA`, approve PR
4. If changes needed: Update status to `Fixes needed`, request changes
5. Leave comment with `Next: @agent:qa` or `Next: @agent:develop`

### QA Workflow

When performing QA (status = `QA`):

1. Assess change type (frontend/backend/database)
2. Claim a staging slot (4-10) from `project_documentation/staging-slots.md`
3. Deploy to staging
4. Perform relevant verification based on change type
5. If passed: Update status to `Ready to Deploy`
6. If failed: Update status to `Fixes needed`, release staging slot

### Deployment Workflow

When deploying (status = `Ready to Deploy`):

1. Verify PR is approved and CI passing
2. Merge PR using GitHub MCP
3. Monitor CI until completion
4. If passed: Release staging slot, delete branch, update status to `Done`
5. If failed: Tag `@agent:fix-ci`

## Key Files

- `project_documentation/agent-workflow.md` - Full workflow documentation
- `.cursor/rules/cursorrules.mdc` - Project rules and standards
- `project_documentation/staging-slots.md` - Staging slot registry
