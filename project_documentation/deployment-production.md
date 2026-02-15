# Deployment to Production

This document describes the production deployment process.

## Production Environment

- **URL**: https://justapply.net
- **Airflow**: https://justapply.net/airflow/
- **Deploy**: `./scripts/deploy-production-dedicated.sh main`

## Triggering Deploy

The deployment triggers automatically on push to main via `.github/workflows/deploy-production-dedicated.yml`.

Manual deploy: `./scripts/deploy-production-dedicated.sh main`

## Troubleshooting: Production Not Accessible

If https://justapply.net returns "Connection refused" or times out:

### 1. Run diagnostics (requires SSH)

```bash
./scripts/deploy-production-dedicated.sh --diagnose
```

This SSHs to the droplet and reports:
- Environment file presence
- Docker/container status
- Port 80 listener
- Recent container logs

### 2. Common causes and fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Connection refused on port 80 | Containers not running | SSH to droplet, run `docker-compose -f docker-compose.yml -f docker-compose.production.yml -p production up -d` |
| Missing .env.production | Deploy failed at startup | Create `/home/deploy/.env.production` on droplet (see .env.example) |
| Containers crash immediately | DB connection failure, bad config | Check logs: `docker logs production-frontend` and `production-backend-api` |
| GitHub Actions deploy fails | Missing secrets (PROD_DROPLET_SSH_KEY, GITHUB_TOKEN) | Configure repo secrets in GitHub Settings |

### 3. Manual recovery on the droplet

```bash
ssh deploy@167.99.0.168
cd /home/deploy/job-search-project
# Ensure .env.production exists
export ENVIRONMENT=production
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p production up -d
docker-compose -f docker-compose.yml -f docker-compose.production.yml -p production ps
```
