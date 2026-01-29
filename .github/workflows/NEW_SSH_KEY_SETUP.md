# New SSH Key Setup

A new SSH key pair was created for GitHub Actions deployment (no passphrase).

## Key Location

- **Private**: `~/.ssh/github_actions_deploy`
- **Public**: `~/.ssh/github_actions_deploy.pub`

## 1. Add Public Key to Droplet

You must add the public key to `~/.ssh/authorized_keys` on the droplet for user `deploy`.

### Option A: SSH (if you have access)

```powershell
ssh-copy-id -i $env:USERPROFILE\.ssh\github_actions_deploy.pub deploy@134.122.35.239
```

Or manually:
```powershell
type $env:USERPROFILE\.ssh\github_actions_deploy.pub | ssh deploy@134.122.35.239 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

### Option B: DigitalOcean Web Console

1. Open [DigitalOcean Droplet Console](https://cloud.digitalocean.com/droplets)
2. Select the droplet, then **Access** → **Launch Droplet Console**
3. Log in as `deploy` (or `root` then `su - deploy`)
4. Run:
   ```bash
   mkdir -p ~/.ssh
   echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFulDnoMtJmHfuXqxRbB5ytctodxw9fwJLjnrlagyl/7 github-actions-deploy' >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   chmod 700 ~/.ssh
   ```

### Option C: DigitalOcean MCP / API

If you use MCP or the API to manage the droplet, add the public key via your usual method.

## 2. Add Private Key to GitHub Secret

1. Go to: https://github.com/filmozolevskiy/job-etl-project/settings/secrets/actions
2. Edit **SSH_PRIVATE_KEY** (or create it)
3. Paste the **entire** private key, including:
   - `-----BEGIN OPENSSH PRIVATE KEY-----`
   - All lines of base64
   - `-----END OPENSSH PRIVATE KEY-----`
4. Save

To copy the private key (Windows):
```powershell
Get-Content $env:USERPROFILE\.ssh\github_actions_deploy -Raw | Set-Clipboard
```
Then paste into the GitHub secret field.

## 3. Test Connection

```powershell
ssh -i $env:USERPROFILE\.ssh\github_actions_deploy deploy@134.122.35.239 "echo OK"
```

## 4. Re-run Deployment

After both steps:

- Manually trigger: https://github.com/filmozolevskiy/job-etl-project/actions/workflows/deploy-production.yml → **Run workflow**
- Or push to `main` and let CI → CD run

## Security Note

This key has **no passphrase**. Keep the private key secure and use it only for this deployment. Do not commit it to the repo.
