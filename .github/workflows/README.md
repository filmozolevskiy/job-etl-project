# GitHub Actions Workflows

This directory contains GitHub Actions workflows for CI/CD.

## Workflows

### CI (`ci.yml`)

Runs on every pull request and push to main/develop branches:
- Lint and format checking (ruff)
- Unit and integration tests (pytest)
- dbt tests (optional, disabled by default)

### Deploy to Production (`deploy-production.yml`)

Automatically deploys to production (staging-10) when code is pushed to `main` branch.

**Requirements:**
- CI workflow must pass before deployment
- Requires GitHub secrets (see below)

**What it does:**
1. Verifies CI passed for the commit
2. Verifies droplet status via DigitalOcean API (if token provided)
3. Connects to staging droplet via SSH
4. Updates code on staging-10
5. Builds Docker images, runs initial `dbt run` (creates marts e.g. `fact_jobs`), then starts containers
6. Verifies deployment health

**Note:** While we use DigitalOcean API token for verification and status checks, SSH is still required for executing deployment commands on the droplet, as DigitalOcean API doesn't provide remote command execution capabilities.

## Required GitHub Secrets

To enable automatic deployment, configure these secrets in GitHub repository settings:

### `DIGITALOCEAN_API_TOKEN` (required)
DigitalOcean API token for verifying droplet status and getting droplet information.

**How to create:**
1. Go to [DigitalOcean API Tokens](https://cloud.digitalocean.com/account/api/tokens)
2. Click "Generate New Token"
3. Give it a name (e.g., "GitHub Actions Deploy")
4. Select "Write" scope (or "Read" if you only want verification)
5. Copy the token and add it to GitHub secrets

**To set:**
- Go to repository Settings → Secrets and variables → Actions
- Add new secret: `DIGITALOCEAN_API_TOKEN` = `<your-api-token>`

### `SSH_PRIVATE_KEY` (required)
SSH private key for connecting to the staging droplet. **Note:** SSH is still required for executing deployment commands on the droplet, as DigitalOcean API doesn't provide a way to execute commands remotely.

This should be the private key that corresponds to a public key installed on the droplet for the `deploy` user.

**How to generate:**
```bash
# Generate a new SSH key pair (if you don't have one)
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy

# Copy the public key to the droplet
ssh-copy-id -i ~/.ssh/github_actions_deploy.pub deploy@134.122.35.239

# Add the private key to GitHub secrets
# Copy the contents of ~/.ssh/github_actions_deploy (without .pub)
```

### `DROPLET_HOST` (optional)
The IP address or hostname of the staging droplet. Defaults to `134.122.35.239` if not set. The workflow will also try to discover the IP via DigitalOcean API if `DIGITALOCEAN_API_TOKEN` is provided.

**To set:**
- Go to repository Settings → Secrets and variables → Actions
- Add new secret: `DROPLET_HOST` = `134.122.35.239` (or your droplet IP)

## Manual Deployment

You can also trigger deployment manually:

1. Go to Actions tab in GitHub
2. Select "Deploy to Production" workflow
3. Click "Run workflow"
4. Select branch (usually `main`) and click "Run workflow"

## Troubleshooting

### Deployment fails with SSH connection error
- Verify `SSH_PRIVATE_KEY` secret is set correctly
- Ensure the corresponding public key is in `~/.ssh/authorized_keys` on the droplet
- Check that the droplet is accessible from GitHub Actions runners

### SSH "Connection timed out" (port 22)
The droplet firewall is blocking SSH from GitHub Actions IPs. **Fix:** Allow SSH from GitHub (or temporarily from anywhere). See [FIREWALL_SSH_FIX.md](FIREWALL_SSH_FIX.md).

**Quick fix via recovery console:**
```bash
sudo ufw allow 22/tcp
sudo ufw reload
```
If you use a DigitalOcean Cloud Firewall, add an inbound rule to allow SSH (port 22) from `0.0.0.0/0` or from [GitHub Actions IP ranges](https://api.github.com/meta) (`actions` key).

### DigitalOcean API verification fails
- Verify `DIGITALOCEAN_API_TOKEN` secret is set correctly
- Check that the API token has read permissions
- If API verification fails, the workflow will fall back to using the IP from `DROPLET_HOST` secret
- The workflow will still proceed even if API verification fails (it's optional)

### Deployment fails with "CI workflow not found"
- This is normal for the first few commits - the workflow will proceed
- For subsequent runs, ensure CI workflow completes before deployment

### Services not starting / no staging-10 containers
- Compose uses `env_file: .env.staging` and `.env` in the project dir. The deploy workflow **symlinks** these to `~/.env.staging-10` before `docker compose up`.
- Ensure `~/staging-10/.env.staging-10` exists. **Quick setup:** Copy from staging-1 and adapt:
  ```bash
  # On droplet, from repo root
  ./scripts/copy_staging1_env_to_staging10.sh
  ```
  Then ensure `job_search_staging_10` exists on the Postgres instance.
- Check Docker logs: `docker compose -p staging-10 logs`
- Verify database connectivity from the droplet.

### Why SSH is still required
DigitalOcean API doesn't provide a way to execute commands on droplets remotely. SSH is the standard and secure method for remote command execution. The DigitalOcean API token is used for:
- Verifying droplet status before deployment
- Getting droplet information dynamically
- Future enhancements (monitoring, alerts, etc.)
