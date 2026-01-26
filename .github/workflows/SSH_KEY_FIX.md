# SSH Key Fix for Deployment Workflow

## Problem

The deployment workflow is failing with:
```
Error loading key "(stdin)": error in libcrypto
Error: Command failed: ssh-add -
Error loading key "(stdin)": error in libcrypto
```

## Root Cause

This error typically occurs when:
1. **Line endings are wrong**: SSH keys must use LF (Unix) line endings, not CRLF (Windows)
2. **Key format is incorrect**: Missing proper header/footer or extra whitespace
3. **Key is corrupted**: Incomplete or malformed key

## Solution

### Option 1: Fix the GitHub Secret (Recommended)

1. **Get your SSH private key** (the one that matches the public key on the droplet):
   ```bash
   # On your local machine
   cat ~/.ssh/id_rsa
   # Or wherever your SSH key is located
   ```

2. **Ensure proper format** - The key should look like:
   ```
   -----BEGIN OPENSSH PRIVATE KEY-----
   [base64 encoded key data]
   -----END OPENSSH PRIVATE KEY-----
   ```
   OR (for older format):
   ```
   -----BEGIN RSA PRIVATE KEY-----
   [base64 encoded key data]
   -----END RSA PRIVATE KEY-----
   ```

3. **Fix line endings** (if on Windows):
   ```bash
   # Convert CRLF to LF
   # Using PowerShell:
   (Get-Content ~/.ssh/id_rsa -Raw) -replace "`r`n", "`n" | Set-Content ~/.ssh/id_rsa -NoNewline
   
   # Or using dos2unix (if installed):
   dos2unix ~/.ssh/id_rsa
   ```

4. **Update GitHub Secret**:
   - Go to: https://github.com/filmozolevskiy/job-etl-project/settings/secrets/actions
   - Edit `SSH_PRIVATE_KEY`
   - Paste the entire key (including `-----BEGIN...` and `-----END...` lines)
   - Make sure there are no extra spaces or line breaks
   - Save

### Option 2: Verify Key Format

To verify your key is correct:

```bash
# Test if key can be loaded
ssh-keygen -l -f ~/.ssh/id_rsa

# If that works, the key format is correct
```

### Option 3: Generate New Key Pair (If needed)

If the key is corrupted, generate a new one:

```bash
# Generate new SSH key
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy

# Copy public key to droplet
ssh-copy-id -i ~/.ssh/github_actions_deploy.pub deploy@134.122.35.239

# Or manually add to droplet:
cat ~/.ssh/github_actions_deploy.pub | ssh deploy@134.122.35.239 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# Then update GitHub secret with the private key:
cat ~/.ssh/github_actions_deploy
```

## Verification

After updating the secret:

1. **Test locally** (if you have the key):
   ```bash
   ssh -i ~/.ssh/id_rsa deploy@134.122.35.239 "echo 'SSH connection successful'"
   ```

2. **Re-run the deployment workflow**:
   - Go to: https://github.com/filmozolevskiy/job-etl-project/actions/workflows/deploy-production.yml
   - Click "Re-run failed jobs" or trigger a new run

## Common Issues

### Issue: "No such file or directory"
- **Cause**: Key path is wrong
- **Fix**: Use the full key content in the secret, not a file path

### Issue: "Permission denied"
- **Cause**: Key permissions on droplet are wrong
- **Fix**: On droplet, run:
  ```bash
  chmod 600 ~/.ssh/authorized_keys
  chmod 700 ~/.ssh
  ```

### Issue: "Host key verification failed"
- **Cause**: GitHub Actions runner doesn't have the host key
- **Fix**: Already handled in workflow with `ssh-keyscan`

## Workflow Update

The workflow has been updated to better handle SSH keys. If issues persist:

1. Check the secret format in GitHub
2. Verify the key works locally
3. Check workflow logs for more details
