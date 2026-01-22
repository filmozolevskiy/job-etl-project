# Production Deployment

This document describes the production deployment process and promotion policy for the Job Search Assistant project.

## Overview

Production deployments follow a strict promotion flow to ensure stability:

1. Changes are tested on a staging slot
2. A release tag is created
3. The tag is deployed to staging for final verification
4. The same tag is promoted to production

## Promotion Flow

```
feature branch → main → staging (tag vX.Y.Z) → verify → production (tag vX.Y.Z)
```

### Step 1: Merge to Main

1. Create a pull request from your feature branch to `main`
2. Ensure all CI checks pass
3. Get code review approval
4. Merge the pull request

### Step 2: Create Release Tag

Release tags follow semantic versioning: `vMAJOR.MINOR.PATCH`

```bash
# Pull latest main
git checkout main
git pull origin main

# Create annotated tag
git tag -a v1.2.3 -m "Release v1.2.3: Brief description of changes"

# Push tag to remote
git push origin v1.2.3
```

### Step 3: Deploy Tag to Staging

```bash
# Deploy the tagged version to a staging slot
./scripts/deploy-staging.sh 1 v1.2.3
```

### Step 4: Verify on Staging

Before promoting to production, verify:

- [ ] Application starts without errors
- [ ] Health checks pass
- [ ] Key user flows work (login, dashboard, campaigns)
- [ ] DAG can be triggered and completes successfully
- [ ] No critical errors in logs
- [ ] Database migrations applied correctly (if any)

### Step 5: Promote to Production

Once staging verification passes:

```bash
# Deploy the same tag to production
./scripts/deploy-production.sh v1.2.3
```

## Version Comparison

### Compare Staging and Production Versions

```bash
# Check staging version
curl https://staging-1.jobsearch.example.com/api/version

# Check production version
curl https://jobsearch.example.com/api/version
```

### Expected Response

```json
{
    "environment": "staging",
    "slot": 1,
    "branch": "v1.2.3",
    "commit_sha": "abc123def456...",
    "deployed_at": "2025-01-22T10:30:00Z"
}
```

## Production Deployment Rules

### Pre-Deployment Checklist

- [ ] Tag exists and matches what was tested on staging
- [ ] All CI checks pass on the tag
- [ ] Staging verification complete
- [ ] Database backup created (if needed)
- [ ] Deployment window scheduled (if applicable)

### Deployment Restrictions

1. **Tagged commits only**: Production deploys only from tagged commits
2. **Same tag on staging**: The tag must be successfully tested on staging first
3. **No hotfixes without tags**: Even urgent fixes must follow the tagging process
4. **Rollback plan ready**: Know the previous tag to rollback to if needed

## Rollback Procedure

If issues are found after production deployment:

```bash
# Rollback to previous tag
./scripts/deploy-production.sh v1.2.2

# Or, if scripts aren't available, manually:
ssh deploy@production-server
cd /home/deploy/production/job-search-project
git checkout v1.2.2
docker compose -f docker-compose.yml -f docker-compose.production.yml down
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d
```

## Hotfix Process

For urgent production fixes:

1. Create a hotfix branch from the current production tag:
   ```bash
   git checkout v1.2.3
   git checkout -b hotfix/critical-bug-fix
   ```

2. Make the fix and commit

3. Create a new patch version tag:
   ```bash
   git tag -a v1.2.4 -m "Hotfix: Critical bug fix"
   git push origin v1.2.4
   ```

4. Deploy to staging, verify, then promote to production

## Release Notes

For each release, update `CHANGELOG.md` with:

- Version number and date
- Summary of changes
- Breaking changes (if any)
- Migration steps (if any)
- Contributors

Example:

```markdown
## [1.2.3] - 2025-01-22

### Added
- New feature X

### Fixed
- Bug in Y

### Changed
- Improved Z performance
```

## Monitoring After Deployment

After production deployment:

1. **Check logs**: `docker compose logs -f --tail=100`
2. **Monitor health**: Watch `/api/health` endpoint
3. **Check metrics**: Review application metrics dashboard
4. **Watch for errors**: Monitor error tracking system
5. **User feedback**: Be available for user-reported issues

## Scheduled Maintenance

For deployments requiring downtime:

1. Schedule maintenance window
2. Notify users in advance
3. Enable maintenance mode (if available)
4. Perform deployment
5. Verify functionality
6. Disable maintenance mode
7. Send completion notification
