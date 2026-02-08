# Staging Slot Registry

This document defines the available staging slots and ownership rules for the Job Search Assistant project.

## Overview

The multi-staging environment provides 10 independent staging slots on a single DigitalOcean droplet. Each slot is a complete, isolated environment with its own:

- Git checkout folder
- Docker Compose stack (unique project name)
- Database (separate DB on shared PostgreSQL instance)
- Subdomain and port mapping

**Dedicated Production Environment**: Production has been moved to a dedicated DigitalOcean droplet (`167.99.0.168`). Slot 10 on the staging droplet is now a standard staging slot.

## Available Staging Slots

| Slot | Identifier | Subdomain | Campaign UI Port | Airflow Port | Database |
|------|------------|-----------|------------------|--------------|----------|
| 1 | `staging-1` | `staging-1.jobsearch.example.com` | 5001 | 8081 | `job_search_staging_1` |
| 2 | `staging-2` | `staging-2.jobsearch.example.com` | 5002 | 8082 | `job_search_staging_2` |
| 3 | `staging-3` | `staging-3.jobsearch.example.com` | 5003 | 8083 | `job_search_staging_3` |
| 4 | `staging-4` | `staging-4.jobsearch.example.com` | 5004 | 8084 | `job_search_staging_4` |
| 5 | `staging-5` | `staging-5.jobsearch.example.com` | 5005 | 8085 | `job_search_staging_5` |
| 6 | `staging-6` | `staging-6.jobsearch.example.com` | 5006 | 8086 | `job_search_staging_6` |
| 7 | `staging-7` | `staging-7.jobsearch.example.com` | 5007 | 8087 | `job_search_staging_7` |
| 8 | `staging-8` | `staging-8.jobsearch.example.com` | 5008 | 8088 | `job_search_staging_8` |
| 9 | `staging-9` | `staging-9.jobsearch.example.com` | 5009 | 8089 | `job_search_staging_9` |
| 10 | `staging-10` | `staging-10.jobsearch.example.com` | 5010 | 8090 | `job_search_staging_10` |

## Slot Usage Registry

Track current slot usage below. Update this table when claiming or releasing a slot.

| Slot | Status | Owner | Branch | Issue ID | Deployed At | Purpose |
|------|--------|-------|--------|----------|-------------|---------|
| 1 | In Use | QA | linear-JOB-39-add-job-location-column | JOB-39 | 2026-02-03T13:05:00Z | QA: Job Location column (Campaign Details) |
| 2 | Available | - | - | - | - | - |
| 3 | Available | - | - | - | - | - |
| 4 | Available | - | - | - | - | - |
| 5 | Available | - | - | - | - | - |
| 6 | Available | - | - | - | - | - |
| 7 | Available | - | - | - | - | - |
| 8 | Available | - | - | - | - | - |
| 9 | Available | - | - | - | - | - |
| 10 | Available | - | - | - | - | - |

## Ownership Rules

### Claiming a Slot

1. **Check availability**: Review the slot usage registry above (slots 1-9 for QA agents; slot 10 is temporarily reserved for production)
2. **Claim the slot**: Update the registry table with:
   - Status: `In Use`
   - Owner: Your name or agent identifier (e.g., `QA-Agent`)
   - Branch: Git branch being tested (e.g., `linear-abc123-feature`)
   - Issue ID: Linear issue ID for traceability (e.g., `ABC-123`)
   - Deployed At: ISO 8601 timestamp
   - Purpose: Brief description (e.g., "QA for feature X")
3. **Deploy**: Run the deployment script for your slot
   - **Optional**: Use DigitalOcean MCP (`droplet-get`, `db-cluster-get`) to verify droplet and database cluster status before/after deployment

### Releasing a Slot

**When to release**:
- After PR is merged to main (Deploy agent responsibility)
- If QA fails and issue goes back to development

**Do NOT release**:
- When QA passes but PR is not yet merged (keep allocated for potential debugging)
- When CI fails after merge (may need for debugging)

**Release steps**:
1. **Stop services**: Run `docker compose -p staging-N down`
2. **Update registry**: Set status back to `Available` and clear other fields
3. **Optional cleanup**: Remove the checkout folder if no longer needed

### Rules

- **One slot per task**: Each Linear issue gets exactly one staging slot
- **Slots 1-9 for QA**: Available for QA agent verification
- **Slot 10 reserved**: Temporarily reserved for production (deploy via `./scripts/deploy-production.sh`). Do not claim for QA.
- **Release after merge**: Deploy agent releases slot after PR merge (slots 1-9 only)
- **Issue ID required**: Always include Linear issue ID when claiming (slots 1-9)
- **Long-running tests**: For tests running longer than 24 hours, add a note in the Purpose field
- **Conflict resolution**: If a slot is needed urgently, coordinate with the current owner

## Deploy Comment Format

When deploying to a slot, use this standard comment format in Linear issues:

```markdown
**Staging Deployment**
- Slot: staging-N
- Branch: feature/my-feature
- Commit: abc123def456...
- Deployed: 2025-01-22T10:30:00Z
- URL: https://staging-N.jobsearch.example.com
```

## Production Deployment

### Automatic Deployment (CI/CD)

Production is automatically deployed via GitHub Actions when code is merged to `main`:
- Workflow: `.github/workflows/deploy-production-dedicated.yml`
- Triggers: Push to `main` branch (after CI passes)
- Manual trigger: Available in GitHub Actions UI

See `.github/workflows/README.md` for setup instructions and required secrets.

### Manual Deployment

To deploy manually from your local machine:

```bash
./scripts/deploy-production-dedicated.sh
```

- **URL**: http://167.99.0.168
- **Airflow**: http://167.99.0.168:8080

## Slot Directory Structure

On the staging droplet, each slot has its own directory:

```
/home/deploy/
├── staging-1/
│   ├── job-search-project/    # Git checkout
│   ├── .env.staging-1         # Environment file
│   └── version.json           # Deployment metadata
├── staging-2/
│   ├── job-search-project/
│   ├── .env.staging-2
│   └── version.json
└── ... (slots 3-10)
```

## Verification

To verify which version is deployed on a slot:

1. **Via API**: `curl https://staging-N.jobsearch.example.com/api/version`
2. **Via UI**: Check the footer of the Campaign UI
3. **Via file**: SSH and check `/home/deploy/staging-N/version.json`
