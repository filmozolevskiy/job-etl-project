# Staging Slot Registry

This document defines the available staging slots and ownership rules for the Job Search Assistant project.

## Overview

The multi-staging environment provides 10 independent staging slots on a single DigitalOcean droplet. Each slot is a complete, isolated environment with its own:

- Git checkout folder
- Docker Compose stack (unique project name)
- Database (separate DB on shared PostgreSQL instance)
- Subdomain and port mapping

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

| Slot | Status | Owner | Branch | Commit SHA | Deployed At | Purpose |
|------|--------|-------|--------|------------|-------------|---------|
| 1 | Available | - | - | - | - | - |
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

1. **Check availability**: Review the slot usage registry above
2. **Claim the slot**: Update the registry table with:
   - Status: `In Use`
   - Owner: Your name or agent identifier
   - Branch: Git branch being tested
   - Commit SHA: Full commit SHA being deployed
   - Deployed At: ISO 8601 timestamp
   - Purpose: Brief description (e.g., "Testing feature X", "QA for PR #123")
3. **Deploy**: Run the deployment script for your slot

### Releasing a Slot

1. **Stop services**: Run `docker compose -p staging-N down`
2. **Update registry**: Set status back to `Available` and clear other fields
3. **Optional cleanup**: Remove the checkout folder if no longer needed

### Rules

- **One slot per task**: Each cloud agent or developer should use only one slot at a time per task
- **Release promptly**: Release slots when testing is complete
- **Priority slots**: Slots 1-3 are reserved for CI/CD and automated testing
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
