# Deployment to Production

This document describes the production deployment process.

## Production Environment

- **URL**: https://justapply.net
- **Airflow**: https://justapply.net/airflow/
- **Deploy**: `./scripts/deploy-production.sh main`

### Production SMTP (SendGrid)

Email notifications use SendGrid on port 2525 (DigitalOcean blocks 587). On the droplet, ensure `/home/deploy/.env.production` includes:

- `SMTP_HOST=smtp.sendgrid.net`
- `SMTP_PORT=2525`
- `SMTP_USER=apikey`
- `SMTP_PASSWORD=<SendGrid API key>`
- `SMTP_FROM_EMAIL=admin@justapply.net`

`admin@justapply.net` must be verified in SendGrid (Single Sender or domain authentication).

## Triggering Deploy

The deployment triggers automatically on push to main via `.github/workflows/deploy-production-dedicated.yml`.

Manual deploy: `./scripts/deploy-production.sh main`

## Backup and Rollback

### Backup Strategy

Before each deploy, the deploy script saves the current production state to `last-known-good.json` on the droplet (`/home/deploy/last-known-good.json`). This file contains the commit SHA, branch, and deploy timestamp of the last successful run. Docker images for previous commits remain available on GHCR (tagged with the commit SHA).

### Rollback Procedure

If a deploy fails and production is broken:

1. **Run the rollback script** (recommended):
   ```bash
   ./scripts/rollback-production.sh
   ```
   This fetches the last-known-good commit from the droplet and re-deploys using that SHA.

2. **Or deploy a specific commit manually**:
   ```bash
   ./scripts/deploy-production.sh <commit-sha>
   ```
   Use the full 40-char SHA or short 7-char SHA of a known-good commit.

3. **Verify** production is healthy:
   ```bash
   curl -sf https://justapply.net/api/ping
   ```

### When to Roll Back

- Containers crash on startup after a new deploy
- Health check fails after deploy
- Critical bug discovered post-deploy

### Notes

- `last-known-good.json` is created only after at least one successful deploy. The first deploy has no backup.
- The rollback script requires `GITHUB_TOKEN` or `REGISTRY_TOKEN` for `docker pull` from ghcr.io.
- For manual recovery without the rollback script, see "Manual recovery on the droplet" below.

## Troubleshooting: Production Not Accessible

If https://justapply.net returns "Connection refused" or times out:

### 1. Run diagnostics (requires SSH)

```bash
./scripts/deploy-production.sh --diagnose
```

This SSHs to the droplet and reports:
- Environment file presence
- Docker/container status
- Port 80 listener
- Recent container logs

### 2. Common causes and fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Connection refused on port 80 | Containers not running | SSH to droplet, run `docker compose -f docker-compose.yml -f docker-compose.production.yml -p production up -d` |
| Missing .env.production | Deploy failed at startup | Create `/home/deploy/.env.production` on droplet (see .env.example) |
| Containers crash immediately | DB connection failure, bad config | Check logs: `docker logs production-frontend` and `production-backend-api` |
| GitHub Actions deploy fails | Missing secrets (PROD_DROPLET_SSH_KEY, GITHUB_TOKEN) | Configure repo secrets in GitHub Settings |

### 3. Manual recovery on the droplet

```bash
ssh deploy@167.99.0.168
cd /home/deploy/job-search-project
# Ensure .env.production exists
export ENVIRONMENT=production
docker compose -f docker-compose.yml -f docker-compose.production.yml -p production up -d
docker compose -f docker-compose.yml -f docker-compose.production.yml -p production ps
```
