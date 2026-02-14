# Deployment to Production

This document describes the production deployment process.

## Production Environment

- **URL**: http://167.99.0.168
- **Airflow**: http://167.99.0.168:8080
- **Deploy**: `./scripts/deploy-production-dedicated.sh main`

## Triggering Deploy

The deployment triggers automatically on push to main via `.github/workflows/deploy-production-dedicated.yml`.

Manual deploy: `./scripts/deploy-production-dedicated.sh main`

## Troubleshooting: Production Not Accessible

If http://167.99.0.168 returns "Connection refused" or times out:

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
| Can't login (CORS or 401) | Backend rejects browser origin or no admin user | In `.env.production` set `CORS_ORIGINS=http://167.99.0.168` (and your domain if different). Ensure DB has admin user (run `19_seed_admin_user.sql` on production DB if needed). |
| Containers crash immediately | DB connection failure, bad config | Check logs: `docker logs production-frontend` and `production-backend-api` |
| **Login/API returns 500, health shows DB unhealthy** | Droplet cannot reach Managed PostgreSQL (firewall) | In DigitalOcean: Databases → your cluster → **Settings** → **Trusted Sources**. Add the droplet (by ID) or its public IP `167.99.0.168`. Save and retry. |
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
