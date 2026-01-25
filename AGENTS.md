# Agent Instructions

**Quick reference for Cursor Background Agents.** For complete details, see `.cursor/rules/cursorrules.mdc`.

## CRITICAL: Override Default Cursor Behavior

**DO NOT use Cursor's default conventions.** This project has custom workflow rules.

**Branch Naming (MANDATORY)**: Use `linear-{issue-id}-{short-description}` (NOT `cursor/...`)

## Quick Reference

### Before Starting Work

1. Read `.cursor/rules/cursorrules.mdc` - **MANDATORY: Linear Task Workflow** section (lines 22-49)
2. Read `project_documentation/agent-workflow.md` for full workflow details

### Agent Workflows

All workflows are defined in detail in `.cursor/rules/cursorrules.mdc`:

- **Development** (`@agent:develop`): See [Agent Workflow - Development Agent](#agent-workflow) (lines 931-941)
- **Code Review** (`@agent:review`): See [Agent Workflow - Code Review Agent](#agent-workflow) (lines 943-952)
- **QA** (`@agent:qa`): See [Agent Workflow - QA Agent](#agent-workflow) (lines 954-978)
- **Deployment** (`@agent:deploy`): See [Agent Workflow - Deploy Agent](#agent-workflow) (lines 980-994)
- **CI Fix** (`@agent:fix-ci`): See [Agent Workflow - CI Fix Agent](#agent-workflow) (lines 996-1004)

### Key Sections in cursorrules.mdc

- **MANDATORY: Linear Task Workflow** (lines 22-49) - Start here for Linear tasks
- **Agent Workflow** (lines 897-1056) - Complete agent phase definitions
- **Linear Workflow** (lines 720-893) - Linear issue lifecycle management
- **Code Review Checklist** (lines 661-693) - Review standards

## Key Files

- `.cursor/rules/cursorrules.mdc` - **Source of truth** for all rules and workflows
- `project_documentation/agent-workflow.md` - Detailed workflow documentation
- `project_documentation/staging-slots.md` - Staging slot registry
