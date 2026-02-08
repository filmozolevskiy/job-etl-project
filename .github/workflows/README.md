# GitHub Actions Workflows

This directory contains GitHub Actions workflows for CI/CD.

## Workflows

### CI (`ci.yml`)

Runs on every pull request and push to main/develop branches:
- Lint and format checking (ruff)
- Unit and integration tests (pytest)
- dbt tests (optional, disabled by default)

### Deploy Dedicated Production (`deploy-production-dedicated.yml`)

Automatically deploys to the **dedicated production environment** when code is pushed to the `main` branch.

**Requirements:**
- CI workflow must pass before deployment
- Requires GitHub secrets: `PROD_DROPLET_HOST`, `SSH_PRIVATE_KEY`

**What it does:**
1. Connects to the dedicated production droplet via SSH.
2. Updates code in `/home/deploy/job-search-project`.
3. Builds Docker images using `docker-compose.production.yml`.
4. Runs `dbt` and custom migrations.
5. Restarts services and verifies health.

### Deploy to Staging (`deploy-staging.yml`)

Manually triggered workflow to deploy any branch to one of the 10 staging slots.

**Trigger:**
1. Go to Actions tab in GitHub.
2. Select "Deploy to Staging".
3. Click "Run workflow".
4. Enter the **Slot Number** (1-10) and the **Branch Name**.

**Requirements:**
- Requires GitHub secrets: `DROPLET_HOST` (staging droplet), `SSH_PRIVATE_KEY`

## Required GitHub Secrets

Configure these secrets in GitHub repository settings (Settings → Secrets and variables → Actions):

### `SSH_PRIVATE_KEY` (required)
SSH private key for the `deploy` user on both staging and production droplets.

### `PROD_DROPLET_HOST` (required)
IP address of the dedicated production droplet (e.g., `167.99.0.168`).

### `DROPLET_HOST` (required)
IP address of the shared staging droplet (e.g., `134.122.35.239`).

### `DIGITALOCEAN_API_TOKEN` (optional)
Used for additional verification steps in some workflows.

## Manual Deployment

Both production and staging can be triggered manually via the GitHub Actions UI.

## Troubleshooting

### Deployment fails with SSH connection error
- Verify `SSH_PRIVATE_KEY` secret is set correctly.
- Ensure the corresponding public key is in `~/.ssh/authorized_keys` on the target droplet.

### Services not starting
- Check Docker logs on the droplet:
  ```bash
  # For production
  docker-compose -f docker-compose.yml -f docker-compose.production.yml -p production logs
  
  # For staging slot N
  docker compose -p staging-N logs
  ```
